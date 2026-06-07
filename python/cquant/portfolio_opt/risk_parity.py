"""cquant.portfolio_opt.risk_parity — Risk Parity optimization."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
from scipy.optimize import minimize

from cquant.portfolio_opt.base import OptimizationResult, PortfolioOptimizer
from cquant.portfolio_opt.constraints import ConstraintConfig

logger = logging.getLogger(__name__)


class RiskParityOptimizer(PortfolioOptimizer):
    """Risk Parity optimizer (Equal Risk Contribution).

    Allocates weights such that each asset contributes equally to portfolio risk.

    Supports sector limits, factor exposure limits, tracking error budget,
    and asset exclusion via ConstraintConfig.

    Usage::

        optimizer = RiskParityOptimizer()
        result = optimizer.optimize(
            expected_returns={"SSE:600036": 0.10, "SZSE:000858": 0.12},
            covariance={
                "SSE:600036": {"SSE:600036": 0.04, "SZSE:000858": 0.02},
                "SZSE:000858": {"SSE:600036": 0.02, "SZSE:000858": 0.09},
            },
        )
        print(result.weights)
    """

    def optimize(
        self,
        expected_returns: dict[str, float],
        covariance: dict[str, dict[str, float]],
        constraints: dict[str, Any] | ConstraintConfig | None = None,
    ) -> OptimizationResult:
        """Optimize for equal risk contribution."""
        if not expected_returns:
            return OptimizationResult(weights={})

        # Normalise constraints to ConstraintConfig
        cfg = self._normalise_constraints(constraints)

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
                k: {kk: vv for kk, vv in v.items() if kk not in excluded}
                for k, v in covariance.items()
                if k not in excluded
            }

        if not expected_returns:
            return OptimizationResult(weights={})

        assets, mu, sigma = self._to_arrays(expected_returns, covariance)
        n = len(assets)
        asset_idx = {a: i for i, a in enumerate(assets)}

        # ── Objective: equal risk contribution ────────────────────────────────
        def risk_parity_objective(w: np.ndarray) -> float:
            port_vol = np.sqrt(np.dot(w, np.dot(sigma, w)))
            if port_vol < 1e-10:
                return 0.0
            mrc = np.dot(sigma, w) / port_vol
            rc = w * mrc
            target_rc = port_vol / n
            return float(np.sum((rc - target_rc) ** 2))

        # ── Constraints ───────────────────────────────────────────────────────
        eq_constraint = {"type": "eq", "fun": lambda w: np.sum(w) - 1.0}
        cons: list[dict[str, Any]] = [eq_constraint]

        # ── Bounds ────────────────────────────────────────────────────────────
        bounds = [
            (
                max(0.0, cfg.min_weights.get(a, cfg.min_weight)),
                cfg.max_weights.get(a, cfg.max_weight),
            )
            for a in assets
        ]

        # ── Sector limits ─────────────────────────────────────────────────────
        for sector_label, sector_lim in cfg.sector_limits.items():
            idxs = [
                asset_idx[a]
                for a in assets
                if cfg.sector_map.get(a) == sector_label
            ]
            if not idxs:
                continue
            idxs_arr = np.array(idxs)
            cons.append({
                "type": "ineq",
                "fun": lambda w, _i=idxs_arr, _lo=sector_lim.min_weight: float(np.sum(w[_i])) - _lo,
            })
            cons.append({
                "type": "ineq",
                "fun": lambda w, _i=idxs_arr, _hi=sector_lim.max_weight: _hi - float(np.sum(w[_i])),
            })

        # ── Factor exposure limits ────────────────────────────────────────────
        for factor_name, factor_lim in cfg.factor_limits.items():
            loadings = np.array(
                [cfg.factor_loadings.get(a, {}).get(factor_name, 0.0) for a in assets],
                dtype=float,
            )
            cons.append({
                "type": "ineq",
                "fun": lambda w, _l=loadings, _lo=factor_lim.min_exposure: float(np.dot(w, _l)) - _lo,
            })
            cons.append({
                "type": "ineq",
                "fun": lambda w, _l=loadings, _hi=factor_lim.max_exposure: _hi - float(np.dot(w, _l)),
            })

        # ── Tracking error budget ─────────────────────────────────────────────
        if cfg.max_tracking_error is not None and cfg.benchmark_weights:
            bench_w = np.array(
                [cfg.benchmark_weights.get(a, 0.0) for a in assets], dtype=float
            )
            cons.append({
                "type": "ineq",
                "fun": lambda w, _bw=bench_w, _mt=cfg.max_tracking_error: (
                    _mt ** 2 - float(np.dot(w - _bw, np.dot(sigma, w - _bw)))
                ),
            })

        # ── Optimise ──────────────────────────────────────────────────────────
        w0 = np.ones(n) / n

        result = minimize(
            risk_parity_objective,
            w0,
            method="SLSQP",
            bounds=bounds,
            constraints=cons,
            options={"maxiter": 1000, "ftol": 1e-12},
        )

        if not result.success:
            logger.warning("Risk parity optimization did not converge: %s", result.message)

        optimal_weights = result.x
        port_return = float(np.dot(optimal_weights, mu))
        port_vol = float(np.sqrt(np.dot(optimal_weights, np.dot(sigma, optimal_weights))))

        weights_dict: dict[str, float] = {}
        for a in expected_returns:
            weights_dict[a] = float(optimal_weights[asset_idx[a]])
        for a in excluded:
            weights_dict[a] = 0.0

        return OptimizationResult(
            weights=weights_dict,
            expected_return=port_return,
            expected_volatility=port_vol,
            sharpe_ratio=(port_return / port_vol) if port_vol > 0 else 0.0,
            metadata={"optimizer": "risk_parity", "success": result.success},
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
