"""Risk management API routes."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Literal

import numpy as np
import polars as pl
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from scipy import stats

from cquant.api_server.deps import CatalogDep

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


class PortfolioVarRequest(BaseModel):
    """Request parameters for portfolio VaR calculation."""
    method: Literal["parametric", "historical", "monte_carlo"] = "parametric"
    confidence: float = Field(default=0.95, ge=0.9, le=0.999)
    horizon_days: int = Field(default=1, ge=1, le=30)
    # Portfolio context (optional, uses placeholder if not provided)
    weights: dict[str, float] = Field(default_factory=dict, description="Asset weights {asset_id: weight}")
    nav: float = Field(default=1_000_000.0, description="Portfolio NAV")
    # Historical data (optional)
    returns_data: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Historical returns [{date, asset_id, return}]"
    )


class PortfolioVarResponse(BaseModel):
    """Response for portfolio VaR calculation."""
    var: float
    cvar: float
    method: str
    confidence: float
    portfolio_nav: float
    horizon_days: int
    var_amount: float  # VaR in currency terms
    cvar_amount: float  # CVaR in currency terms


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


@router.get("/portfolio-var", response_model=PortfolioVarResponse)
async def portfolio_var(
    method: Literal["parametric", "historical", "monte_carlo"] = "parametric",
    confidence: float = 0.95,
    horizon_days: int = 1,
    weights_json: str = "",
    nav: float = 1_000_000.0,
) -> dict:
    """Calculate portfolio-level Value at Risk (VaR) and Conditional VaR (CVaR).

    Supports three methods:
    - **parametric**: Assumes normal distribution of returns. VaR = z * sqrt(w' * Sigma * w) * sqrt(horizon)
    - **historical**: Uses historical portfolio returns quantile
    - **monte_carlo**: Simulates portfolio returns using multivariate normal distribution

    Args:
        method: VaR calculation method
        confidence: Confidence level (0.9 to 0.999)
        horizon_days: Time horizon in days (1 to 30)
        weights_json: JSON string of asset weights {"asset_id": weight}
        nav: Portfolio Net Asset Value

    Returns:
        VaR and CVR as percentages and in currency terms
    """
    import json

    # Parse weights
    if weights_json:
        try:
            weights = json.loads(weights_json)
        except json.JSONDecodeError:
            raise HTTPException(status_code=422, detail="Invalid weights_json format")
    else:
        # Use placeholder equal weights for demo
        weights = {"asset_1": 0.3, "asset_2": 0.3, "asset_3": 0.4}

    if not weights:
        raise HTTPException(status_code=422, detail="No weights provided")

    # Normalize weights
    total_weight = sum(weights.values())
    if abs(total_weight) < 1e-10:
        raise HTTPException(status_code=422, detail="Total weight is zero")
    if abs(total_weight - 1.0) > 0.01:
        weights = {k: v / total_weight for k, v in weights.items()}

    # Get historical returns
    # TODO: Fetch real historical returns from datahub using asset_ids
    # Currently uses synthetic data with realistic parameters for demonstration
    n_assets = len(weights)
    n_days = 252  # 1 year of history
    rng = np.random.default_rng(42)  # Local RNG to avoid global state pollution

    mean_returns = np.full(n_assets, 0.10 / 252)  # Daily mean return ~10% annual
    base_vol = 0.20 / np.sqrt(252)  # Daily vol ~20% annualized
    cov_matrix = np.eye(n_assets) * base_vol**2
    for i in range(n_assets):
        for j in range(i+1, n_assets):
            cov_matrix[i, j] = 0.3 * base_vol**2
            cov_matrix[j, i] = 0.3 * base_vol**2

    historical_returns = rng.multivariate_normal(mean_returns, cov_matrix, n_days)

    # Calculate VaR based on method
    w = np.array([weights[k] for k in sorted(weights.keys())])

    if method == "parametric":
        var_pct, cvar_pct = _parametric_var(w, cov_matrix, confidence, horizon_days)
    elif method == "historical":
        var_pct, cvar_pct = _historical_var(w, historical_returns, confidence, horizon_days)
    elif method == "monte_carlo":
        var_pct, cvar_pct = _monte_carlo_var(w, mean_returns, cov_matrix, confidence, horizon_days)
    else:
        raise HTTPException(status_code=422, detail=f"Unknown method: {method}")

    # Convert to currency terms
    var_amount = var_pct * nav
    cvar_amount = cvar_pct * nav

    return {
        "var": float(var_pct),
        "cvar": float(cvar_pct),
        "method": method,
        "confidence": confidence,
        "portfolio_nav": nav,
        "horizon_days": horizon_days,
        "var_amount": float(var_amount),
        "cvar_amount": float(cvar_amount),
    }


def _parametric_var(
    weights: np.ndarray,
    cov_matrix: np.ndarray,
    confidence: float,
    horizon_days: int,
) -> tuple[float, float]:
    """Calculate parametric VaR assuming normal distribution.

    VaR = z * sqrt(w' * Sigma * w) * sqrt(horizon)
    CVaR = (phi(z) / (1 - confidence)) * sigma * sqrt(horizon)
    """
    # Portfolio variance: w' * Sigma * w
    port_variance = weights @ cov_matrix @ weights
    port_vol_daily = np.sqrt(port_variance)

    # Scale to horizon
    port_vol_horizon = port_vol_daily * np.sqrt(horizon_days)

    # z-score for confidence level
    z = stats.norm.ppf(1 - confidence)

    # Parametric VaR (positive number representing loss)
    var_pct = abs(z * port_vol_horizon)

    # Parametric CVaR (Expected Shortfall)
    # CVaR = (phi(z) / (1 - confidence)) * sigma
    phi_z = stats.norm.pdf(z)
    cvar_pct = (phi_z / (1 - confidence)) * port_vol_horizon

    return float(var_pct), float(cvar_pct)


def _historical_var(
    weights: np.ndarray,
    historical_returns: np.ndarray,
    confidence: float,
    horizon_days: int,
) -> tuple[float, float]:
    """Calculate historical simulation VaR.

    1. Compute portfolio returns: r_p = w' * r_assets
    2. For multi-day horizon, sum returns over rolling windows
    3. Take quantile at (1 - confidence)
    """
    # Portfolio returns for each day
    port_returns = historical_returns @ weights

    if horizon_days > 1:
        # Aggregate returns over rolling horizon windows
        n_days = len(port_returns)
        horizon_returns = np.array([
            np.sum(port_returns[i:i+horizon_days])
            for i in range(n_days - horizon_days + 1)
        ])
    else:
        horizon_returns = port_returns

    # Sort returns (ascending - worst losses first)
    sorted_returns = np.sort(horizon_returns)

    # VaR at (1 - confidence) quantile
    var_idx = int(np.floor((1 - confidence) * len(sorted_returns)))
    var_pct = abs(sorted_returns[var_idx]) if var_idx < len(sorted_returns) else abs(sorted_returns[-1])

    # CVaR: mean of returns worse than VaR
    cvar_returns = sorted_returns[:var_idx + 1]
    cvar_pct = abs(np.mean(cvar_returns)) if len(cvar_returns) > 0 else var_pct

    return float(var_pct), float(cvar_pct)


def _monte_carlo_var(
    weights: np.ndarray,
    mean_returns: np.ndarray,
    cov_matrix: np.ndarray,
    confidence: float,
    horizon_days: int,
    n_simulations: int = 10000,
) -> tuple[float, float]:
    """Calculate Monte Carlo VaR.

    1. Simulate N paths using multivariate normal distribution
    2. Compute portfolio returns for each simulation
    3. Take quantile of simulated returns
    """
    # Simulate daily returns for all assets
    simulated_daily = np.random.multivariate_normal(mean_returns, cov_matrix, (n_simulations, horizon_days))

    # Sum over horizon for each simulation
    simulated_horizon = np.sum(simulated_daily, axis=1)  # Shape: (n_simulations,)

    # Compute portfolio returns: w' * r_assets for each simulation
    port_returns = simulated_horizon @ weights

    # Sort returns
    sorted_returns = np.sort(port_returns)

    # VaR at (1 - confidence) quantile
    var_idx = int(np.floor((1 - confidence) * n_simulations))
    var_pct = abs(sorted_returns[var_idx]) if var_idx < n_simulations else abs(sorted_returns[-1])

    # CVaR: mean of returns worse than VaR
    cvar_returns = sorted_returns[:var_idx + 1]
    cvar_pct = abs(np.mean(cvar_returns)) if len(cvar_returns) > 0 else var_pct

    return float(var_pct), float(cvar_pct)


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


# ── Factor Decomposition ─────────────────────────────────────────────────────


class FactorDecompositionResponse(BaseModel):
    """Response for portfolio factor risk decomposition."""

    style_exposures: dict[str, float] = Field(
        description="Style factor exposures (market_cap, value, momentum, volatility, turnover, quality)"
    )
    industry_exposures: dict[str, float] = Field(
        description="Industry factor exposures (Shenwan Level-1 industry weights)"
    )
    risk_decomposition: dict[str, Any] = Field(
        description="Risk decomposition with total_risk, factor_risk, idiosyncratic_risk, "
        "factor_risk_pct, and per-factor risk contributions"
    )


@router.get("/factor-decomposition", response_model=FactorDecompositionResponse)
async def get_factor_decomposition(
    catalog: CatalogDep,
    weights_json: str = "",
    nav: float = 1_000_000.0,
    as_of_date: str = "",
) -> dict:
    """Compute portfolio factor risk decomposition (Barra-style).

    Decomposes portfolio risk into systematic (factor) and idiosyncratic
    components using a simplified Barra-style factor model.

    **Style factors:** market_cap (ln), value (1/PB), momentum (20d return),
    volatility (60d std), turnover, quality (ROE).

    **Industry factors:** Shenwan Level-1 industry dummies from silver_assets.

    Args:
        weights_json: JSON string of asset weights ``{"asset_id": weight}``.
        nav: Portfolio Net Asset Value (informational, not used in risk math).
        as_of_date: ISO date for data cutoff (optional, uses latest data).

    Returns:
        Style exposures, industry exposures, and risk decomposition breakdown.
    """
    # Parse weights
    if not weights_json:
        raise HTTPException(
            status_code=422,
            detail="weights_json is required. Provide a JSON string of {asset_id: weight}.",
        )

    try:
        weights = json.loads(weights_json)
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="Invalid weights_json format")

    if not isinstance(weights, dict) or not weights:
        raise HTTPException(
            status_code=422,
            detail="weights_json must be a non-empty dict of {asset_id: weight}",
        )
    for k, v in weights.items():
        if not isinstance(v, (int, float)):
            raise HTTPException(
                status_code=422,
                detail=f"Weight for '{k}' must be numeric, got {type(v).__name__}",
            )

    # Normalise weights if they don't sum to ~1
    total_w = sum(weights.values())
    if abs(total_w) > 1e-12 and abs(total_w - 1.0) > 0.01:
        weights = {k: float(v) / total_w for k, v in weights.items()}

    # Run factor decomposition
    from cquant.riskguard.factor_decomposition import run_factor_decomposition

    try:
        result = run_factor_decomposition(
            catalog=catalog,
            weights=weights,
            as_of_date=as_of_date or None,
        )
    except Exception as exc:
        logger.exception("Factor decomposition failed")
        raise HTTPException(status_code=500, detail=f"Factor decomposition failed: {exc}")

    return result
