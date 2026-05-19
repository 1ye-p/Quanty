"""Tests for strategy combination framework."""
import polars as pl
import pytest
from datetime import date
from cquant.backtest_vector.strategy import Strategy, StrategyContext
from cquant.backtest_vector.strategies.combo import CompositeStrategy


class _FixedStrategy(Strategy):
    """Test strategy that returns fixed signals."""
    def __init__(self, sid: str, assets: list[str], strengths: list[float]):
        self._sid = sid
        self._assets = assets
        self._strengths = strengths

    @property
    def strategy_id(self) -> str:
        return self._sid

    def generate_signals(self, ctx: StrategyContext) -> pl.DataFrame:
        return pl.DataFrame({
            "asset_id": self._assets,
            "signal_date": [ctx.as_of_date] * len(self._assets),
            "direction": ["long"] * len(self._assets),
            "strength": self._strengths,
            "confidence": [1.0] * len(self._assets),
        })


def _make_ctx() -> StrategyContext:
    return StrategyContext(as_of_date=date(2025, 6, 1), universe_id="test")


class TestCompositeStrategy:
    def test_name(self):
        s1 = _FixedStrategy("s1", ["A"], [1.0])
        combo = CompositeStrategy(strategy_id="combo", strategies=[s1])
        assert combo.strategy_id == "combo"

    def test_single_strategy_passthrough(self):
        s1 = _FixedStrategy("s1", ["A", "B"], [0.8, 0.6])
        combo = CompositeStrategy(strategy_id="combo", strategies=[s1])
        signals = combo.generate_signals(_make_ctx())
        assert set(signals["asset_id"].to_list()) == {"A", "B"}

    def test_equal_weight_combination(self):
        s1 = _FixedStrategy("s1", ["A", "B"], [1.0, 0.5])
        s2 = _FixedStrategy("s2", ["A", "C"], [0.6, 0.8])
        combo = CompositeStrategy(
            strategy_id="combo",
            strategies=[s1, s2],
            method="equal_weight",
        )
        signals = combo.generate_signals(_make_ctx())
        # A appears in both, should be combined
        a_row = signals.filter(pl.col("asset_id") == "A")
        assert not a_row.is_empty()

    def test_custom_weights(self):
        s1 = _FixedStrategy("s1", ["A"], [1.0])
        s2 = _FixedStrategy("s2", ["A"], [1.0])
        combo = CompositeStrategy(
            strategy_id="combo",
            strategies=[s1, s2],
            method="custom",
            strategy_weights={"s1": 0.7, "s2": 0.3},
        )
        signals = combo.generate_signals(_make_ctx())
        a_strength = signals.filter(pl.col("asset_id") == "A")["strength"].to_list()[0]
        assert a_strength == pytest.approx(0.7 * 1.0 + 0.3 * 1.0)

    def test_empty_strategies_returns_empty(self):
        combo = CompositeStrategy(strategy_id="combo", strategies=[])
        signals = combo.generate_signals(_make_ctx())
        assert len(signals) == 0
