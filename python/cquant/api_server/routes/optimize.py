"""Portfolio optimization API routes."""

from __future__ import annotations

import logging
from datetime import date
from typing import Literal

import polars as pl
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from cquant.api_server.deps import CatalogDep

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/optimize", tags=["optimize"])


# ── Request / Response schemas ────────────────────────────────────────────────


class CovarianceRequest(BaseModel):
    asset_ids: list[str]
    as_of_date: str = ""  # ISO date, defaults to latest
    method: Literal["historical", "ewma", "ledoit_wolf"] = "historical"
    window: int = 252
    halflife: int = 63


class CovarianceResponse(BaseModel):
    covariance: dict[str, dict[str, float]]
    assets: list[str]
    method: str
    as_of_date: str


class OptimizeRequest(BaseModel):
    expected_returns: dict[str, float]  # asset_id -> expected annual return
    covariance: dict[str, dict[str, float]]  # asset_id -> {asset_id -> cov}
    optimizer: Literal["mean_variance", "risk_parity", "cost_aware"] = "mean_variance"
    constraints: dict = Field(default_factory=dict)
    # mean_variance / cost_aware params
    risk_free_rate: float = 0.0
    long_only: bool = True
    # cost_aware params
    cost_rate: float = 0.001
    turnover_penalty: float = 0.0005
    current_weights: dict[str, float] = Field(default_factory=dict)


class OptimizeResponse(BaseModel):
    weights: dict[str, float]
    expected_return: float
    expected_volatility: float
    sharpe_ratio: float
    metadata: dict


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("/covariance", response_model=CovarianceResponse)
async def compute_covariance(body: CovarianceRequest, catalog: CatalogDep) -> dict:
    """Compute covariance matrix for a set of assets from historical prices."""
    if not body.asset_ids:
        raise HTTPException(status_code=422, detail="asset_ids cannot be empty")

    placeholders = ",".join(["?" for _ in body.asset_ids])
    query = (
        f"SELECT asset_id, trade_date, close FROM gold_daily_prices "
        f"WHERE asset_id IN ({placeholders}) ORDER BY trade_date"
    )
    df = catalog.query(query, body.asset_ids)

    if df.is_empty():
        raise HTTPException(status_code=404, detail="No price data found for given assets")

    from cquant.portfolio_opt.covariance import CovarianceEstimator

    estimator = CovarianceEstimator(
        method=body.method,
        window=body.window,
        halflife=body.halflife,
    )

    as_of = date.fromisoformat(body.as_of_date) if body.as_of_date else None
    cov_matrix = estimator.estimate(df, as_of_date=as_of)

    return {
        "covariance": cov_matrix,
        "assets": sorted(cov_matrix.keys()),
        "method": body.method,
        "as_of_date": body.as_of_date or str(df["trade_date"].max()),
    }


@router.post("", response_model=OptimizeResponse)
async def optimize_portfolio(body: OptimizeRequest) -> dict:
    """Run portfolio optimization (MVO, Risk Parity, or Cost-Aware)."""
    if not body.expected_returns:
        raise HTTPException(status_code=422, detail="expected_returns cannot be empty")

    if body.optimizer == "mean_variance":
        from cquant.portfolio_opt.mean_variance import MeanVarianceOptimizer

        optimizer = MeanVarianceOptimizer(
            risk_free_rate=body.risk_free_rate,
            long_only=body.long_only,
        )
    elif body.optimizer == "risk_parity":
        from cquant.portfolio_opt.risk_parity import RiskParityOptimizer

        optimizer = RiskParityOptimizer()
    elif body.optimizer == "cost_aware":
        from cquant.portfolio_opt.cost_aware import CostAwareOptimizer

        optimizer = CostAwareOptimizer(
            risk_free_rate=body.risk_free_rate,
            long_only=body.long_only,
            cost_rate=body.cost_rate,
            turnover_penalty=body.turnover_penalty,
        )
    else:
        raise HTTPException(status_code=422, detail=f"Unknown optimizer: {body.optimizer}")

    constraints = dict(body.constraints)
    if body.current_weights:
        constraints["current_weights"] = body.current_weights

    try:
        result = optimizer.optimize(
            expected_returns=body.expected_returns,
            covariance=body.covariance,
            constraints=constraints or None,
        )
    except Exception as exc:
        logger.exception("Optimization failed")
        raise HTTPException(status_code=422, detail=f"Optimization failed: {exc}")

    return {
        "weights": result.weights,
        "expected_return": result.expected_return,
        "expected_volatility": result.expected_volatility,
        "sharpe_ratio": result.sharpe_ratio,
        "metadata": result.metadata,
    }
