"""cquant.execution.adapter — Broker adapter interface for real brokers.

Extends the Broker ABC with connection lifecycle and callback support.
"""

from __future__ import annotations

import logging
from abc import abstractmethod
from dataclasses import dataclass
from typing import Any, Callable

from cquant.execution.broker import Broker, Order

logger = logging.getLogger(__name__)


@dataclass
class BrokerInfo:
    """Broker connection metadata."""
    broker_name: str
    broker_version: str
    connected: bool
    account_id: str = ""
    server_info: str = ""
    supported_order_types: list[str] | None = None
    metadata: dict[str, Any] | None = None


class BrokerAdapter(Broker):
    """Abstract broker adapter with connection lifecycle.

    Extends Broker with:
    - connect/disconnect lifecycle
    - Event callbacks (on_fill, on_reject, on_cancel)
    - Broker metadata

    Usage::

        adapter = QMTAdapter(config)
        adapter.connect()
        adapter.on_fill = lambda order: print(f"Filled: {order}")
        adapter.submit_order(order)
        adapter.disconnect()
    """

    # Event callbacks
    on_fill: Callable[[Order], None] | None = None
    on_reject: Callable[[Order], None] | None = None
    on_cancel: Callable[[Order], None] | None = None

    @abstractmethod
    def connect(self) -> None:
        """Establish connection to the broker."""

    @abstractmethod
    def disconnect(self) -> None:
        """Close connection to the broker."""

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if connected to the broker."""

    @abstractmethod
    def get_broker_info(self) -> BrokerInfo:
        """Get broker connection metadata."""

    def _fire_fill(self, order: Order) -> None:
        """Notify fill callback."""
        if self.on_fill:
            try:
                self.on_fill(order)
            except Exception as exc:
                logger.error("on_fill callback error: %s", exc)

    def _fire_reject(self, order: Order) -> None:
        """Notify reject callback."""
        if self.on_reject:
            try:
                self.on_reject(order)
            except Exception as exc:
                logger.error("on_reject callback error: %s", exc)

    def _fire_cancel(self, order: Order) -> None:
        """Notify cancel callback."""
        if self.on_cancel:
            try:
                self.on_cancel(order)
            except Exception as exc:
                logger.error("on_cancel callback error: %s", exc)
