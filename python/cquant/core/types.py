"""cquant.core.types — Canonical domain models shared across all modules.

All monetary values use Python Decimal to avoid floating-point rounding errors.
All timestamps are timezone-aware (UTC preferred internally; display may differ).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

import polars as pl
from pydantic import BaseModel, ConfigDict, field_validator

from cquant.core.enums import (
    AdjMethod,
    AssetClass,
    AssetStatus,
    Currency,
    Exchange,
    Frequency,
    OrderSide,
    OrderStatus,
    OrderType,
    RiskDecisionType,
    SignalDirection,
)


class Asset(BaseModel):
    """Canonical instrument descriptor."""

    model_config = ConfigDict(frozen=True)

    asset_id: str          # "{exchange}:{symbol}", e.g. "SSE:600036"
    symbol: str
    exchange: Exchange
    asset_class: AssetClass
    currency: Currency
    name: str = ""
    status: AssetStatus = AssetStatus.ACTIVE
    lot_size: int = 100    # Minimum tradable units (A-share default: 100)
    tick_size: Decimal = Decimal("0.01")

    @field_validator("asset_id")
    @classmethod
    def _validate_asset_id(cls, v: str) -> str:
        if ":" not in v:
            raise ValueError("asset_id must follow '{exchange}:{symbol}' format")
        return v


class Bar(BaseModel):
    """OHLCV bar for a single asset at a single timestamp."""

    model_config = ConfigDict(frozen=True)

    asset_id: str
    timestamp: datetime        # Bar close time, UTC
    trade_date: date           # Local exchange date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    amount: Decimal = Decimal("0")  # Turnover in local currency
    adj_close: Decimal | None = None
    adj_factor: Decimal | None = None
    adj_method: AdjMethod = AdjMethod.NONE
    is_suspended: bool = False
    limit_up: Decimal | None = None    # Upper price limit for the day
    limit_down: Decimal | None = None  # Lower price limit for the day
    frequency: Frequency = Frequency.D1


class Signal(BaseModel):
    """Single-asset trading signal at a point in time."""

    model_config = ConfigDict(frozen=True)

    asset_id: str
    signal_date: date
    direction: SignalDirection
    strength: float = 0.0    # Normalized [-1, 1]; 0 = neutral/flat
    confidence: float = 1.0  # [0, 1]
    strategy_id: str = ""
    model_version: str = ""


class TargetWeights(BaseModel):
    """Desired portfolio weights after position sizing."""

    model_config = ConfigDict(frozen=True)

    strategy_id: str
    rebalance_date: date
    weights: dict[str, float]  # asset_id → target weight (sum may ≠ 1 for long-short)
    sizer_name: str = ""
    metadata: dict[str, Any] = {}


class OrderIntent(BaseModel):
    """Pre-trade order request submitted to risk checks."""

    model_config = ConfigDict(frozen=True)

    asset_id: str
    side: OrderSide
    requested_qty: Decimal
    order_type: OrderType = OrderType.MARKET
    limit_price: Decimal | None = None
    strategy_id: str = ""
    signal_date: date | None = None


class Order(BaseModel):
    """Approved order after risk checks pass."""

    model_config = ConfigDict(frozen=True)

    order_id: str
    asset_id: str
    side: OrderSide
    approved_qty: Decimal
    order_type: OrderType = OrderType.MARKET
    limit_price: Decimal | None = None
    status: OrderStatus = OrderStatus.PENDING
    strategy_id: str = ""
    submitted_at: datetime | None = None


class OrderFill(BaseModel):
    """Confirmed fill event from the execution / simulation layer."""

    model_config = ConfigDict(frozen=True)

    fill_id: str
    order_id: str
    asset_id: str
    side: OrderSide
    filled_qty: Decimal
    fill_price: Decimal
    commission: Decimal = Decimal("0")
    stamp_duty: Decimal = Decimal("0")
    slippage: Decimal = Decimal("0")
    total_cost: Decimal = Decimal("0")   # commission + stamp_duty + slippage
    filled_at: datetime | None = None


class RiskDecision(BaseModel):
    """Result of a pre-trade risk check."""

    model_config = ConfigDict(frozen=True)

    decision: RiskDecisionType
    original_qty: Decimal
    approved_qty: Decimal
    reasons: list[str] = []
    policy_names: list[str] = []


class RiskSnapshot(BaseModel):
    """Point-in-time portfolio risk metrics."""

    model_config = ConfigDict(frozen=True)

    snapshot_ts: datetime
    strategy_id: str
    gross_leverage: float = 0.0
    net_leverage: float = 0.0
    beta: float | None = None
    drawdown: float = 0.0        # Current drawdown from peak (negative)
    var_95: float | None = None  # 1-day 95% VaR as fraction of NAV
    cvar_95: float | None = None
    sector_exposure: dict[str, float] = {}
    factor_exposure: dict[str, float] = {}


# ── Polars-based frame aliases ─────────────────────────────────────────────────
# These are type aliases for documentation; actual validation happens at write
# boundaries via schema checks, not at runtime via isinstance checks.

SignalFrame = pl.DataFrame
"""Polars DataFrame with columns: asset_id (str), signal_date (date),
direction (str), strength (f64), confidence (f64), strategy_id (str)."""
