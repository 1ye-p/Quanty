"""Unit tests for live execution engine components.

Tests:
- SignalConverter: signal-to-order conversion
- StrategyLoader: strategy loading from config
- ExecutionPersister: execution result persistence
"""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import polars as pl
import pytest

from cquant.core.types import SignalFrame
from cquant.execution.broker import Order, OrderStatus
from cquant.execution.execution_persister import ExecutionPersister
from cquant.execution.signal_converter import SignalConverter


# ── SignalConverter Tests ─────────────────────────────────────────────────


class TestSignalConverter:
    """Test SignalConverter signal-to-order conversion."""

    def _make_signals(self, assets: list[str], strengths: list[float]) -> SignalFrame:
        """Helper to create a SignalFrame."""
        return pl.DataFrame({
            "asset_id": assets,
            "signal_date": [date(2025, 6, 1)] * len(assets),
            "direction": ["buy"] * len(assets),
            "strength": strengths,
            "confidence": [0.8] * len(assets),
        })

    def test_convert_empty_signals(self):
        """Empty signals should produce no orders."""
        converter = SignalConverter()
        signals = pl.DataFrame({
            "asset_id": [],
            "signal_date": [],
            "direction": [],
            "strength": [],
            "confidence": [],
        }).cast({"asset_id": pl.Utf8, "signal_date": pl.Date, "direction": pl.Utf8, "strength": pl.Float64, "confidence": pl.Float64})

        orders = converter.convert(signals, {}, 1_000_000, {})
        assert orders == []

    def test_convert_below_min_strength(self):
        """Signals below min_strength should be filtered out."""
        converter = SignalConverter(min_strength=0.5)
        signals = self._make_signals(["SSE:600036", "SSE:000001"], [0.1, 0.3])

        orders = converter.convert(signals, {}, 1_000_000, {"SSE:600036": 50.0, "SSE:000001": 10.0})
        assert orders == []

    def test_convert_generates_buy_orders(self):
        """Positive signals should generate buy orders."""
        converter = SignalConverter(lot_size=100, min_strength=0.01)
        signals = self._make_signals(["SSE:600036"], [0.8])

        orders = converter.convert(
            signals, {}, 1_000_000, {"SSE:600036": 50.0}
        )
        assert len(orders) == 1
        assert orders[0].side == "buy"
        assert orders[0].asset_id == "SSE:600036"
        assert orders[0].qty > 0
        assert orders[0].qty % 100 == 0  # Rounded to lot

    def test_convert_generates_sell_for_exits(self):
        """Assets in current positions but not in signals should generate sell orders."""
        converter = SignalConverter(lot_size=100, min_strength=0.01)
        signals = self._make_signals(["SSE:600036"], [0.8])

        current_positions = {"SSE:600036": 1000, "SSE:000001": 500}
        orders = converter.convert(
            signals, current_positions, 1_000_000,
            {"SSE:600036": 50.0, "SSE:000001": 10.0}
        )

        # Should have a sell order for SSE:000001 (excluded from signals)
        sell_orders = [o for o in orders if o.side == "sell"]
        assert len(sell_orders) == 1
        assert sell_orders[0].asset_id == "SSE:000001"
        assert sell_orders[0].qty == 500

    def test_convert_lot_size_rounding(self):
        """Orders should be rounded to lot size."""
        converter = SignalConverter(lot_size=100, min_strength=0.01)
        signals = self._make_signals(["SSE:600036"], [0.5])

        orders = converter.convert(
            signals, {}, 100_000, {"SSE:600036": 50.0}
        )
        for order in orders:
            assert order.qty % 100 == 0

    def test_convert_max_position_pct(self):
        """Single position should not exceed max_position_pct."""
        converter = SignalConverter(lot_size=100, min_strength=0.01, max_position_pct=0.05)
        signals = self._make_signals(["SSE:600036"], [0.8])

        nav = 1_000_000
        price = 50.0
        orders = converter.convert(signals, {}, nav, {"SSE:600036": price})

        if orders:
            max_qty = int(nav * 0.05 / price)
            max_qty = (max_qty // 100) * 100
            assert orders[0].qty <= max_qty

    def test_convert_no_price_skipped(self):
        """Assets with no price should be skipped."""
        converter = SignalConverter(lot_size=100, min_strength=0.01)
        signals = self._make_signals(["SSE:600036"], [0.8])

        orders = converter.convert(signals, {}, 1_000_000, {})
        assert orders == []

    def test_convert_order_has_uuid(self):
        """Each order should have a unique order_id."""
        converter = SignalConverter(lot_size=100, min_strength=0.01)
        signals = self._make_signals(["SSE:600036", "SSE:000001"], [0.8, 0.6])

        orders = converter.convert(
            signals, {}, 1_000_000,
            {"SSE:600036": 50.0, "SSE:000001": 10.0}
        )
        order_ids = {o.order_id for o in orders}
        assert len(order_ids) == len(orders)  # All unique

    def test_convert_market_order_type(self):
        """All orders should be market type."""
        converter = SignalConverter(lot_size=100, min_strength=0.01)
        signals = self._make_signals(["SSE:600036"], [0.8])

        orders = converter.convert(
            signals, {}, 1_000_000, {"SSE:600036": 50.0}
        )
        for order in orders:
            assert order.order_type == "market"


# ── ExecutionPersister Tests ─────────────────────────────────────────────


class TestExecutionPersister:
    """Test ExecutionPersister persistence logic."""

    def test_persist_order(self):
        """Should persist an order and return execution_id."""
        mock_catalog = MagicMock()
        persister = ExecutionPersister(mock_catalog)

        order = Order(
            order_id="test-001",
            asset_id="SSE:600036",
            side="buy",
            qty=1000,
            filled_qty=1000,
            filled_price=50.0,
            commission=5.0,
            stamp_duty=0.0,
            slippage=1.0,
            total_cost=6.0,
            status=OrderStatus.FILLED,
        )

        execution_id = persister.persist_order("live_001", "my_strategy", order)

        assert execution_id  # Non-empty string
        assert mock_catalog.execute.call_count >= 2  # DDL + INSERT

    def test_persist_batch(self):
        """Should persist multiple orders."""
        mock_catalog = MagicMock()
        persister = ExecutionPersister(mock_catalog)

        orders = [
            Order(
                order_id=f"test-{i}",
                asset_id=f"SSE:6000{i}",
                side="buy",
                qty=1000,
                filled_qty=1000,
                filled_price=50.0,
                status=OrderStatus.FILLED,
            )
            for i in range(3)
        ]

        ids = persister.persist_batch("live_001", "my_strategy", orders)
        assert len(ids) == 3
        assert len(set(ids)) == 3  # All unique

    def test_get_executions_empty(self):
        """Should return empty list when no executions exist."""
        mock_catalog = MagicMock()

        # First call: _ensure_schema (execute), then get_executions queries
        # Count query returns 0, data query returns empty
        def side_effect(sql, params=None):
            if "COUNT(*)" in sql:
                return pl.DataFrame({"cnt": [0]})
            return pl.DataFrame()

        mock_catalog.query.side_effect = side_effect
        persister = ExecutionPersister(mock_catalog)

        result = persister.get_executions("live_001")
        assert result["total"] == 0
        assert result["items"] == []


# ── StrategyLoader Tests ─────────────────────────────────────────────────


class TestStrategyLoader:
    """Test StrategyLoader class resolution."""

    def test_get_strategy_class_static_topn(self):
        """Should resolve StaticTopN strategy."""
        from cquant.execution.strategy_loader import get_strategy_class

        cls = get_strategy_class("StaticTopN")
        assert cls.__name__ == "StaticTopNStrategy"

    def test_get_strategy_class_unknown_raises(self):
        """Unknown strategy type should raise ValueError."""
        from cquant.execution.strategy_loader import get_strategy_class

        with pytest.raises(ValueError, match="Unknown strategy type"):
            get_strategy_class("NonExistentStrategy")

    def test_load_no_backtest_run_raises(self):
        """Should raise ValueError when no backtest run found."""
        from cquant.execution.strategy_loader import StrategyLoader

        mock_catalog = MagicMock()
        mock_catalog.query.return_value = pl.DataFrame()
        loader = StrategyLoader(mock_catalog)

        with pytest.raises(ValueError, match="No completed backtest run"):
            loader.load("nonexistent_strategy")


# ── Integration: LiveExecutor.run_once ────────────────────────────────────


class TestLiveExecutorRunOnce:
    """Test LiveExecutor.run_once logic."""

    def test_run_once_not_trading_day(self):
        """Should skip execution on non-trading days."""
        from cquant.execution.live_executor import LiveExecutor

        mock_catalog = MagicMock()
        mock_catalog.query.return_value = pl.DataFrame({"cnt": [0]})

        executor = LiveExecutor(mock_catalog)

        with patch.object(executor, '_is_trading_day', return_value=False):
            summary = executor.run_once()

        assert summary["executed"] == 0
        assert summary["skipped"] >= 1

    def test_run_once_no_active_strategies(self):
        """Should return empty summary when no active strategies."""
        from cquant.execution.live_executor import LiveExecutor

        mock_catalog = MagicMock()

        # Return empty DataFrame for all queries (active strategies is empty)
        def side_effect(sql, params=None):
            if "COUNT(*)" in sql:
                return pl.DataFrame({"cnt": [0]})
            # For active strategies query - return empty with correct schema
            if "meta_live_strategies" in sql and "active" in sql:
                return pl.DataFrame({
                    "live_id": [],
                    "strategy_id": [],
                    "backtest_run_id": [],
                    "initial_cash": [],
                    "risk_mode": [],
                }).cast({
                    "live_id": pl.Utf8,
                    "strategy_id": pl.Utf8,
                    "backtest_run_id": pl.Utf8,
                    "initial_cash": pl.Float64,
                    "risk_mode": pl.Utf8,
                })
            return pl.DataFrame()

        mock_catalog.query.side_effect = side_effect
        executor = LiveExecutor(mock_catalog)

        with patch.object(executor, '_is_trading_day', return_value=True):
            summary = executor.run_once()

        assert summary["executed"] == 0
