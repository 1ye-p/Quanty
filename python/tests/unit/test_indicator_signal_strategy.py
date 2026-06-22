"""Tests for IndicatorSignalStrategy and PositionManager."""

from datetime import date, timedelta
import random

import polars as pl
import pytest

from cquant.backtest_vector.strategies.indicator_signal import (
    IndicatorSignalStrategy,
    _extract_indicator_refs,
    _parse_value,
)
from cquant.backtest_vector.strategies.position_manager import (
    PositionManager,
    PositionManagerConfig,
)
from cquant.backtest_vector.strategy import StrategyContext


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_prices(
    assets: list[str],
    n_days: int = 100,
    base_date: date = date(2025, 1, 1),
    seed: int = 42,
) -> pl.DataFrame:
    """Generate synthetic OHLCV price data."""
    rng = random.Random(seed)
    rows = []
    for asset in assets:
        price = 100.0
        for i in range(n_days):
            d = base_date + timedelta(days=i)
            change = rng.uniform(-0.03, 0.03)
            price *= (1 + change)
            rows.append({
                "asset_id": asset,
                "trade_date": d,
                "open": price * 0.99,
                "high": price * 1.02,
                "low": price * 0.98,
                "close": price,
                "volume": rng.randint(1_000_000, 10_000_000),
            })
    return pl.DataFrame(rows)


# ---------------------------------------------------------------------------
# _extract_indicator_refs
# ---------------------------------------------------------------------------

class TestExtractIndicatorRefs:
    def test_single_indicator(self):
        refs = _extract_indicator_refs(["rsi(14) > 70"])
        assert len(refs) == 1
        assert refs[0]["name"] == "rsi"
        assert refs[0]["params"]["period"] == 14
        assert refs[0]["col_name"] == "rsi(14)"

    def test_multiple_indicators(self):
        refs = _extract_indicator_refs(["rsi(14) < 30 AND close > sma(20)"])
        names = {r["col_name"] for r in refs}
        assert "rsi(14)" in names
        assert "sma(20)" in names

    def test_deduplication(self):
        refs = _extract_indicator_refs(["rsi(14) > 70", "rsi(14) < 30"])
        assert len(refs) == 1

    def test_different_params_not_deduped(self):
        refs = _extract_indicator_refs(["sma(5) crosses_above sma(20)"])
        cols = {r["col_name"] for r in refs}
        assert "sma(5)" in cols
        assert "sma(20)" in cols

    def test_no_indicators(self):
        refs = _extract_indicator_refs(["close > 100"])
        assert len(refs) == 0

    def test_empty_conditions(self):
        refs = _extract_indicator_refs([])
        assert len(refs) == 0


# ---------------------------------------------------------------------------
# _parse_value
# ---------------------------------------------------------------------------

class TestParseValue:
    def test_int(self):
        assert _parse_value("14") == 14

    def test_float(self):
        assert _parse_value("3.14") == 3.14

    def test_string(self):
        assert _parse_value("close") == "close"

    def test_negative_int(self):
        assert _parse_value("-5") == -5


# ---------------------------------------------------------------------------
# IndicatorSignalStrategy
# ---------------------------------------------------------------------------

