"""cquant.execution.broker — Abstract broker interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any


class OrderStatus(Enum):
    """Order lifecycle states."""
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIAL_FILLED = "partial_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass
class Order:
    """Order representation."""
    order_id: str
    asset_id: str
    side: str  # "buy", "sell"
    qty: int
    order_type: str = "market"  # "market", "limit"
    limit_price: float | None = None
    status: OrderStatus = OrderStatus.PENDING
    filled_qty: int = 0
    filled_price: float = 0.0
    commission: float = 0.0
    stamp_duty: float = 0.0
    slippage: float = 0.0
    total_cost: float = 0.0
    strategy_id: str = ""
    submitted_at: datetime | None = None
    filled_at: datetime | None = None
    cancelled_at: datetime | None = None
    rejected_at: datetime | None = None
    reject_reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Position:
    """Position representation."""
    asset_id: str
    qty: int
    avg_cost: float
    market_value: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0


@dataclass
class Account:
    """Account state."""
    cash: float
    positions: dict[str, Position]
    nav: float
    gross_exposure: float
    net_exposure: float
    realized_pnl: float
    unrealized_pnl: float


class Broker(ABC):
    """Abstract broker interface.

    Implementations should handle order submission, cancellation,
    position tracking, and account state management.
    """

    @abstractmethod
    def submit_order(self, order: Order) -> Order:
        """Submit an order for execution.

        Args:
            order: Order to submit

        Returns:
            Updated order with status
        """

    @abstractmethod
    def cancel_order(self, order_id: str) -> Order:
        """Cancel a pending order.

        Args:
            order_id: ID of order to cancel

        Returns:
            Updated order with cancelled status
        """

    @abstractmethod
    def get_order(self, order_id: str) -> Order | None:
        """Get order by ID.

        Args:
            order_id: Order ID

        Returns:
            Order if found, None otherwise
        """

    @abstractmethod
    def get_orders(self, status: OrderStatus | None = None) -> list[Order]:
        """Get all orders, optionally filtered by status.

        Args:
            status: Filter by order status (None = all)

        Returns:
            List of orders
        """

    @abstractmethod
    def get_positions(self) -> dict[str, Position]:
        """Get current positions.

        Returns:
            Dict of asset_id -> Position
        """

    @abstractmethod
    def get_account(self) -> Account:
        """Get current account state.

        Returns:
            Account with cash, positions, NAV, etc.
        """

    @abstractmethod
    def update_prices(self, prices: dict[str, float]) -> None:
        """Update market prices for position valuation.

        Args:
            prices: Dict of asset_id -> current price
        """
