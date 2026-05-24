"""Risk management API routes."""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

import polars as pl
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/risk", tags=["risk"])


# ── Schemas ───────────────────────────────────────────────────────────────────


class PolicyInfo(BaseModel):
    name: str
    description: str
    params: list[dict[str, Any]]


class SizerInfo(BaseModel):
    name: str
    description: str
    params: list[dict[str, Any]]


class RiskCheckRequest(BaseModel):
    policy_name: str
    params: dict[str, Any] = Field(default_factory=dict)
    # Candidate order
    asset_id: str
    side: str  # "buy" | "sell"
    qty: float
    price: float
    # Portfolio context
    nav: float = 1_000_000.0
    cash: float = 500_000.0
    positions: dict[str, dict[str, float]] = Field(default_factory=dict)
    # Optional context
    drawdown: float = 0.0
    as_of_date: str = ""  # ISO date


class RiskCheckResponse(BaseModel):
    decision: str  # "approved" | "clipped" | "rejected"
    original_qty: float
    approved_qty: float
    reasons: list[str]


# ── Policy registry ───────────────────────────────────────────────────────────

_POLICY_REGISTRY: list[dict[str, Any]] = [
    {
        "name": "fixed_stop_loss",
        "description": "Reject if loss exceeds fixed threshold from entry price",
        "params": [
            {"key": "stop_pct", "type": "float", "default": 0.05, "description": "Stop loss percentage (e.g. 0.05 = 5%)"},
        ],
    },
    {
        "name": "trailing_stop_loss",
        "description": "Reject if price drops trailing_pct from peak",
        "params": [
            {"key": "trailing_pct", "type": "float", "default": 0.08, "description": "Trailing stop percentage"},
        ],
    },
    {
        "name": "atr_stop_loss",
        "description": "ATR-based stop loss",
        "params": [
            {"key": "n_atr", "type": "float", "default": 2.0, "description": "ATR multiplier for stop distance"},
        ],
    },
    {
        "name": "drawdown_breaker",
        "description": "Halt trading when portfolio drawdown exceeds threshold",
        "params": [
            {"key": "max_drawdown", "type": "float", "default": -0.10, "description": "Max drawdown (negative, e.g. -0.10)"},
        ],
    },
    {
        "name": "position_limit",
        "description": "Limit single position weight",
        "params": [
            {"key": "max_position_pct", "type": "float", "default": 0.10, "description": "Max position weight"},
        ],
    },
    {
        "name": "sector_limit",
        "description": "Limit sector exposure",
        "params": [
            {"key": "max_sector_pct", "type": "float", "default": 0.30, "description": "Max sector weight"},
            {"key": "sector_map", "type": "dict", "default": {}, "description": "asset_id -> sector mapping"},
        ],
    },
    {
        "name": "leverage_limit",
        "description": "Limit gross leverage",
        "params": [
            {"key": "max_gross_leverage", "type": "float", "default": 1.0, "description": "Max gross leverage"},
        ],
    },
    {
        "name": "max_holding_days",
        "description": "Force exit after max holding period",
        "params": [
            {"key": "max_days", "type": "int", "default": 30, "description": "Max holding days"},
        ],
    },
    {
        "name": "factor_exposure_limit",
        "description": "Limit factor exposure",
        "params": [
            {"key": "factor_limits", "type": "dict", "default": {}, "description": "factor_name -> max_abs_exposure"},
        ],
    },
]

_SIZER_REGISTRY: list[dict[str, Any]] = [
    {
        "name": "equal_weight",
        "description": "Equal weight across all selected assets",
        "params": [],
    },
    {
        "name": "kelly",
        "description": "Kelly criterion based sizing",
        "params": [
            {"key": "fraction", "type": "float", "default": 0.5, "description": "Kelly fraction (half-Kelly = 0.5)"},
        ],
    },
    {
        "name": "mvo",
        "description": "Mean-variance optimized weights",
        "params": [
            {"key": "risk_free_rate", "type": "float", "default": 0.0, "description": "Risk-free rate"},
            {"key": "long_only", "type": "bool", "default": True, "description": "Long-only constraint"},
        ],
    },
    {
        "name": "target_vol",
        "description": "Target volatility scaling",
        "params": [
            {"key": "target_vol", "type": "float", "default": 0.15, "description": "Target annualized volatility"},
        ],
    },
    {
        "name": "vol_parity",
        "description": "Inverse volatility weighting (risk parity for positions)",
        "params": [],
    },
    {
        "name": "black_litterman",
        "description": "Black-Litterman model with market equilibrium + views",
        "params": [
            {"key": "tau", "type": "float", "default": 0.05, "description": "Uncertainty scaling factor"},
            {"key": "risk_free_rate", "type": "float", "default": 0.0, "description": "Risk-free rate"},
        ],
    },
]


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("/policies", response_model=list[PolicyInfo])
async def list_policies() -> list[dict]:
    """List available risk policies and their configurable parameters."""
    return _POLICY_REGISTRY


