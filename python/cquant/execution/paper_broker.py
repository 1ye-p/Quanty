"""cquant.execution.paper_broker — Simulated broker for testing.

Implements the Broker interface with simulated order execution.
Orders are filled at the current market price with configurable costs.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from cquant.backtest_vector.costs import CostModel
from cquant.execution.broker import Account, Broker, Order, OrderStatus, Position

logger = logging.getLogger(__name__)


class PaperBroker(Broker):
    """Simulated broker for paper trading.

    Executes orders at market price with realistic cost simulation.
    Tracks positions, cash, and provides account state.

    Usage::

        broker = PaperBroker(initial_cash=1_000_000)
        order = Order(order_id="1", asset_id="SSE:600036", side="buy", qty=1000)
        result = broker.submit_order(order)
        account = broker.get_account()
    """

    def __init__(
        self,
        initial_cash: float = 1_000_000,
        cost_model: CostModel | None = None,
    ) -> None:
        self._cash = initial_cash
        self._initial_cash = initial_cash
        self._cost_model = cost_model or CostModel.for_cn()
        self._positions: dict[str, Position] = {}
        self._orders: dict[str, Order] = {}
        self._prices: dict[str, float] = {}
        self._realized_pnl = 0.0

    def submit_order(self, order: Order) -> Order:
        """Submit an order for immediate execution.

        For paper trading, orders are filled immediately at market price.
        """
        # Validate qty
        if order.qty <= 0:
            order.status = OrderStatus.REJECTED
            order.reject_reason = f"Invalid qty: {order.qty}"
            order.rejected_at = datetime.now(tz=timezone.utc)
            self._orders[order.order_id] = order
            return order

        # Reject limit orders (not supported in paper trading)
        if order.order_type != "market":
            order.status = OrderStatus.REJECTED
            order.reject_reason = "PaperBroker currently supports market orders only"
            order.rejected_at = datetime.now(tz=timezone.utc)
            self._orders[order.order_id] = order
            return order

        if order.status != OrderStatus.PENDING:
            order.status = OrderStatus.REJECTED
            order.reject_reason = f"Invalid order status: {order.status}"
            order.rejected_at = datetime.now(tz=timezone.utc)
            self._orders[order.order_id] = order
            return order

        # Get current price
        price = self._prices.get(order.asset_id, 0.0)
        if price <= 0:
            order.status = OrderStatus.REJECTED
            order.reject_reason = f"No price available for {order.asset_id}"
            order.rejected_at = datetime.now(tz=timezone.utc)
            self._orders[order.order_id] = order
            return order

        # Check if we can execute
        if order.side == "buy":
            return self._execute_buy(order, price)
        elif order.side == "sell":
            return self._execute_sell(order, price)
        else:
            order.status = OrderStatus.REJECTED
            order.reject_reason = f"Invalid side: {order.side}"
            order.rejected_at = datetime.now(tz=timezone.utc)
            self._orders[order.order_id] = order
            return order

    def cancel_order(self, order_id: str) -> Order:
        """Cancel a pending order."""
        order = self._orders.get(order_id)
        if order is None:
            raise ValueError(f"Order not found: {order_id}")

        if order.status in (OrderStatus.PENDING, OrderStatus.SUBMITTED):
            order.status = OrderStatus.CANCELLED
            order.cancelled_at = datetime.now(tz=timezone.utc)
        else:
            logger.warning("Cannot cancel order %s with status %s", order_id, order.status)

        return order

    def get_order(self, order_id: str) -> Order | None:
        """Get order by ID."""
        return self._orders.get(order_id)

    def get_orders(self, status: OrderStatus | None = None) -> list[Order]:
        """Get all orders, optionally filtered by status."""
        orders = list(self._orders.values())
        if status is not None:
            orders = [o for o in orders if o.status == status]
        return orders

    def get_positions(self) -> dict[str, Position]:
        """Get current positions."""
        return self._positions.copy()

    def get_account(self) -> Account:
        """Get current account state."""
        # Update market values
        gross_exposure = 0.0
        unrealized_pnl = 0.0

        for asset_id, pos in self._positions.items():
            price = self._prices.get(asset_id, pos.avg_cost)
            pos.market_value = pos.qty * price
            pos.unrealized_pnl = (price - pos.avg_cost) * pos.qty
            gross_exposure += abs(pos.market_value)
            unrealized_pnl += pos.unrealized_pnl

        nav = self._cash + sum(pos.market_value for pos in self._positions.values())
        net_exposure = sum(pos.market_value for pos in self._positions.values())

        return Account(
            cash=self._cash,
            positions=self._positions.copy(),
            nav=nav,
            gross_exposure=gross_exposure,
            net_exposure=net_exposure,
            realized_pnl=self._realized_pnl,
            unrealized_pnl=unrealized_pnl,
        )

    def update_prices(self, prices: dict[str, float]) -> None:
        """Update market prices for position valuation."""
        self._prices.update(prices)

    def _execute_buy(self, order: Order, price: float) -> Order:
        """Execute a buy order."""
        from decimal import Decimal

        notional = order.qty * price
        commission = float(self._cost_model.commission(Decimal(str(notional))))
        stamp_duty = float(self._cost_model.stamp_duty(Decimal(str(notional)), is_sell=False))
        slippage = float(self._cost_model.slippage(Decimal(str(notional))))
        total_cost = commission + stamp_duty + slippage

        # Check cash
        required = notional + total_cost
        if required > self._cash:
            order.status = OrderStatus.REJECTED
            order.reject_reason = f"Insufficient cash: need {required:.2f}, have {self._cash:.2f}"
            order.rejected_at = datetime.now(tz=timezone.utc)
            self._orders[order.order_id] = order
            return order

        # Execute
        self._cash -= required
        order.filled_qty = order.qty
        order.filled_price = price
        order.commission = commission
        order.stamp_duty = stamp_duty
        order.slippage = slippage
        order.total_cost = total_cost
        order.status = OrderStatus.FILLED
        order.filled_at = datetime.now(tz=timezone.utc)

        # Update position
        if order.asset_id in self._positions:
            pos = self._positions[order.asset_id]
            total_cost_basis = pos.avg_cost * pos.qty + notional + total_cost
            pos.qty += order.qty
            pos.avg_cost = total_cost_basis / pos.qty if pos.qty > 0 else 0
        else:
            self._positions[order.asset_id] = Position(
                asset_id=order.asset_id,
                qty=order.qty,
                avg_cost=(notional + total_cost) / order.qty,
            )

        self._orders[order.order_id] = order
        logger.info("Filled buy: %s x%d @ %.2f (cost: %.2f)", order.asset_id, order.qty, price, total_cost)
        return order

    def _execute_sell(self, order: Order, price: float) -> Order:
        """Execute a sell order."""
        from decimal import Decimal

        # Check position
        pos = self._positions.get(order.asset_id)
        if pos is None or pos.qty <= 0:
            order.status = OrderStatus.REJECTED
            order.reject_reason = f"No position to sell: {order.asset_id}"
            order.rejected_at = datetime.now(tz=timezone.utc)
            self._orders[order.order_id] = order
            return order

        # Adjust qty if needed
        sell_qty = min(order.qty, pos.qty)
        notional = sell_qty * price
        commission = float(self._cost_model.commission(Decimal(str(notional))))
        stamp_duty = float(self._cost_model.stamp_duty(Decimal(str(notional)), is_sell=True))
        slippage = float(self._cost_model.slippage(Decimal(str(notional))))
        total_cost = commission + stamp_duty + slippage

        # Execute
        self._cash += notional - total_cost
        order.filled_qty = sell_qty
        order.filled_price = price
        order.commission = commission
        order.stamp_duty = stamp_duty
        order.slippage = slippage
        order.total_cost = total_cost
        order.status = OrderStatus.FILLED
        order.filled_at = datetime.now(tz=timezone.utc)

        # Calculate realized PnL (including fees)
        realized = (price - pos.avg_cost) * sell_qty - total_cost
        self._realized_pnl += realized

        # Update position
        pos.qty -= sell_qty
        if pos.qty <= 0:
            del self._positions[order.asset_id]

        self._orders[order.order_id] = order
        logger.info("Filled sell: %s x%d @ %.2f (cost: %.2f, PnL: %.2f)",
                     order.asset_id, sell_qty, price, total_cost, realized)
        return order
