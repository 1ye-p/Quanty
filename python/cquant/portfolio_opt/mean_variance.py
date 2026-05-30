"""cquant.portfolio_opt.mean_variance — Markowitz Mean-Variance optimization."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
from scipy.optimize import minimize

from cquant.portfolio_opt.base import OptimizationResult, PortfolioOptimizer

logger = logging.getLogger(__name__)


class MeanVarianceOptimizer(PortfolioOptimizer):
    """Markowitz Mean-Variance optimizer.

    Supports long-only constraints, weight bounds, and target return.

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
        constraints: dict[str, Any] | None = None,
    ) -> OptimizationResult:
        """Optimize for maximum Sharpe ratio."""
        if not expected_returns:
            return OptimizationResult(weights={})

        assets, mu, sigma = self._to_arrays(expected_returns, covariance)
        n = len(assets)

        # Default constraints
        con = constraints or {}
        max_weight = con.get("max_weight", 1.0)
        min_weight = con.get("min_weight", 0.0)
        target_return = con.get("target_return", None)
        min_weights = con.get("min_weights", {})  # per-asset lower bounds
        max_weights = con.get("max_weights", {})  # per-asset upper bounds
        current_weights_raw = con.get("current_weights", {})
        turnover_penalty = max(0.0, float(con.get("turnover_penalty", 0.0)))

        # Build per-asset current_weights array
        current_w = np.array(
            [current_weights_raw.get(a, 0.0) for a in assets], dtype=float
        )
        has_current = bool(current_weights_raw) and turnover_penalty != 0.0

        # Bounds (per-asset if provided, else fallback to scalar)
        if self._long_only:
            bounds = [
                (max(0.0, min_weights.get(a, min_weight)), max_weights.get(a, max_weight))
                for a in assets
            ]
        else:
            bounds = [
                (-max_weights.get(a, max_weight), max_weights.get(a, max_weight))
                for a in assets
            ]

        # Constraint: weights sum to 1
        eq_constraint = {"type": "eq", "fun": lambda w: np.sum(w) - 1.0}

        # Optional target return constraint
        if target_return is not None:
            ret_constraint = {
                "type": "eq",
                "fun": lambda w: np.dot(w, mu) - target_return,
            }
            cons = [eq_constraint, ret_constraint]
        else:
            cons = [eq_constraint]

        # Objective: maximize Sharpe ratio (minimize negative Sharpe + turnover penalty)
        def neg_sharpe(w):
            port_return = np.dot(w, mu)
            port_vol = np.sqrt(np.dot(w, np.dot(sigma, w)))
            if port_vol < 1e-10:
                return 1e10
            cost = -(port_return - self._risk_free_rate) / port_vol
            if has_current:
                cost += turnover_penalty * np.sum(np.abs(w - current_w))
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

        # Build weights dict
        weights_dict = {assets[i]: float(optimal_weights[i]) for i in range(n)}

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
