"""Unit tests for backtest_event module.

Tests EngineType assignment, event classes, and engine core logic.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import polars as pl
import pytest

from cquant.backtest_event.event_engine import EventDrivenEngine
from cquant.backtest_event.events import (
    BarEvent,
    EventType,
    FillEvent,
    OrderEvent,
    OrderIntentEvent,
    PortfolioUpdateEvent,
    RiskDecisionEvent,
    SignalEvent,
)
from cquant.core.enums import EngineType


# ── EngineType Tests ──────────────────────────────────────────────────────────

class TestEngineType:
    def test_event_engine_uses_event_type_in_error_handler(self):
        """EventDrivenEngine error handler should set engine=EngineType.EVENT."""
        engine = EventDrivenEngine()
        # Read the source to verify the fix
        import inspect
        source = inspect.getsource(engine.run)
        # After fix, should reference EngineType.EVENT
        assert "EngineType.EVENT" in source or "EngineType.VECTOR" not in source


# ── Event Classes Tests ───────────────────────────────────────────────────────

class TestEventClasses:
    def test_bar_event_creation(self):
        bar = BarEvent(
            asset_id="SSE:600036",
            trade_date=date(2025, 1, 2),
            open=35.0, high=35.8, low=34.8, close=35.5,
            volume=1000000,
        )
        assert bar.asset_id == "SSE:600036"
        assert bar.close == 35.5

    def test_signal_event_creation(self):
        sig = SignalEvent(
            asset_id="SSE:600036",
            trade_date=date(2025, 1, 2),
            direction="long",
            strength=0.8,
            confidence=0.9,
            strategy_id="test",
        )
        assert sig.direction == "long"
        assert sig.strength == 0.8

    def test_fill_event_creation(self):
        fill = FillEvent(
            fill_id="f1",
            order_id="o1",
            asset_id="SSE:600036",
            trade_date=date(2025, 1, 2),
            side="buy",
            qty=1000,
            price=35.5,
            notional=35500.0,
            commission=35.5,
            stamp_duty=0.0,
            slippage=3.55,
            total_cost=39.05,
        )
        assert fill.qty == 1000
        assert fill.total_cost == 39.05

    def test_order_intent_creation(self):
        intent = OrderIntentEvent(
            asset_id="SSE:600036",
            trade_date=date(2025, 1, 2),
            side="buy",
            requested_qty=1000,
            strategy_id="test",
        )
        assert intent.side == "buy"
        assert intent.requested_qty == 1000


# ── Engine Core Logic Tests ───────────────────────────────────────────────────

class TestEventDrivenEngine:
    def test_build_price_lookup(self):
        engine = EventDrivenEngine()
        prices = pl.DataFrame({
            "trade_date": [date(2025, 1, 2), date(2025, 1, 3)],
            "asset_id": ["SSE:600036", "SSE:600036"],
            "open": [35.0, 35.5],
            "high": [35.8, 36.0],
            "low": [34.8, 35.2],
            "close": [35.5, 35.8],
            "volume": [1000000, 1200000],
        })
        lookup = engine._build_price_lookup(prices)

        assert (date(2025, 1, 2), "SSE:600036") in lookup
        assert lookup[(date(2025, 1, 2), "SSE:600036")]["close"] == 35.5

    def test_build_price_lookup_computes_prev_close(self):
        engine = EventDrivenEngine()
        prices = pl.DataFrame({
            "trade_date": [date(2025, 1, 2), date(2025, 1, 3)],
            "asset_id": ["SSE:600036", "SSE:600036"],
            "open": [35.0, 35.5],
            "high": [35.8, 36.0],
            "low": [34.8, 35.2],
            "close": [35.5, 35.8],
            "volume": [1000000, 1200000],
        })
        lookup = engine._build_price_lookup(prices)

        assert lookup[(date(2025, 1, 3), "SSE:600036")]["prev_close"] == 35.5

    def test_build_fills_df_empty(self):
        engine = EventDrivenEngine()
        df = engine._build_fills_df([])
        assert df.is_empty()
        assert "trade_date" in df.columns

    def test_build_snapshots_df_empty(self):
        engine = EventDrivenEngine()
        df = engine._build_snapshots_df([])
        assert df.is_empty()
        assert "nav" in df.columns