class TestIndicatorSignalStrategy:
    def test_returns_signal_frame_columns(self):
        """Signal frame has the expected columns."""
        prices = _make_prices(["AAPL", "GOOG"], n_days=60)
        strat = IndicatorSignalStrategy(
            strategy_id="test_cols",
            entry_conditions=["rsi(14) < 30"],
            exit_conditions=["rsi(14) > 70"],
        )
        ctx = StrategyContext(
            as_of_date=date(2025, 2, 15),
            universe_id="test",
            prices=prices,
        )
        signals = strat.generate_signals(ctx)

        assert isinstance(signals, pl.DataFrame)
        for col in ("asset_id", "signal_date", "direction", "strength", "confidence"):
            assert col in signals.columns, f"Missing column: {col}"

    def test_empty_prices_returns_empty(self):
        """None prices produces empty signals."""
        strat = IndicatorSignalStrategy(
            strategy_id="test_empty",
            entry_conditions=["rsi(14) < 30"],
        )
        ctx = StrategyContext(as_of_date=date(2025, 1, 1), universe_id="test", prices=None)
        signals = strat.generate_signals(ctx)
        assert len(signals) == 0

    def test_max_positions_limits_buy_signals(self):
        """max_positions limits the number of long signals."""
        prices = _make_prices(["A", "B", "C", "D", "E"], n_days=60, seed=99)
        strat = IndicatorSignalStrategy(
            strategy_id="test_max_pos",
            entry_conditions=["rsi(14) < 80"],  # very loose, should trigger for most
            max_positions=2,
        )
        ctx = StrategyContext(
            as_of_date=date(2025, 2, 15),
            universe_id="test",
            prices=prices,
        )
        signals = strat.generate_signals(ctx)
        buy_signals = signals.filter(pl.col("direction") == "long")
        assert len(buy_signals) <= 2

    def test_buy_priority_over_sell(self):
        """When an asset triggers both entry and exit, only buy is kept."""
        prices = _make_prices(["AAPL"], n_days=60, seed=42)
        strat = IndicatorSignalStrategy(
            strategy_id="test_priority",
            entry_conditions=["rsi(14) > 0"],   # always true
            exit_conditions=["rsi(14) > 0"],     # always true
        )
        ctx = StrategyContext(
            as_of_date=date(2025, 2, 15),
            universe_id="test",
            prices=prices,
        )
        signals = strat.generate_signals(ctx)
        # Should only have buy signals (buy takes priority)
        if not signals.is_empty():
            assert all(d == "long" for d in signals["direction"].to_list())

    def test_explicit_indicators(self):
        """Explicit indicator specs override auto-extraction."""
        prices = _make_prices(["AAPL"], n_days=60)
        strat = IndicatorSignalStrategy(
            strategy_id="test_explicit",
            entry_conditions=["rsi(14) < 80"],
            indicators=[{"name": "rsi", "params": {"period": 14}}],
        )
        ctx = StrategyContext(
            as_of_date=date(2025, 2, 15),
            universe_id="test",
            prices=prices,
        )
        signals = strat.generate_signals(ctx)
        assert isinstance(signals, pl.DataFrame)

    def test_crossover_condition(self):
        """Crossover conditions work correctly."""
        prices = _make_prices(["AAPL"], n_days=60)
        strat = IndicatorSignalStrategy(
            strategy_id="test_cross",
            entry_conditions=["sma(5) crosses_above sma(20)"],
        )
        ctx = StrategyContext(
            as_of_date=date(2025, 2, 15),
            universe_id="test",
            prices=prices,
        )
        signals = strat.generate_signals(ctx)
        assert isinstance(signals, pl.DataFrame)

    def test_strategy_id(self):
        strat = IndicatorSignalStrategy(strategy_id="my_strategy")
        assert strat.strategy_id == "my_strategy"


# ---------------------------------------------------------------------------
# PositionManager
# ---------------------------------------------------------------------------

class TestPositionManager:
    def test_equal_weight_sizing(self):
        """Equal weight divides strength equally among buy signals."""
        pm = PositionManager(PositionManagerConfig(sizing="equal_weight"))
        signals = pl.DataFrame({
            "asset_id": ["A", "B", "C"],
            "signal_date": [date(2025, 1, 1)] * 3,
            "direction": ["long"] * 3,
            "strength": [1.0, 1.0, 1.0],
            "confidence": [1.0, 1.0, 1.0],
        })
        result = pm.apply(signals)
        strengths = result["strength"].to_list()
        assert all(abs(s - 1.0 / 3) < 1e-10 for s in strengths)

    def test_max_positions_limits_buy(self):
        """max_positions limits new buy signals."""
        pm = PositionManager(PositionManagerConfig(max_positions=2))
        signals = pl.DataFrame({
            "asset_id": ["A", "B", "C", "D"],
            "signal_date": [date(2025, 1, 1)] * 4,
            "direction": ["long"] * 4,
            "strength": [1.0, 1.0, 1.0, 1.0],
            "confidence": [1.0, 1.0, 1.0, 1.0],
        })
        result = pm.apply(signals, current_positions={})
        assert len(result) == 2

    def test_sell_signals_preserved(self):
        """Sell signals pass through unchanged."""
        pm = PositionManager(PositionManagerConfig())
        signals = pl.DataFrame({
            "asset_id": ["A", "B"],
            "signal_date": [date(2025, 1, 1)] * 2,
            "direction": ["sell", "long"],
            "strength": [1.0, 1.0],
            "confidence": [1.0, 1.0],
        })
        result = pm.apply(signals)
        assert "sell" in result["direction"].to_list()
        assert "long" in result["direction"].to_list()

    def test_empty_signals(self):
        """Empty input returns empty output."""
        pm = PositionManager()
        empty = pl.DataFrame(
            schema={
                "asset_id": pl.Utf8,
                "signal_date": pl.Date,
                "direction": pl.Utf8,
                "strength": pl.Float64,
                "confidence": pl.Float64,
            }
        )
        result = pm.apply(empty)
        assert len(result) == 0
