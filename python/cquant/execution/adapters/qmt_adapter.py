"""cquant.execution.adapters.qmt_adapter — QMT (迅投) broker adapter.

Requires:
- xtquant SDK (from QMT mini terminal)
- QMT client running locally

Configuration:
    host: QMT mini terminal host (default: 127.0.0.1)
    port: QMT mini terminal port (default: 58610)
    account_id: Trading account ID
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from cquant.execution.adapter import BrokerAdapter, BrokerInfo
from cquant.execution.broker import Account, Order, OrderStatus, Position

logger = logging.getLogger(__name__)


class QMTAdapter(BrokerAdapter):
    """QMT (迅投) broker adapter.

    Connects to a local QMT mini terminal for order execution.
    Requires xtquant SDK and a running QMT client.

    Usage::

        adapter = QMTAdapter(host="127.0.0.1", port=58610, account_id="YOUR_ACCOUNT")
        adapter.connect()
        order = Order(order_id="1", asset_id="SSE:600036", side="buy", qty=1000)
        result = adapter.submit_order(order)
        adapter.disconnect()
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 58610,
        account_id: str = "",
        **kwargs: Any,
    ) -> None:
        self._host = host
        self._port = port
        self._account_id = account_id
        self._connected = False
        self._xt_trader = None
        self._xt_connected = False

        # State
        self._orders: dict[str, Order] = {}
        self._positions: dict[str, Position] = {}
        self._cash: float = 0.0
        self._prices: dict[str, float] = {}

    def connect(self) -> None:
        """Connect to QMT mini terminal."""
        try:
            from xtquant import xttrader, xtdata  # type: ignore[import-untyped]
        except ImportError:
            raise RuntimeError(
                "xtquant is not installed. "
                "Install QMT mini terminal and add xtquant to Python path."
            )

        try:
            # Create XtQuantTrader instance
            self._xt_trader = xttrader.XtQuantTrader(
                path=f"{self._host}:{self._port}",
                session_id=int(uuid.uuid4().hex[:8], 16),
            )

            # Connect
            result = self._xt_trader.connect()
            if result == 0:
                self._connected = True
                logger.info("Connected to QMT at %s:%s", self._host, self._port)

                # Subscribe to account updates
                if self._account_id:
                    self._xt_trader.subscribe(self._account_id)
            else:
                logger.error("Failed to connect to QMT: result=%s", result)

        except Exception as exc:
            logger.error("QMT connection failed: %s", exc)
            raise RuntimeError(f"QMT connection failed: {exc}") from exc

    def disconnect(self) -> None:
        """Disconnect from QMT."""
        if self._xt_trader:
            try:
                self._xt_trader.stop()
            except Exception as exc:
                logger.warning("QMT disconnect error: %s", exc)
            finally:
                self._connected = False
                self._xt_trader = None
                logger.info("Disconnected from QMT")

    def is_connected(self) -> bool:
        """Check if connected to QMT."""
        return self._connected

    def get_broker_info(self) -> BrokerInfo:
        """Get QMT connection info."""
        return BrokerInfo(
            broker_name="qmt",
            broker_version="xtquant",
            connected=self._connected,
            account_id=self._account_id,
            server_info=f"{self._host}:{self._port}",
            supported_order_types=["market", "limit"],
        )

    def submit_order(self, order: Order) -> Order:
        """Submit order to QMT."""
        if not self._connected or not self._xt_trader:
            order.status = OrderStatus.REJECTED
            order.reject_reason = "Not connected to QMT"
            order.rejected_at = datetime.now(tz=timezone.utc)
            self._orders[order.order_id] = order
            self._fire_reject(order)
            return order

        try:
            from xtquant.xttype import StockAccount  # type: ignore[import-untyped]

            # Parse asset_id (SSE:600036 -> 600036.SH)
            symbol = self._parse_asset_id(order.asset_id)

            # Map side
            xt_side = 23 if order.side == "buy" else 24  # BUY=23, SELL=24

            # Map order type
            xt_type = 0 if order.order_type == "market" else 11  # MARKET=0, LIMIT=11

            price = order.limit_price or 0.0
            account = StockAccount(self._account_id, "STOCK")

            # Submit via xt_trader
            xt_order_id = self._xt_trader.order_stock(
                account=account,
                stock_code=symbol,
                order_type=xt_side,
                order_volume=order.qty,
                price_type=xt_type,
                price=price,
            )

            order.status = OrderStatus.SUBMITTED
            order.submitted_at = datetime.now(tz=timezone.utc)
            order.metadata["xt_order_id"] = xt_order_id
            self._orders[order.order_id] = order

            logger.info("Submitted order %s to QMT (xt_id=%s)", order.order_id, xt_order_id)

        except Exception as exc:
            order.status = OrderStatus.REJECTED
            order.reject_reason = str(exc)
            order.rejected_at = datetime.now(tz=timezone.utc)
            self._orders[order.order_id] = order
            self._fire_reject(order)
            logger.error("QMT order failed: %s", exc)

        return order

    def cancel_order(self, order_id: str) -> Order:
        """Cancel order via QMT."""
        order = self._orders.get(order_id)
        if order is None:
            raise ValueError(f"Order not found: {order_id}")

        if not self._connected or not self._xt_trader:
            order.status = OrderStatus.REJECTED
            order.reject_reason = "Not connected to QMT"
            return order

        try:
            xt_order_id = order.metadata.get("xt_order_id")
            if xt_order_id:
                account = self._account_id
                self._xt_trader.cancel_order_stock(account, xt_order_id)
                order.status = OrderStatus.CANCELLED
                order.cancelled_at = datetime.now(tz=timezone.utc)
                self._fire_cancel(order)
        except Exception as exc:
            logger.error("QMT cancel failed: %s", exc)

        return order

    def get_order(self, order_id: str) -> Order | None:
        """Get order by ID."""
        return self._orders.get(order_id)

    def get_orders(self, status: OrderStatus | None = None) -> list[Order]:
        """Get all orders."""
        orders = list(self._orders.values())
        if status:
            orders = [o for o in orders if o.status == status]
        return orders

    def get_positions(self) -> dict[str, Position]:
        """Get positions from QMT."""
        if not self._connected or not self._xt_trader:
            return self._positions.copy()

        try:
            from xtquant.xttype import StockAccount
            account = StockAccount(self._account_id, "STOCK")
            positions = self._xt_trader.query_stock_positions(account)

            result: dict[str, Position] = {}
            for pos in positions:
                asset_id = self._to_asset_id(pos.stock_code)
                result[asset_id] = Position(
                    asset_id=asset_id,
                    qty=pos.volume,
                    avg_cost=pos.open_price,
                    market_value=pos.market_value,
                    unrealized_pnl=pos.market_value - pos.open_price * pos.volume,
                )
            self._positions = result
            return result.copy()

        except Exception as exc:
            logger.error("QMT query positions failed: %s", exc)
            return self._positions.copy()

    def get_account(self) -> Account:
        """Get account state from QMT."""
        if not self._connected or not self._xt_trader:
            return Account(
                cash=0, positions={}, nav=0,
                gross_exposure=0, net_exposure=0,
                realized_pnl=0, unrealized_pnl=0,
            )

        try:
            from xtquant.xttype import StockAccount
            account = StockAccount(self._account_id, "STOCK")
            asset = self._xt_trader.query_stock_asset(account)

            positions = self.get_positions()
            gross_exposure = sum(abs(p.market_value) for p in positions.values())
            net_exposure = sum(p.market_value for p in positions.values())
            unrealized_pnl = sum(p.unrealized_pnl for p in positions.values())

            return Account(
                cash=asset.cash,
                positions=positions,
                nav=asset.total_asset,
                gross_exposure=gross_exposure,
                net_exposure=net_exposure,
                realized_pnl=0,  # QMT doesn't expose this directly
                unrealized_pnl=unrealized_pnl,
            )

        except Exception as exc:
            logger.error("QMT query account failed: %s", exc)
            return Account(
                cash=0, positions={}, nav=0,
                gross_exposure=0, net_exposure=0,
                realized_pnl=0, unrealized_pnl=0,
            )

    def update_prices(self, prices: dict[str, float]) -> None:
        """Update cached prices."""
        self._prices.update(prices)

    def _parse_asset_id(self, asset_id: str) -> str:
        """Convert SSE:600036 to 600036.SH for QMT."""
        if ":" in asset_id:
            exchange, code = asset_id.split(":", 1)
            suffix = "SH" if exchange == "SSE" else "SZ"
            return f"{code}.{suffix}"
        return asset_id

    def _to_asset_id(self, qmt_code: str) -> str:
        """Convert 600036.SH to SSE:600036."""
        if "." in qmt_code:
            code, suffix = qmt_code.split(".", 1)
            exchange = "SSE" if suffix == "SH" else "SZSE"
            return f"{exchange}:{code}"
        return qmt_code
