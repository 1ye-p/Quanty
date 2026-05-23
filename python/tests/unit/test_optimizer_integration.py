"""Tests for PortfolioOptimizer integration in BacktestSpec."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import numpy as np
import polars as pl
import pytest

from cquant.backtest_vector.engine import BacktestSpec, VectorBacktestEngine
from cquant.backtest_vector.strategy import Strategy, StrategyContext
from cquant.portfolio_opt.mean_variance import MeanVarianceOptimizer


class _TopNStrategy(Strategy):
    @property
    def strategy_id(self) -> str:
        return "top_n"

    def generate_signals(self, ctx: StrategyContext) -> pl.DataFrame:
        return pl.DataFrame({
            "asset_id": ["SSE:600036", "SSE:000001"],
            "signal_date": [ctx.as_of_date, ctx.as_of_date],
            "direction": ["long", "long"],
            "strength": [0.8, 0.6],
            "confidence": [1.0, 1.0],
        })


def _make_prices(n_days: int = 30) -> pl.DataFrame:
    rng = np.random.default_rng(42)
    dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(n_days)]
    rows = []
    prices = {"SSE:600036": 50.0, "SSE:000001": 30.0}
    for d in dates:
        for a, p in prices.items():
            p *= 1 + rng.normal(0.0005, 0.01)
            prices[a] = p
            rows.append({
                "asset_id": a, "trade_date": d,
                "open": p, "high": p * 1.01, "low": p * 0.99,
                "close": p, "volume": 1e6, "amount": p * 1e6,
                "adj_factor": 1.0, "adj_close": p, "is_suspended": False,
            })
    return pl.DataFrame(rows)


class TestBacktestSpecOptimizerField:
    def test_backtest_spec_accepts_optimizer(self) -> None:
        optimizer = MeanVarianceOptimizer()
        spec = BacktestSpec(
            strategy=_TopNStrategy(),
            prices=_make_prices(),
            start_date=date(2025, 1, 5),
            end_date=date(2025, 1, 20),
            optimizer=optimizer,
        )
        assert spec.optimizer is optimizer

    def test_backtest_spec_optimizer_defaults_to_none(self) -> None:
        spec = BacktestSpec(
            strategy=_TopNStrategy(),
            prices=_make_prices(),
            start_date=date(2025, 1, 5),
            end_date=date(2025, 1, 20),
        )
        assert spec.optimizer is None

    def test_backtest_with_optimizer_runs_without_error(self) -> None:
        engine = VectorBacktestEngine()
        spec = BacktestSpec(
            strategy=_TopNStrategy(),
            prices=_make_prices(30),
            start_date=date(2025, 1, 5),
            end_date=date(2025, 1, 20),
            optimizer=MeanVarianceOptimizer(),
        )
        result = engine.run(spec)
        assert result.error is None

    def test_backtest_without_optimizer_still_works(self) -> None:
        engine = VectorBacktestEngine()
        spec = BacktestSpec(
            strategy=_TopNStrategy(),
            prices=_make_prices(30),
            start_date=date(2025, 1, 5),
            end_date=date(2025, 1, 20),
        )
        result = engine.run(spec)
        assert result.error is None
