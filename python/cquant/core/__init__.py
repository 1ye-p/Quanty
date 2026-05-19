"""cquant.core — Shared domain types, enums, errors, event bus, clock, and config."""

from cquant.core.enums import (
    AdjMethod,
    AssetClass,
    AssetStatus,
    Currency,
    Exchange,
    Frequency,
    Market,
    OrderSide,
    OrderType,
    SignalDirection,
)
from cquant.core.errors import (
    CQuantError,
    DataNotFoundError,
    IngestError,
    InvalidSignalError,
    MarketCalendarError,
    PluginError,
    RiskDecisionError,
)
from cquant.core.config import settings
from cquant.core.types import (
    Asset,
    Bar,
    Order,
    OrderFill,
    OrderIntent,
    RiskDecision,
    RiskSnapshot,
    Signal,
    SignalFrame,
    TargetWeights,
)

__all__ = [
    # Config
    "settings",
    # Enums
    "AdjMethod",
    "AssetClass",
    "AssetStatus",
    "Currency",
    "Exchange",
    "Frequency",
    "Market",
    "OrderSide",
    "OrderType",
    "SignalDirection",
    # Errors
    "CQuantError",
    "DataNotFoundError",
    "IngestError",
    "InvalidSignalError",
    "MarketCalendarError",
    "PluginError",
    "RiskDecisionError",
    # Domain types
    "Asset",
    "Bar",
    "Order",
    "OrderFill",
    "OrderIntent",
    "RiskDecision",
    "RiskSnapshot",
    "Signal",
    "SignalFrame",
    "TargetWeights",
]
