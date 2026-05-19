"""cquant.backtest_event — Event-driven backtest engine.

Provides both the Python event-driven engine and the Rust facade.
"""

from cquant.backtest_event.engine import BacktestEventSpec, EventBacktestEngine
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

__all__ = [
    "BacktestEventSpec",
    "EventBacktestEngine",
    "EventDrivenEngine",
    "BarEvent",
    "EventType",
    "FillEvent",
    "OrderEvent",
    "OrderIntentEvent",
    "PortfolioUpdateEvent",
    "RiskDecisionEvent",
    "SignalEvent",
]
