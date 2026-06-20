"""cquant.portfolio_opt.black_litterman — Black-Litterman portfolio optimization.

Combines market-implied equilibrium returns with investor views to produce
posterior expected returns, then optimizes via mean-variance (MVO).

References:
    - Black & Litterman (1992) "Global Portfolio Optimization"
    - Idzorek (2005) "A Step-By-Step Guide to the Black-Litterman Model"
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

from cquant.portfolio_opt.base import OptimizationResult, PortfolioOptimizer
from cquant.portfolio_opt.constraints import ConstraintConfig

logger = logging.getLogger(__name__)


class BlackLittermanOptimizer(PortfolioOptimizer):
    """Black-Litterman portfolio optimizer.

    Combines market-implied equilibrium returns (prior) with subjective
    investor views to compute posterior expected returns, then delegates
    to MeanVarianceOptimizer for the final weight allocation.

    Parameters
    ----------
    risk_aversion : float
        Market risk aversion coefficient (delta). Default 2.5.
    tau : float
        Scaling factor for the uncertainty of the prior. Controls how
        much weight is given to the equilibrium vs. views. Typical range
        0.01 -- 0.1. Default 0.05.
    risk_free_rate : float
        Risk-free rate for the downstream MVO. Default 0.0.
    long_only : bool
        Whether to enforce long-only constraints. Default True.

    Usage::

        optimizer = BlackLittermanOptimizer()
        result = optimizer.optimize(
            expected_returns={},  # not used directly; views drive returns
            covariance=covariance_dict,
            constraints=None,
            market_weights=market_w_dict,
            views_P=P_matrix,
            views_Q=Q_vector,
        )
    """

    def __init__(
        self,
        risk_aversion: float = 2.5,
        tau: float = 0.05,
        risk_free_rate: float = 0.0,
        long_only: bool = True,
    ) -> None:
        self._risk_aversion = risk_aversion
        self._tau = tau
        self._risk_free_rate = risk_free_rate
        self._long_only = long_only

    def optimize(
        self,
        expected_returns: dict[str, float],
        covariance: dict[str, dict[str, float]],
        constraints: dict[str, Any] | ConstraintConfig | None = None,
        *,
        market_weights: dict[str, float] | None = None,
        views_P: np.ndarray | list[list[float]] | None = None,
        views_Q: np.ndarray | list[float] | None = None,
        views_omega: np.ndarray | list[list[float]] | None = None,
        view_confidences: np.ndarray | list[float] | None = None,
    ) -> OptimizationResult:
        """Optimize portfolio using the Black-Litterman model.

        Parameters
        ----------
        expected_returns : dict
            Asset expected returns (used as fallback if no market weights).
        covariance : dict
            Covariance matrix in nested-dict form.
        constraints : ConstraintConfig or dict or None
            Standard portfolio constraints.
        market_weights : dict[str, float] or None
            Market-cap weights. If ``None``, equal weights are used.
        views_P : array-like (K x N) or None
            Pick matrix defining views.  Row *k* specifies the assets
            involved in view *k* (positive = long, negative = short).
        views_Q : array-like (K,) or None
            Expected return for each view.
        views_omega : array-like (K x K) or None
            Uncertainty matrix for views.  If ``None``, computed
            automatically as ``diag(P @ (tau * Sigma) @ P.T)``.
        view_confidences : array-like (K,) or None
            Per-view confidence in [0, 1].  When provided *and*
            ``views_omega`` is ``None``, omega is scaled by
            ``(1 - confidence) / confidence``.

        Returns
        -------
        OptimizationResult
        """
        if not covariance:
            return OptimizationResult(weights={})

        # ── Convert to arrays ───────────────────────────────────────────────────
        # We need a stable asset ordering.  Use the covariance keys.
        assets = sorted(covariance.keys())
        n = len(assets)
        asset_idx = {a: i for i, a in enumerate(assets)}

        sigma = np.zeros((n, n))
        for i, a in enumerate(assets):
            for j, b in enumerate(assets):
                sigma[i, j] = covariance.get(a, {}).get(b, 0.0)

        # ── Market weights (prior) ──────────────────────────────────────────────
        if market_weights is not None:
            w_mkt = np.array([market_weights.get(a, 0.0) for a in assets])
        else:
            # Fall back to equal weights
            w_mkt = np.ones(n) / n

        # Normalise so they sum to 1
        w_sum = w_mkt.sum()
        if w_sum > 0:
            w_mkt = w_mkt / w_sum

        # ── Implied equilibrium returns: Pi = delta * Sigma * w_mkt ─────────────
        pi = self._risk_aversion * sigma @ w_mkt

        # ── No views => return market portfolio ─────────────────────────────────
        if views_P is None or views_Q is None:
            weights_dict = {assets[i]: float(w_mkt[i]) for i in range(n)}
            port_return = float(w_mkt @ pi)
            port_vol = float(np.sqrt(w_mkt @ sigma @ w_mkt))
            sharpe = (
                (port_return - self._risk_free_rate) / port_vol
                if port_vol > 0
                else 0.0
            )
            return OptimizationResult(
                weights=weights_dict,
                expected_return=port_return,
                expected_volatility=port_vol,
                sharpe_ratio=sharpe,
                metadata={
                    "optimizer": "black_litterman",
                    "prior_returns": pi.tolist(),
                    "posterior_returns": pi.tolist(),
                    "views_applied": 0,
                },
            )

        # ── Ensure views are numpy arrays ───────────────────────────────────────
        P = np.atleast_2d(np.asarray(views_P, dtype=float))
        Q = np.atleast_1d(np.asarray(views_Q, dtype=float))
        k = P.shape[0]

        if P.shape[1] != n:
            raise ValueError(
                f"views_P has {P.shape[1]} columns but covariance has {n} assets"
            )
        if Q.shape[0] != k:
            raise ValueError(
                f"views_P has {k} rows but views_Q has {Q.shape[0]} elements"
            )

        # ── View uncertainty matrix (Omega) ─────────────────────────────────────
        if views_omega is not None:
            omega = np.atleast_2d(np.asarray(views_omega, dtype=float))
        else:
            # Idzorek approach: Omega = diag(P @ (tau * Sigma) @ P.T)
            tau_sigma = self._tau * sigma
            base_omega = np.diag(np.diag(P @ tau_sigma @ P.T))

            if view_confidences is not None:
                conf = np.atleast_1d(np.asarray(view_confidences, dtype=float))
                if conf.shape[0] != k:
                    raise ValueError(
                        f"view_confidences has {conf.shape[0]} elements but "
                        f"views_P has {k} rows"
                    )
                # Scale: omega_i = base_omega_i * (1 - c_i) / c_i
                # High confidence => small omega => view is trusted
                scale = np.where(
                    conf > 0,
                    (1.0 - conf) / conf,
                    1e6,  # zero confidence => very high uncertainty
                )
                omega = base_omega * np.diag(scale)
            else:
                omega = base_omega

        # ── Posterior returns ────────────────────────────────────────────────────
        # E[R] = [(tau*Sigma)^-1 + P' * Omega^-1 * P]^-1
        #        * [(tau*Sigma)^-1 * Pi + P' * Omega^-1 * Q]
        tau_sigma = self._tau * sigma
        tau_sigma_inv = np.linalg.inv(tau_sigma)
        omega_inv = np.linalg.inv(omega)

        M = tau_sigma_inv + P.T @ omega_inv @ P
        M_inv = np.linalg.inv(M)

        posterior_returns = M_inv @ (tau_sigma_inv @ pi + P.T @ omega_inv @ Q)

        # ── Delegate to MVO with posterior returns ──────────────────────────────
        from cquant.portfolio_opt.mean_variance import MeanVarianceOptimizer

        mvo = MeanVarianceOptimizer(
            risk_free_rate=self._risk_free_rate,
            long_only=self._long_only,
        )

        # Build the posterior expected_returns dict for MVO
        posterior_returns_dict = {
            assets[i]: float(posterior_returns[i]) for i in range(n)
        }

        result = mvo.optimize(
            expected_returns=posterior_returns_dict,
            covariance=covariance,
            constraints=constraints,
        )

        # Augment metadata with BL-specific info
        result.metadata.update({
            "optimizer": "black_litterman",
            "prior_returns": pi.tolist(),
            "posterior_returns": posterior_returns.tolist(),
            "views_applied": k,
            "risk_aversion": self._risk_aversion,
            "tau": self._tau,
        })

        return result

    def _normalise_constraints(
        self,
        constraints: dict[str, Any] | ConstraintConfig | None,
    ) -> ConstraintConfig:
        """Normalise constraints (same pattern as MVO)."""
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
