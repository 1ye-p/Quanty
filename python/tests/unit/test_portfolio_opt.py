"""Unit tests for portfolio_opt module.

Tests mean-variance and risk parity optimizers.
"""

from __future__ import annotations

import numpy as np
import pytest

from cquant.portfolio_opt.base import OptimizationResult, PortfolioOptimizer
from cquant.portfolio_opt.mean_variance import MeanVarianceOptimizer
from cquant.portfolio_opt.risk_parity import RiskParityOptimizer


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _simple_returns() -> dict[str, float]:
    return {"A": 0.10, "B": 0.12, "C": 0.08}


def _simple_covariance() -> dict[str, dict[str, float]]:
    return {
        "A": {"A": 0.04, "B": 0.02, "C": 0.01},
        "B": {"A": 0.02, "B": 0.09, "C": 0.015},
        "C": {"A": 0.01, "B": 0.015, "C": 0.0225},
    }


# ── MeanVarianceOptimizer Tests ───────────────────────────────────────────────

class TestMeanVarianceOptimizer:
    def test_optimize_returns_result(self):
        optimizer = MeanVarianceOptimizer()
        result = optimizer.optimize(_simple_returns(), _simple_covariance())
        assert isinstance(result, OptimizationResult)
        assert len(result.weights) == 3

    def test_weights_sum_to_one(self):
        optimizer = MeanVarianceOptimizer()
        result = optimizer.optimize(_simple_returns(), _simple_covariance())
        total = sum(result.weights.values())
        assert abs(total - 1.0) < 1e-6

    def test_long_only_weights_non_negative(self):
        optimizer = MeanVarianceOptimizer(long_only=True)
        result = optimizer.optimize(_simple_returns(), _simple_covariance())
        for w in result.weights.values():
            assert w >= -1e-6

    def test_max_weight_constraint(self):
        optimizer = MeanVarianceOptimizer()
        result = optimizer.optimize(
            _simple_returns(),
            _simple_covariance(),
            constraints={"max_weight": 0.5},
        )
        for w in result.weights.values():
            assert w <= 0.5 + 1e-6

    def test_empty_returns(self):
        optimizer = MeanVarianceOptimizer()
        result = optimizer.optimize({}, {})
        assert result.weights == {}

    def test_sharpe_ratio_calculated(self):
        optimizer = MeanVarianceOptimizer()
        result = optimizer.optimize(_simple_returns(), _simple_covariance())
        assert result.sharpe_ratio != 0.0

    def test_metadata_contains_optimizer_name(self):
        optimizer = MeanVarianceOptimizer()
        result = optimizer.optimize(_simple_returns(), _simple_covariance())
        assert result.metadata["optimizer"] == "mean_variance"


# ── RiskParityOptimizer Tests ─────────────────────────────────────────────────

class TestRiskParityOptimizer:
    def test_optimize_returns_result(self):
        optimizer = RiskParityOptimizer()
        result = optimizer.optimize(_simple_returns(), _simple_covariance())
        assert isinstance(result, OptimizationResult)
        assert len(result.weights) == 3

    def test_weights_sum_to_one(self):
        optimizer = RiskParityOptimizer()
        result = optimizer.optimize(_simple_returns(), _simple_covariance())
        total = sum(result.weights.values())
        assert abs(total - 1.0) < 1e-6

    def test_weights_non_negative(self):
        optimizer = RiskParityOptimizer()
        result = optimizer.optimize(_simple_returns(), _simple_covariance())
        for w in result.weights.values():
            assert w >= -1e-6

    def test_empty_returns(self):
        optimizer = RiskParityOptimizer()
        result = optimizer.optimize({}, {})
        assert result.weights == {}


# ── Base Classes Tests ────────────────────────────────────────────────────────

class TestPortfolioOptimizerBase:
    def test_to_arrays_conversion(self):
        class TestOptimizer(PortfolioOptimizer):
            def optimize(self, expected_returns, covariance, constraints=None):
                assets, mu, sigma = self._to_arrays(expected_returns, covariance)
                return OptimizationResult(
                    weights={a: 1.0 / len(assets) for a in assets},
                    expected_return=float(mu.mean()),
                )

        opt = TestOptimizer()
        result = opt.optimize(_simple_returns(), _simple_covariance())
        assert len(result.weights) == 3


# ── CostAwareOptimizer Tests ──────────────────────────────────────────────────

class TestCostAwareOptimizer:
    def test_optimize_with_transaction_costs(self):
        from cquant.portfolio_opt.cost_aware import CostAwareOptimizer

        optimizer = CostAwareOptimizer(
            cost_rate=0.001,
            turnover_penalty=0.0005,
        )
        result = optimizer.optimize(
            _simple_returns(),
            _simple_covariance(),
            constraints={"current_weights": {"A": 0.3, "B": 0.4, "C": 0.3}},
        )
        assert isinstance(result, OptimizationResult)
        assert len(result.weights) == 3

    def test_low_turnover_with_existing_weights(self):
        """With high turnover penalty, optimal should be close to current."""
        from cquant.portfolio_opt.cost_aware import CostAwareOptimizer

        current = {"A": 0.5, "B": 0.3, "C": 0.2}
        optimizer = CostAwareOptimizer(
            cost_rate=0.001,
            turnover_penalty=0.1,
        )
        result = optimizer.optimize(
            _simple_returns(),
            _simple_covariance(),
            constraints={"current_weights": current},
        )
        turnover = sum(abs(result.weights.get(a, 0) - current[a]) for a in current)
        assert turnover < 0.5

    def test_metadata_contains_optimizer_name(self):
        from cquant.portfolio_opt.cost_aware import CostAwareOptimizer

        optimizer = CostAwareOptimizer()
        result = optimizer.optimize(_simple_returns(), _simple_covariance())
        assert result.metadata["optimizer"] == "cost_aware"
        assert "turnover" in result.metadata

    def test_empty_returns(self):
        from cquant.portfolio_opt.cost_aware import CostAwareOptimizer

        optimizer = CostAwareOptimizer()
        result = optimizer.optimize({}, {})
        assert result.weights == {}