@router.get("/sizers", response_model=list[SizerInfo])
async def list_sizers() -> list[dict]:
    """List available position sizers and their configurable parameters."""
    return _SIZER_REGISTRY


@router.post("/check", response_model=RiskCheckResponse)
async def risk_check(body: RiskCheckRequest) -> dict:
    """Run a pre-trade risk check using the specified policy.

    Constructs proper OrderIntent, RiskSnapshot, and RiskContext from
    the request body and runs the selected policy's evaluate() method.
    """
    from cquant.core.enums import OrderSide, RiskDecisionType
    from cquant.core.types import OrderIntent, RiskSnapshot
    from cquant.riskguard.models import RiskContext

    # Build candidate OrderIntent
    side = OrderSide.BUY if body.side.lower() == "buy" else OrderSide.SELL
    candidate = OrderIntent(
        asset_id=body.asset_id,
        side=side,
        requested_qty=Decimal(str(body.qty)),
        limit_price=Decimal(str(body.price)),
    )

    # Build RiskSnapshot
    now = datetime.now(tz=timezone.utc)
    snapshot = RiskSnapshot(
        snapshot_ts=now,
        strategy_id="api_check",
        drawdown=body.drawdown,
    )

    # Build RiskContext with current positions as DataFrame
    as_of = date.fromisoformat(body.as_of_date) if body.as_of_date else date.today()
    if body.positions:
        pos_rows = []
        for aid, p in body.positions.items():
            mv = p.get("market_value", p.get("qty", 0) * p.get("avg_cost", 0))
            pos_rows.append({
                "asset_id": aid,
                "quantity": p.get("qty", 0),
                "market_value": mv,
                "weight": mv / body.nav if body.nav > 0 else 0,
            })
        current_positions = pl.DataFrame(pos_rows)
    else:
        current_positions = pl.DataFrame({
            "asset_id": [],
            "quantity": [],
            "market_value": [],
            "weight": [],
        }).cast({"asset_id": pl.Utf8, "quantity": pl.Float64, "market_value": pl.Float64, "weight": pl.Float64})

    ctx = RiskContext(
        as_of_date=as_of,
        portfolio_nav=Decimal(str(body.nav)),
        current_positions=current_positions,
        current_snapshot=snapshot,
    )

    # Instantiate and run policy
    policy = _create_policy(body.policy_name, body.params)

    try:
        decision = policy.evaluate(candidate, snapshot, ctx)
    except Exception as exc:
        logger.exception("Risk check failed for policy %s", body.policy_name)
        raise HTTPException(status_code=422, detail=f"Risk check failed: {exc}")

    return {
        "decision": decision.decision.value if isinstance(decision.decision, RiskDecisionType) else str(decision.decision),
        "original_qty": float(decision.original_qty),
        "approved_qty": float(decision.approved_qty),
        "reasons": decision.reasons,
    }


def _create_policy(name: str, params: dict) -> Any:
    """Factory for risk policy instances."""
    from cquant.riskguard.policies import (
        ATRStopLossPolicy,
        DrawdownBreakerPolicy,
        FactorExposureLimitPolicy,
        FixedStopLossPolicy,
        LeverageLimitPolicy,
        MaxHoldingDaysPolicy,
        PositionLimitPolicy,
        SectorLimitPolicy,
        TrailingStopLossPolicy,
    )

    registry = {
        "fixed_stop_loss": lambda p: FixedStopLossPolicy(stop_pct=-abs(p.get("stop_pct", 0.05))),
        "trailing_stop_loss": lambda p: TrailingStopLossPolicy(trail_pct=-abs(p.get("trailing_pct", 0.08))),
        "atr_stop_loss": lambda p: ATRStopLossPolicy(n_atr=p.get("n_atr", 2.0)),
        "drawdown_breaker": lambda p: DrawdownBreakerPolicy(max_drawdown=p.get("max_drawdown", -0.10)),
        "position_limit": lambda p: PositionLimitPolicy(max_position_pct=p.get("max_position_pct", 0.10)),
        "sector_limit": lambda p: SectorLimitPolicy(
            max_sector_pct=p.get("max_sector_pct", 0.30), sector_map=p.get("sector_map")
        ),
        "leverage_limit": lambda p: LeverageLimitPolicy(max_gross_leverage=p.get("max_gross_leverage", 1.0)),
        "max_holding_days": lambda p: MaxHoldingDaysPolicy(max_days=p.get("max_days", 30)),
        "factor_exposure_limit": lambda p: FactorExposureLimitPolicy(factor_limits=p.get("factor_limits", {})),
    }

    factory = registry.get(name)
    if not factory:
        raise HTTPException(status_code=422, detail=f"Unknown policy: {name}")
    return factory(params)
