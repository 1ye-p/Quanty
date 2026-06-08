"""cquant.portfolio_opt.cost_aware — Portfolio optimizer with transaction cost awareness."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
from scipy.optimize import minimize

from cquant.portfolio_opt.constraints import ConstraintConfig

from cquant.portfolio_opt.base import OptimizationResult, PortfolioOptimizer

logger = logging.getLogger(__name__)


class CostAwareOptimizer(PortfolioOptimizer):
    """Mean-variance optimizer with transaction cost penalty.

    Adds a turnover penalty to the objective function to discourage
    large portfolio changes that would incur high trading costs.

    Usage::

        optimizer = CostAwareOptimizer(cost_rate=0.001, turnover_penalty=0.0005)
        result = optimizer.optimize(
            expected_returns=returns,
            covariance=cov,
            constraints={"current_weights": {"A": 0.3, "B": 0.4, "C": 0.3}},
        )
    """

    def __init__(
        self,
        risk_free_rate: float = 0.0,
        long_only: bool = True,
        cost_rate: float = 0.001,
        turnover_penalty: float = 0.0005,
    ) -> None:
        self._risk_free_rate = risk_free_rate
        self._long_only = long_only
        self._cost_rate = cost_rate
        self._turnover_penalty = turnover_penalty

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
            current_weights=constraints.get("current_weights", {}),
        )

    def optimize(
        self,
        expected_returns: dict[str, float],
        covariance: dict[str, dict[str, float]],
        constraints: dict[str, Any] | ConstraintConfig | None = None,
    ) -> OptimizationResult:
        if not expected_returns:
            return OptimizationResult(weights={})

        cfg = self._normalise_constraints(constraints)
        assets, mu, sigma = self._to_arrays(expected_returns, covariance)
        n = len(assets)

        w_current = np.array([cfg.current_weights.get(a, 0.0) for a in assets])

        if cfg.long_only:
            bounds = [
                (max(0.0, cfg.min_weights.get(a, cfg.min_weight)), cfg.max_weights.get(a, cfg.max_weight))
                for a in assets
            ]
        else:
            bounds = [
                (-cfg.max_weights.get(a, cfg.max_weight), cfg.max_weights.get(a, cfg.max_weight))
                for a in assets
            ]

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

        eq_constraint = {"type": "eq", "fun": lambda w: np.sum(w) - 1.0}

        def objective(w: np.ndarray) -> float:
            port_return = np.dot(w, mu)
            port_vol = np.sqrt(np.dot(w, np.dot(sigma, w)))
            sharpe = -(port_return - self._risk_free_rate) / max(port_vol, 1e-10)

            turnover = np.sum(np.abs(w - w_current))
            cost = self._cost_rate * turnover
            penalty = self._turnover_penalty * turnover ** 2

            return sharpe + cost + penalty

        w0 = np.ones(n) / n

        result = minimize(
            objective,
            w0,
            method="SLSQP",
            bounds=bounds,
            constraints=[eq_constraint],
            options={"maxiter": 1000, "ftol": 1e-10},
        )

        if not result.success:
            logger.warning("Cost-aware optimization did not converge: %s", result.message)

        optimal_weights = result.x
        port_return = float(np.dot(optimal_weights, mu))
        port_vol = float(np.sqrt(np.dot(optimal_weights, np.dot(sigma, optimal_weights))))
        sharpe = (port_return - self._risk_free_rate) / port_vol if port_vol > 0 else 0.0
        turnover = float(np.sum(np.abs(optimal_weights - w_current)))

        weights_dict = {assets[i]: float(optimal_weights[i]) for i in range(n)}

        return OptimizationResult(
            weights=weights_dict,
            expected_return=port_return,
            expected_volatility=port_vol,
            sharpe_ratio=sharpe,
            metadata={
                "optimizer": "cost_aware",
                "success": result.success,
                "turnover": turnover,
                "transaction_cost": self._cost_rate * turnover,
            },
        )
