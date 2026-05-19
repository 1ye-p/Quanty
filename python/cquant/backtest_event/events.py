"""cquant.backtest_event.events — Event types for the event-driven engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any


class EventType(Enum):
    """Types of events in the backtest pipeline."""
    BAR = "bar"
    SIGNAL = "signal"
    ORDER_INTENT = "order_intent"
    ORDER = "order"
    FILL = "fill"
    RISK_DECISION = "risk_decision"
    PORTFOLIO_UPDATE = "portfolio_update"


@dataclass
class BarEvent:
    """Market data bar event."""
    event_type: EventType = EventType.BAR
    asset_id: str = ""
    trade_date: date | None = None
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: float = 0.0
    amount: float = 0.0
    is_suspended: bool = False
    prev_close: float = 0.0


@dataclass
class SignalEvent:
    """Strategy signal event."""
    event_type: EventType = EventType.SIGNAL
    asset_id: str = ""
    trade_date: date | None = None
    direction: str = "long"  # "long", "short", "flat"
    strength: float = 0.0
    confidence: float = 1.0
    strategy_id: str = ""


@dataclass
class OrderIntentEvent:
    """Pre-risk-check order intent."""
    event_type: EventType = EventType.ORDER_INTENT
    asset_id: str = ""
    trade_date: date | None = None
    side: str = "buy"  # "buy", "sell"
    requested_qty: int = 0
    order_type: str = "market"
    limit_price: float | None = None
    strategy_id: str = ""


@dataclass
class OrderEvent:
    """Approved order after risk checks."""
    event_type: EventType = EventType.ORDER
    order_id: str = ""
    asset_id: str = ""
    trade_date: date | None = None
    side: str = "buy"
    approved_qty: int = 0
    order_type: str = "market"
    limit_price: float | None = None
    status: str = "pending"  # "pending", "filled", "cancelled", "rejected"
    strategy_id: str = ""


@dataclass
class FillEvent:
    """Confirmed fill event."""
    event_type: EventType = EventType.FILL
    fill_id: str = ""
    order_id: str = ""
    asset_id: str = ""
    trade_date: date | None = None
    side: str = "buy"
    qty: int = 0
    price: float = 0.0
    notional: float = 0.0
    commission: float = 0.0
    stamp_duty: float = 0.0
    slippage: float = 0.0
    total_cost: float = 0.0


@dataclass
class RiskDecisionEvent:
    """Risk check decision."""
    event_type: EventType = EventType.RISK_DECISION
    order_intent: OrderIntentEvent | None = None
    decision: str = "approved"  # "approved", "clipped", "rejected"
    approved_qty: int = 0
    reasons: list[str] = field(default_factory=list)
    policy_names: list[str] = field(default_factory=list)


@dataclass
class PortfolioUpdateEvent:
    """Portfolio state update."""
    event_type: EventType = EventType.PORTFOLIO_UPDATE
    trade_date: date | None = None
    cash: float = 0.0
    nav: float = 0.0
    positions_count: int = 0
    gross_exposure: float = 0.0
    net_exposure: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
