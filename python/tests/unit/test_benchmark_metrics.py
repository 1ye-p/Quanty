"""Tests for benchmark return wiring in BacktestEngine."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import numpy as np
import polars as pl
import pytest

from cquant.backtest_vector.engine import BacktestSpec, VectorBacktestEngine
from cquant.backtest_vector.strategy import Strategy, StrategyContext


class _EmptyStrategy(Strategy):
    @property
    def strategy_id(self) -> str:
        return "empty"

    def generate_signals(self, ctx: StrategyContext) -> pl.DataFrame:
        return pl.DataFrame(
            schema={"asset_id": pl.Utf8, "signal_date": pl.Date,
                    "direction": pl.Utf8, "strength": pl.Float64, "confidence": pl.Float64}
        )


class _BuyAndHoldStrategy(Strategy):
    """Always buys the first available asset with full strength."""

    def __init__(self, asset_id: str) -> None:
        self._asset_id = asset_id

    @property
    def strategy_id(self) -> str:
        return "buy_and_hold"

    def generate_signals(self, ctx: StrategyContext) -> pl.DataFrame:
        return pl.DataFrame({
            "asset_id": [self._asset_id],
            "signal_date": [ctx.as_of_date],
            "direction": ["long"],
            "strength": [1.0],
            "confidence": [1.0],
        })


def _make_prices(n_days: int = 50) -> pl.DataFrame:
    rng = np.random.default_rng(42)
    dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(n_days)]
    assets = ["SSE:600036", "SSE:000001", "BM:CSI300"]
    rows = []
    price = {a: 100.0 for a in assets}
    for d in dates:
        for a in assets:
            price[a] *= 1 + rng.normal(0.0003, 0.01)
            rows.append({
                "asset_id": a, "trade_date": d,
                "open": price[a], "high": price[a] * 1.01, "low": price[a] * 0.99,
                "close": price[a], "volume": 1_000_000.0, "amount": price[a] * 1_000_000,
                "adj_factor": 1.0, "adj_close": price[a], "is_suspended": False,
            })
    return pl.DataFrame(rows)


class TestBenchmarkMetricsWired:
    def test_no_benchmark_gives_none_ir(self) -> None:
        engine = VectorBacktestEngine()
        prices = _make_prices(30)
        spec = BacktestSpec(
            strategy=_EmptyStrategy(),
            prices=prices,
            start_date=date(2025, 1, 10),
            end_date=date(2025, 1, 31),
            benchmark_asset_id="",
        )
        result = engine.run(spec)
        assert result.metrics.information_ratio is None

    def test_with_benchmark_gives_non_none_tracking_error(self) -> None:
        engine = VectorBacktestEngine()
        prices = _make_prices(50)
        spec = BacktestSpec(
            strategy=_BuyAndHoldStrategy("SSE:600036"),
            prices=prices,
            start_date=date(2025, 1, 10),
            end_date=date(2025, 2, 15),
            benchmark_asset_id="BM:CSI300",
        )
        result = engine.run(spec)
        assert result.metrics.tracking_error is not None

    def test_with_nonexistent_benchmark_gracefully_degrades(self) -> None:
        engine = VectorBacktestEngine()
        prices = _make_prices(30)
        spec = BacktestSpec(
            strategy=_EmptyStrategy(),
            prices=prices,
            start_date=date(2025, 1, 10),
            end_date=date(2025, 1, 31),
            benchmark_asset_id="NONEXISTENT",
        )
        result = engine.run(spec)
        assert result.metrics.information_ratio is None
