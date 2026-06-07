"""cquant.portfolio_opt.mean_variance — Markowitz Mean-Variance optimization."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
from scipy.optimize import minimize

from cquant.portfolio_opt.base import OptimizationResult, PortfolioOptimizer
from cquant.portfolio_opt.constraints import ConstraintConfig

logger = logging.getLogger(__name__)


class MeanVarianceOptimizer(PortfolioOptimizer):
    """Markowitz Mean-Variance optimizer.

    Supports long-only constraints, weight bounds, target return,
    sector limits, factor exposure limits, tracking error budget,
    and asset exclusion.

    Usage::

        optimizer = MeanVarianceOptimizer()
        result = optimizer.optimize(
            expected_returns={"SSE:600036": 0.10, "SZSE:000858": 0.12},
            covariance={
                "SSE:600036": {"SSE:600036": 0.04, "SZSE:000858": 0.02},
                "SZSE:000858": {"SSE:600036": 0.02, "SZSE:000858": 0.09},
            },
        )
        print(result.weights)
    """

    def __init__(
        self,
        risk_free_rate: float = 0.0,
        long_only: bool = True,
    ) -> None:
        self._risk_free_rate = risk_free_rate
        self._long_only = long_only

    def optimize(
        self,
        expected_returns: dict[str, float],
        covariance: dict[str, dict[str, float]],
        constraints: dict[str, Any] | ConstraintConfig | None = None,
    ) -> OptimizationResult:
        """Optimize for maximum Sharpe ratio."""
        if not expected_returns:
            return OptimizationResult(weights={})

        # Normalise constraints to ConstraintConfig
        cfg = self._normalise_constraints(constraints)

        # Validate
        errors = cfg.validate()
        if errors:
            raise ValueError("Invalid constraints: " + "; ".join(errors))

        # Filter out excluded assets
        excluded = cfg.get_excluded_assets()
        if excluded:
            expected_returns = {
                k: v for k, v in expected_returns.items() if k not in excluded
            }
            covariance = {
                k: v for k, v in covariance.items() if k not in excluded
            }
            # Also remove excluded keys from inner dicts
            covariance = {
                k: {kk: vv for kk, vv in v.items() if kk not in excluded}
                for k, v in covariance.items()
            }

        if not expected_returns:
            return OptimizationResult(weights={})

        assets, mu, sigma = self._to_arrays(expected_returns, covariance)
        n = len(assets)
        asset_idx = {a: i for i, a in enumerate(assets)}

        # ── Build per-asset bounds ────────────────────────────────────────────
        bounds = []
        for a in assets:
            lo = max(0.0, cfg.min_weights.get(a, cfg.min_weight)) if cfg.long_only else -cfg.max_weights.get(a, cfg.max_weight)
            hi = cfg.max_weights.get(a, cfg.max_weight)
            bounds.append((lo, hi))

        # ── Equality constraints ──────────────────────────────────────────────
        eq_constraint = {"type": "eq", "fun": lambda w: np.sum(w) - 1.0}
        cons: list[dict[str, Any]] = [eq_constraint]

        # Target return
        if cfg.target_return is not None:
            cons.append({
                "type": "eq",
                "fun": lambda w: np.dot(w, mu) - cfg.target_return,
            })

        # ── Turnover constraints ──────────────────────────────────────────────
        current_w = np.array(
            [cfg.current_weights.get(a, 0.0) for a in assets], dtype=float
        )
        has_current = bool(cfg.current_weights) and cfg.turnover_penalty != 0.0

        if cfg.max_turnover is not None and has_current:
            cons.append({
                "type": "ineq",
                "fun": lambda w, _mt=cfg.max_turnover: _mt - np.sum(np.abs(w - current_w)),
            })

        # ── Sector limits (inequality constraints) ────────────────────────────
        for sector_label, sector_lim in cfg.sector_limits.items():
            # Find indices of assets belonging to this sector
            idxs = [
                asset_idx[a]
                for a in assets
                if cfg.sector_map.get(a) == sector_label
            ]
            if not idxs:
                continue
            idxs_arr = np.array(idxs)
            # lower: sum(weights[idxs]) >= min_weight
            cons.append({
                "type": "ineq",
                "fun": lambda w, _i=idxs_arr, _lo=sector_lim.min_weight: float(np.sum(w[_i])) - _lo,
            })
            # upper: sum(weights[idxs]) <= max_weight
            cons.append({
                "type": "ineq",
                "fun": lambda w, _i=idxs_arr, _hi=sector_lim.max_weight: _hi - float(np.sum(w[_i])),
            })

        # ── Factor exposure limits (inequality constraints) ───────────────────
        for factor_name, factor_lim in cfg.factor_limits.items():
            # Build factor loading vector for this factor
            loadings = np.array(
                [cfg.factor_loadings.get(a, {}).get(factor_name, 0.0) for a in assets],
                dtype=float,
            )
            # lower: w . loadings >= min_exposure
            cons.append({
                "type": "ineq",
                "fun": lambda w, _l=loadings, _lo=factor_lim.min_exposure: float(np.dot(w, _l)) - _lo,
            })
            # upper: w . loadings <= max_exposure
            cons.append({
                "type": "ineq",
                "fun": lambda w, _l=loadings, _hi=factor_lim.max_exposure: _hi - float(np.dot(w, _l)),
            })

        # ── Tracking error budget (inequality constraint) ─────────────────────
        if cfg.max_tracking_error is not None and cfg.benchmark_weights:
            bench_w = np.array(
                [cfg.benchmark_weights.get(a, 0.0) for a in assets], dtype=float
            )
            # TE = sqrt((w - b)' Sigma (w - b))
            # Constraint: TE <= max_tracking_error
            # Equivalent: max_TE^2 - (w-b)' Sigma (w-b) >= 0
            cons.append({
                "type": "ineq",
                "fun": lambda w, _bw=bench_w, _mt=cfg.max_tracking_error: (
                    _mt ** 2 - float(np.dot(w - _bw, np.dot(sigma, w - _bw)))
                ),
            })

        # ── Objective: negative Sharpe ratio + turnover penalty ───────────────
        def neg_sharpe(w: np.ndarray) -> float:
            port_return = float(np.dot(w, mu))
            port_vol = float(np.sqrt(np.dot(w, np.dot(sigma, w))))
            if port_vol < 1e-10:
                return 1e10
            cost = -(port_return - self._risk_free_rate) / port_vol
            if has_current:
                cost += cfg.turnover_penalty * float(np.sum(np.abs(w - current_w)))
            return cost

        # Initial guess: equal weight
        w0 = np.ones(n) / n

        # Optimize
        result = minimize(
            neg_sharpe,
            w0,
            method="SLSQP",
            bounds=bounds,
            constraints=cons,
            options={"maxiter": 1000, "ftol": 1e-10},
        )

        if not result.success:
            logger.warning("Optimization did not converge: %s", result.message)

        # Extract weights
        optimal_weights = result.x
        port_return = float(np.dot(optimal_weights, mu))
        port_vol = float(np.sqrt(np.dot(optimal_weights, np.dot(sigma, optimal_weights))))
        sharpe = (port_return - self._risk_free_rate) / port_vol if port_vol > 0 else 0.0

        # Build weights dict (include excluded assets with 0 weight for completeness)
        weights_dict: dict[str, float] = {}
        for a in expected_returns:
            weights_dict[a] = float(optimal_weights[asset_idx[a]])
        for a in excluded:
            weights_dict[a] = 0.0

        # Compute actual turnover
        actual_turnover = float(np.sum(np.abs(optimal_weights - current_w)))

        return OptimizationResult(
            weights=weights_dict,
            expected_return=port_return,
            expected_volatility=port_vol,
            sharpe_ratio=sharpe,
            metadata={
                "optimizer": "mean_variance",
                "success": result.success,
                "turnover": actual_turnover,
            },
        )

    # ── helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _normalise_constraints(
        constraints: dict[str, Any] | ConstraintConfig | None,
    ) -> ConstraintConfig:
        """Accept either a ConstraintConfig or a legacy dict and return a ConstraintConfig."""
        if constraints is None:
            return ConstraintConfig()
        if isinstance(constraints, ConstraintConfig):
            return constraints
        # Legacy dict path
        return ConstraintConfig(
            long_only=constraints.get("long_only", True),
            max_weight=constraints.get("max_weight", 1.0),
            min_weight=constraints.get("min_weight", 0.0),
            min_weights=constraints.get("min_weights", {}),
            max_weights=constraints.get("max_weights", {}),
            max_turnover=constraints.get("max_turnover"),
            turnover_penalty=constraints.get("turnover_penalty", 0.0),
            current_weights=constraints.get("current_weights", {}),
            target_return=constraints.get("target_return"),
            sector_map=constraints.get("sector_map", {}),
            sector_limits=constraints.get("sector_limits", {}),
            factor_loadings=constraints.get("factor_loadings", {}),
            factor_limits=constraints.get("factor_limits", {}),
            max_tracking_error=constraints.get("max_tracking_error"),
            benchmark_weights=constraints.get("benchmark_weights", {}),
            exclude_assets=set(constraints.get("exclude_assets", [])),
            exclude_st=constraints.get("exclude_st", False),
            st_assets=set(constraints.get("st_assets", [])),
            exclude_suspended=constraints.get("exclude_suspended", False),
            suspended_assets=set(constraints.get("suspended_assets", [])),
        )
