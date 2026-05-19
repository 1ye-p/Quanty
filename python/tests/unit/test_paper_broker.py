"""Unit tests for PaperBroker.

Tests order validation, execution, PnL calculation, and position management.
"""

from __future__ import annotations

import pytest

from cquant.execution.broker import Order, OrderStatus
from cquant.execution.paper_broker import PaperBroker


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def broker() -> PaperBroker:
    return PaperBroker(initial_cash=1_000_000)


@pytest.fixture
def funded_broker() -> PaperBroker:
    """Broker with prices set and enough cash."""
    b = PaperBroker(initial_cash=1_000_000)
    b.update_prices({"SSE:600036": 35.0, "SSE:601318": 50.0})
    return b


def _buy_order(asset_id: str = "SSE:600036", qty: int = 1000) -> Order:
    return Order(order_id="buy-1", asset_id=asset_id, side="buy", qty=qty)


def _sell_order(asset_id: str = "SSE:600036", qty: int = 1000) -> Order:
    return Order(order_id="sell-1", asset_id=asset_id, side="sell", qty=qty)


# ── Validation Tests ──────────────────────────────────────────────────────────

class TestOrderValidation:
    def test_negative_qty_rejected(self, broker: PaperBroker):
        order = Order(order_id="neg-1", asset_id="SSE:600036", side="buy", qty=-100)
        result = broker.submit_order(order)
        assert result.status == OrderStatus.REJECTED
        assert "Invalid qty" in result.reject_reason

    def test_zero_qty_rejected(self, broker: PaperBroker):
        order = Order(order_id="zero-1", asset_id="SSE:600036", side="buy", qty=0)
        result = broker.submit_order(order)
        assert result.status == OrderStatus.REJECTED
        assert "Invalid qty" in result.reject_reason

    def test_limit_order_rejected(self, broker: PaperBroker):
        order = Order(
            order_id="limit-1", asset_id="SSE:600036", side="buy", qty=100,
            order_type="limit", limit_price=35.0,
        )
        result = broker.submit_order(order)
        assert result.status == OrderStatus.REJECTED
        assert "market orders only" in result.reject_reason

    def test_invalid_side_rejected(self, broker: PaperBroker):
        order = Order(order_id="side-1", asset_id="SSE:600036", side="hold", qty=100)
        broker.update_prices({"SSE:600036": 35.0})
        result = broker.submit_order(order)
        assert result.status == OrderStatus.REJECTED
        assert "Invalid side" in result.reject_reason

    def test_no_price_rejected(self, broker: PaperBroker):
        order = _buy_order()
        result = broker.submit_order(order)
        assert result.status == OrderStatus.REJECTED
        assert "No price available" in result.reject_reason


# ── Buy Order Tests ───────────────────────────────────────────────────────────

class TestBuyOrder:
    def test_buy_fills_at_market_price(self, funded_broker: PaperBroker):
        result = funded_broker.submit_order(_buy_order())
        assert result.status == OrderStatus.FILLED
        assert result.filled_qty == 1000
        assert result.filled_price == 35.0

    def test_buy_deducts_cash(self, funded_broker: PaperBroker):
        funded_broker.submit_order(_buy_order())
        account = funded_broker.get_account()
        assert account.cash < 1_000_000
        # Cash should be reduced by notional + fees
        assert account.cash < 1_000_000 - 35_000

    def test_buy_creates_position(self, funded_broker: PaperBroker):
        funded_broker.submit_order(_buy_order())
        positions = funded_broker.get_positions()
        assert "SSE:600036" in positions
        assert positions["SSE:600036"].qty == 1000

    def test_buy_avg_cost_includes_fees(self, funded_broker: PaperBroker):
        funded_broker.submit_order(_buy_order())
        pos = funded_broker.get_positions()["SSE:600036"]
        # avg_cost should be slightly higher than market price due to fees
        assert pos.avg_cost > 35.0

    def test_buy_insufficient_cash_rejected(self, funded_broker: PaperBroker):
        # Try to buy more than we can afford
        order = _buy_order(qty=100_000)  # 3.5M+ at 35.0
        result = funded_broker.submit_order(order)
        assert result.status == OrderStatus.REJECTED
        assert "Insufficient cash" in result.reject_reason


# ── Sell Order Tests ──────────────────────────────────────────────────────────

