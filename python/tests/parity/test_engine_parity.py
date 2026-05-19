"""Framework for vector-engine ↔ event-engine parity tests.

Current status: the EventBacktestEngine delegates to VectorBacktestEngine when
the Rust wheel is not built, so both results will be identical by construction.

TODO: replace the fallback assertion with strict numerical parity once the Rust
event engine is compiled and routed through EventBacktestEngine.run().
"""

from __future__ import annotations

from decimal import Decimal

import polars as pl
import pytest

from cquant.backtest_event import BacktestEventSpec, EventBacktestEngine
from cquant.backtest_vector import BacktestSpec, VectorBacktestEngine
from cquant.backtest_vector.strategy import Strategy, StrategyContext
from cquant.core.enums import SignalDirection


class _LongOnlyStrategy(Strategy):
    """Minimal strategy: always go long on the first available asset."""

    @property
    def strategy_id(self) -> str:
        return "parity-test-long-only"

    def generate_signals(self, ctx: StrategyContext) -> pl.DataFrame:
        prices = ctx.prices
        if prices is None or prices.is_empty():
            return pl.DataFrame(schema={"asset_id": pl.Utf8, "signal_date": pl.Date,
                                        "direction": pl.Utf8, "strength": pl.Float64,
                                        "confidence": pl.Float64, "strategy_id": pl.Utf8})
        asset_id = prices.filter(pl.col("trade_date") == ctx.as_of_date)["asset_id"].head(1).to_list()
        if not asset_id:
            return pl.DataFrame(schema={"asset_id": pl.Utf8, "signal_date": pl.Date,
                                        "direction": pl.Utf8, "strength": pl.Float64,
                                        "confidence": pl.Float64, "strategy_id": pl.Utf8})
        return pl.DataFrame([{
            "asset_id": asset_id[0],
            "signal_date": ctx.as_of_date,
            "direction": SignalDirection.LONG.value,
            "strength": 1.0,
            "confidence": 1.0,
            "strategy_id": self.strategy_id,
        }])


def test_event_engine_fallback_parity(sample_prices: pl.DataFrame) -> None:
    """When Rust is not available, EventBacktestEngine must match VectorBacktestEngine exactly."""
    strategy = _LongOnlyStrategy()
    start = sample_prices["trade_date"].min()
    end = sample_prices["trade_date"].max()

    v_spec = BacktestSpec(strategy=strategy, prices=sample_prices,
                          start_date=start, end_date=end, initial_cash=Decimal("1000000"))
    e_spec = BacktestEventSpec(strategy=strategy, prices=sample_prices,
                               start_date=start, end_date=end, initial_cash=Decimal("1000000"))

    v_result = VectorBacktestEngine().run(v_spec)
    e_result = EventBacktestEngine().run(e_spec)

    assert v_result.error is None, f"Vector engine error: {v_result.error}"
    assert e_result.error is None, f"Event engine error: {e_result.error}"

    # Both engines should produce identical portfolio_returns when Rust is not available
    v_sorted = v_result.portfolio_returns.sort("trade_date")
    e_sorted = e_result.portfolio_returns.sort("trade_date")
    assert v_sorted.equals(e_sorted), (
        "Vector/Event engine portfolio_returns mismatch in fallback mode. "
        "This is unexpected — both should delegate to the same VectorBacktestEngine."
    )


def test_event_engine_available_attribute() -> None:
    """EventBacktestEngine.available reflects whether Rust wheel is loaded."""
    engine = EventBacktestEngine()
    # Whether True or False, .available must be a bool
    assert isinstance(engine.available, bool)
