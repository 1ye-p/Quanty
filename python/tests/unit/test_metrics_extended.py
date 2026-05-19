"""Tests for extended backtest metrics: Sortino, VaR, CVaR, Beta."""
import numpy as np
import polars as pl
import pytest
from cquant.backtest_vector.metrics import compute_metrics, BacktestMetrics


def _constant_returns(r: float, n: int = 252) -> pl.Series:
    return pl.Series("daily_return", [r] * n)


def _random_returns(seed: int = 42, n: int = 1000) -> pl.Series:
    rng = np.random.default_rng(seed)
    rets = rng.normal(0.0005, 0.015, n)
    return pl.Series("daily_return", rets.tolist())


class TestSortinoRatio:
    def test_sortino_positive_for_positive_returns(self):
        m = compute_metrics(_constant_returns(0.001))
        assert m.sortino_ratio > 0

    def test_sortino_higher_than_sharpe_when_no_downside(self):
        m = compute_metrics(_constant_returns(0.001))
        assert m.sortino_ratio > m.sharpe_ratio

    def test_sortino_with_mixed_returns(self):
        rets = pl.Series("daily_return", [0.01, -0.02, 0.015, -0.005, 0.008] * 50)
        m = compute_metrics(rets)
        assert isinstance(m.sortino_ratio, float)
        assert m.sortino_ratio != 0.0


class TestVaRCVaR:
    def test_var_is_negative(self):
        m = compute_metrics(_random_returns())
        assert m.var_95 < 0

    def test_cvar_worse_than_var(self):
        m = compute_metrics(_random_returns())
        assert m.cvar_95 <= m.var_95

    def test_var_for_constant_returns(self):
        m = compute_metrics(_constant_returns(0.001))
        assert m.var_95 == pytest.approx(0.001, abs=1e-6)


class TestBeta:
    def test_beta_with_benchmark(self):
        rng = np.random.default_rng(42)
        market = rng.normal(0.0003, 0.01, 252)
        stock = 0.0001 + 1.5 * market + rng.normal(0, 0.005, 252)
        m = compute_metrics(
            pl.Series("daily_return", stock.tolist()),
            benchmark_returns=pl.Series("benchmark", market.tolist()),
        )
        assert m.beta is not None
        assert 1.0 < m.beta < 2.0

    def test_beta_none_without_benchmark(self):
        m = compute_metrics(_random_returns())
        assert m.beta is None


class TestTotalTrades:
    def test_total_trades_separate_from_trading_days(self):
        m = compute_metrics(_random_returns(), total_fills=42)
        assert m.total_trades == 42
        assert m.trading_days == 1000