class TestSellOrder:
    def test_sell_without_position_rejected(self, funded_broker: PaperBroker):
        result = funded_broker.submit_order(_sell_order())
        assert result.status == OrderStatus.REJECTED
        assert "No position to sell" in result.reject_reason

    def test_sell_after_buy_fills(self, funded_broker: PaperBroker):
        funded_broker.submit_order(_buy_order())
        result = funded_broker.submit_order(_sell_order())
        assert result.status == OrderStatus.FILLED
        assert result.filled_qty == 1000

    def test_sell_removes_position(self, funded_broker: PaperBroker):
        funded_broker.submit_order(_buy_order())
        funded_broker.submit_order(_sell_order())
        positions = funded_broker.get_positions()
        assert "SSE:600036" not in positions

    def test_sell_partial_qty(self, funded_broker: PaperBroker):
        funded_broker.submit_order(_buy_order(qty=1000))
        funded_broker.submit_order(_sell_order(qty=500))
        positions = funded_broker.get_positions()
        assert positions["SSE:600036"].qty == 500

    def test_sell_excess_qty_fills_available(self, funded_broker: PaperBroker):
        funded_broker.submit_order(_buy_order(qty=500))
        result = funded_broker.submit_order(_sell_order(qty=1000))
        assert result.status == OrderStatus.FILLED
        assert result.filled_qty == 500  # Only had 500


# ── PnL Tests ─────────────────────────────────────────────────────────────────

class TestPnLCalculation:
    def test_realized_pnl_positive_on_profit(self, funded_broker: PaperBroker):
        funded_broker.submit_order(_buy_order(qty=1000))
        # Price goes up
        funded_broker.update_prices({"SSE:600036": 40.0})
        funded_broker.submit_order(_sell_order(qty=1000))
        account = funded_broker.get_account()
        # Should be positive (5.0 * 1000 - fees)
        assert account.realized_pnl > 0

    def test_realized_pnl_negative_on_loss(self, funded_broker: PaperBroker):
        funded_broker.submit_order(_buy_order(qty=1000))
        # Price goes down
        funded_broker.update_prices({"SSE:600036": 30.0})
        funded_broker.submit_order(_sell_order(qty=1000))
        account = funded_broker.get_account()
        # Should be negative (-5.0 * 1000 - fees)
        assert account.realized_pnl < 0

    def test_unrealized_pnl_tracks_price(self, funded_broker: PaperBroker):
        funded_broker.submit_order(_buy_order(qty=1000))
        funded_broker.update_prices({"SSE:600036": 40.0})
        account = funded_broker.get_account()
        # Should show unrealized gain
        assert account.unrealized_pnl > 0

    def test_nav_equals_cash_plus_positions(self, funded_broker: PaperBroker):
        funded_broker.submit_order(_buy_order(qty=1000))
        funded_broker.update_prices({"SSE:600036": 36.0})
        account = funded_broker.get_account()
        expected_nav = account.cash + sum(p.market_value for p in account.positions.values())
        assert abs(account.nav - expected_nav) < 0.01


# ── Cancel Order Tests ────────────────────────────────────────────────────────

class TestCancelOrder:
    def test_cancel_nonexistent_raises(self, broker: PaperBroker):
        with pytest.raises(ValueError, match="not found"):
            broker.cancel_order("nonexistent")

    def test_cancel_pending_order(self, funded_broker: PaperBroker):
        # Submit with no price to keep it pending... actually it would reject
        # Let's create a pending order directly
        order = Order(order_id="pending-1", asset_id="SSE:600036", side="buy", qty=100)
        # Manually add to orders dict
        funded_broker._orders["pending-1"] = order
        result = funded_broker.cancel_order("pending-1")
        assert result.status == OrderStatus.CANCELLED


# ── Account State Tests ───────────────────────────────────────────────────────

class TestAccountState:
    def test_initial_account_state(self, broker: PaperBroker):
        account = broker.get_account()
        assert account.cash == 1_000_000
        assert account.nav == 1_000_000
        assert account.positions == {}
        assert account.realized_pnl == 0.0
        assert account.unrealized_pnl == 0.0

    def test_gross_exposure_calculated(self, funded_broker: PaperBroker):
        funded_broker.submit_order(_buy_order(qty=1000))
        account = funded_broker.get_account()
        assert account.gross_exposure > 0

    def test_multiple_positions(self, funded_broker: PaperBroker):
        funded_broker.submit_order(_buy_order(asset_id="SSE:600036", qty=1000))
        funded_broker.submit_order(_buy_order(asset_id="SSE:601318", qty=500))
        positions = funded_broker.get_positions()
        assert len(positions) == 2
        assert "SSE:600036" in positions
        assert "SSE:601318" in positions
