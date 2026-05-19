"""cquant.portfolio_opt.risk_parity — Risk Parity optimization."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
from scipy.optimize import minimize

from cquant.portfolio_opt.base import OptimizationResult, PortfolioOptimizer

logger = logging.getLogger(__name__)


class RiskParityOptimizer(PortfolioOptimizer):
    """Risk Parity optimizer (Equal Risk Contribution).

    Allocates weights such that each asset contributes equally to portfolio risk.

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
        constraints: dict[str, Any] | None = None,
    ) -> OptimizationResult:
        """Optimize for equal risk contribution."""
        if not expected_returns:
            return OptimizationResult(weights={})

        assets, mu, sigma = self._to_arrays(expected_returns, covariance)
        n = len(assets)

        # Objective: minimize sum of squared differences in risk contribution
        def risk_parity_objective(w):
            port_vol = np.sqrt(np.dot(w, np.dot(sigma, w)))
            if port_vol < 1e-10:
                return 0.0

            # Marginal risk contribution
            mrc = np.dot(sigma, w) / port_vol
            # Risk contribution
            rc = w * mrc
            # Target: equal risk contribution
            target_rc = port_vol / n
            # Sum of squared differences
            return np.sum((rc - target_rc) ** 2)

        # Constraints
        eq_constraint = {"type": "eq", "fun": lambda w: np.sum(w) - 1.0}
        cons = [eq_constraint]

        # Bounds: long-only
        max_weight = (constraints or {}).get("max_weight", 1.0)
        bounds = [(0.0, max_weight) for _ in range(n)]

        # Initial guess: equal weight
        w0 = np.ones(n) / n

        # Optimize
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

        # Extract weights
        optimal_weights = result.x
        port_return = float(np.dot(optimal_weights, mu))
        port_vol = float(np.sqrt(np.dot(optimal_weights, np.dot(sigma, optimal_weights))))

        # Build weights dict
        weights_dict = {assets[i]: float(optimal_weights[i]) for i in range(n)}

        return OptimizationResult(
            weights=weights_dict,
            expected_return=port_return,
            expected_volatility=port_vol,
            sharpe_ratio=(port_return / port_vol) if port_vol > 0 else 0.0,
            metadata={"optimizer": "risk_parity", "success": result.success},
        )
