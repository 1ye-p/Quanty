"""Tests for MarketNeutralStrategy."""
from __future__ import annotations

from datetime import date

import polars as pl
import pytest

from cquant.backtest_vector.strategies.market_neutral import MarketNeutralStrategy
from cquant.backtest_vector.strategy import StrategyContext


def _make_features(n: int = 10) -> pl.DataFrame:
    return pl.DataFrame({
        "asset_id": [f"A{i:02d}" for i in range(n)],
        "trade_date": [date(2025, 6, 1)] * n,
        "ret_20d": [float(i) / n for i in range(n)],
    })


def _ctx(features: pl.DataFrame) -> StrategyContext:
    return StrategyContext(
        as_of_date=date(2025, 6, 1),
        universe_id="test",
        features=features,
    )


class TestMarketNeutralStrategy:
    def test_strategy_id(self) -> None:
        strat = MarketNeutralStrategy("mn_test")
        assert strat.strategy_id == "mn_test"

    def test_has_both_long_and_short_signals(self) -> None:
        strat = MarketNeutralStrategy("mn_test", top_n=3, short_n=3)
        signals = strat.generate_signals(_ctx(_make_features(10)))
        directions = set(signals["direction"].to_list())
        assert "long" in directions
        assert "short" in directions

    def test_correct_number_of_longs_and_shorts(self) -> None:
        strat = MarketNeutralStrategy("mn_test", top_n=3, short_n=2)
        signals = strat.generate_signals(_ctx(_make_features(10)))
        assert signals.filter(pl.col("direction") == "long").height == 3
        assert signals.filter(pl.col("direction") == "short").height == 2

    def test_longs_are_top_factor_assets(self) -> None:
        strat = MarketNeutralStrategy("mn_test", top_n=3, short_n=3)
        signals = strat.generate_signals(_ctx(_make_features(10)))
        long_assets = set(signals.filter(pl.col("direction") == "long")["asset_id"].to_list())
        assert "A09" in long_assets

    def test_shorts_are_bottom_factor_assets(self) -> None:
        strat = MarketNeutralStrategy("mn_test", top_n=3, short_n=3)
        signals = strat.generate_signals(_ctx(_make_features(10)))
        short_assets = set(signals.filter(pl.col("direction") == "short")["asset_id"].to_list())
        assert "A00" in short_assets

    def test_strength_is_positive(self) -> None:
        strat = MarketNeutralStrategy("mn_test", top_n=3, short_n=3)
        signals = strat.generate_signals(_ctx(_make_features(10)))
        assert all(s > 0 for s in signals["strength"].to_list())

    def test_returns_empty_without_features(self) -> None:
        strat = MarketNeutralStrategy("mn_test")
        ctx = StrategyContext(as_of_date=date(2025, 6, 1), universe_id="test")
        signals = strat.generate_signals(ctx)
        assert signals.is_empty()
