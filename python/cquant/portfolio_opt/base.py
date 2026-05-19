"""cquant.portfolio_opt.base — Portfolio optimizer ABC."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class OptimizationResult:
    """Result of portfolio optimization."""
    weights: dict[str, float]  # asset_id -> weight
    expected_return: float = 0.0
    expected_volatility: float = 0.0
    sharpe_ratio: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class PortfolioOptimizer(ABC):
    """Abstract base class for portfolio optimizers.

    Implementations should take expected returns and covariance matrix
    as inputs and produce optimal portfolio weights.
    """

    @abstractmethod
    def optimize(
        self,
        expected_returns: dict[str, float],
        covariance: dict[str, dict[str, float]],
        constraints: dict[str, Any] | None = None,
    ) -> OptimizationResult:
        """Optimize portfolio weights.

        Args:
            expected_returns: Dict of asset_id -> expected return
            covariance: Dict of asset_id -> {asset_id -> covariance}
            constraints: Optional constraints (max_weight, min_weight, etc.)

        Returns:
            OptimizationResult with optimal weights
        """

    def _to_arrays(
        self,
        expected_returns: dict[str, float],
        covariance: dict[str, dict[str, float]],
    ) -> tuple[list[str], np.ndarray, np.ndarray]:
        """Convert dicts to numpy arrays for optimization."""
        assets = sorted(expected_returns.keys())
        n = len(assets)

        mu = np.array([expected_returns[a] for a in assets])
        sigma = np.zeros((n, n))

        for i, a in enumerate(assets):
            for j, b in enumerate(assets):
                sigma[i, j] = covariance.get(a, {}).get(b, 0.0)

        return assets, mu, sigma
