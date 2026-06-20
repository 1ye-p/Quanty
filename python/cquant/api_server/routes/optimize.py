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


class SectorLimitSchema(BaseModel):
    min_weight: float = 0.0
    max_weight: float = 1.0


class FactorExposureLimitSchema(BaseModel):
    min_exposure: float = -1.0
    max_exposure: float = 1.0


class ConstraintConfigSchema(BaseModel):
    """Pydantic schema mirroring ConstraintConfig for API input."""

    # Weight bounds
    long_only: bool = True
    max_weight: float = 1.0
    min_weight: float = 0.0
    min_weights: dict[str, float] = Field(default_factory=dict)
    max_weights: dict[str, float] = Field(default_factory=dict)

    # Turnover
    max_turnover: float | None = None
    turnover_penalty: float = 0.0
    current_weights: dict[str, float] = Field(default_factory=dict)

    # Target return
    target_return: float | None = None

    # Sector limits
    sector_map: dict[str, str] = Field(default_factory=dict)
    sector_limits: dict[str, SectorLimitSchema] = Field(default_factory=dict)

    # Factor exposure limits
    factor_loadings: dict[str, dict[str, float]] = Field(default_factory=dict)
    factor_limits: dict[str, FactorExposureLimitSchema] = Field(default_factory=dict)

    # Tracking error
    max_tracking_error: float | None = None
    benchmark_weights: dict[str, float] = Field(default_factory=dict)

    # Asset exclusion
    exclude_assets: list[str] = Field(default_factory=list)
    exclude_st: bool = False
    st_assets: list[str] = Field(default_factory=list)
    exclude_suspended: bool = False
    suspended_assets: list[str] = Field(default_factory=list)


class ViewSpec(BaseModel):
    """Single investor view for Black-Litterman."""

    asset: str  # primary asset involved in the view
    against: str | None = None  # relative view: asset to go short (None = absolute)
    expected_return: float  # expected excess return for this view
    confidence: float = 0.5  # confidence in [0, 1]; 1 = certain, 0 = ignore


class OptimizeRequest(BaseModel):
    expected_returns: dict[str, float]  # asset_id -> expected annual return
    covariance: dict[str, dict[str, float]]  # asset_id -> {asset_id -> cov}
    optimizer: Literal["mean_variance", "risk_parity", "cost_aware", "black_litterman"] = "mean_variance"
    constraints: dict = Field(default_factory=dict)
    # Structured constraint config (takes precedence over `constraints` dict when provided)
    constraint_config: ConstraintConfigSchema | None = None
    # mean_variance / cost_aware params
    risk_free_rate: float = 0.0
    long_only: bool = True
    # cost_aware params
    cost_rate: float = 0.001
    turnover_penalty: float = 0.0005
    current_weights: dict[str, float] = Field(default_factory=dict)
    # black_litterman params
    market_weights: dict[str, float] | None = None
    views: list[ViewSpec] | None = None
    tau: float = 0.05
    risk_aversion: float = 2.5


class OptimizeResponse(BaseModel):
    weights: dict[str, float]
    expected_return: float
    expected_volatility: float
    sharpe_ratio: float
    metadata: dict


# ── Helpers ───────────────────────────────────────────────────────────────────


def _build_constraint_config(body: OptimizeRequest):  # noqa: C901
    """Build a ConstraintConfig from the request body.

    If `constraint_config` is provided it is used directly; otherwise we
    synthesise one from the flat `constraints` dict and top-level fields.
    """
    from cquant.portfolio_opt.constraints import (
        ConstraintConfig,
        FactorExposureLimit,
        SectorLimit,
    )

    if body.constraint_config is not None:
        cc = body.constraint_config
        sector_limits = {
            label: SectorLimit(min_weight=sl.min_weight, max_weight=sl.max_weight)
            for label, sl in cc.sector_limits.items()
        }
        factor_limits = {
            name: FactorExposureLimit(
                min_exposure=fl.min_exposure, max_exposure=fl.max_exposure
            )
            for name, fl in cc.factor_limits.items()
        }
        return ConstraintConfig(
            long_only=cc.long_only,
            max_weight=cc.max_weight,
            min_weight=cc.min_weight,
            min_weights=cc.min_weights,
            max_weights=cc.max_weights,
            max_turnover=cc.max_turnover,
            turnover_penalty=cc.turnover_penalty,
            current_weights=cc.current_weights,
            target_return=cc.target_return,
            sector_map=cc.sector_map,
            sector_limits=sector_limits,
            factor_loadings=cc.factor_loadings,
            factor_limits=factor_limits,
            max_tracking_error=cc.max_tracking_error,
            benchmark_weights=cc.benchmark_weights,
            exclude_assets=set(cc.exclude_assets),
            exclude_st=cc.exclude_st,
            st_assets=set(cc.st_assets),
            exclude_suspended=cc.exclude_suspended,
            suspended_assets=set(cc.suspended_assets),
        )

    # Fallback: synthesise from legacy dict + top-level fields
    con = dict(body.constraints)
    if body.current_weights:
        con.setdefault("current_weights", body.current_weights)
    con.setdefault("long_only", body.long_only)

    return ConstraintConfig(
        long_only=con.get("long_only", body.long_only),
        max_weight=con.get("max_weight", 1.0),
        min_weight=con.get("min_weight", 0.0),
        min_weights=con.get("min_weights", {}),
        max_weights=con.get("max_weights", {}),
        max_turnover=con.get("max_turnover"),
        turnover_penalty=con.get("turnover_penalty", 0.0),
        current_weights=con.get("current_weights", {}),
        target_return=con.get("target_return"),
        sector_map=con.get("sector_map", {}),
        sector_limits=con.get("sector_limits", {}),
        factor_loadings=con.get("factor_loadings", {}),
        factor_limits=con.get("factor_limits", {}),
        max_tracking_error=con.get("max_tracking_error"),
        benchmark_weights=con.get("benchmark_weights", {}),
        exclude_assets=set(con.get("exclude_assets", [])),
        exclude_st=con.get("exclude_st", False),
        st_assets=set(con.get("st_assets", [])),
        exclude_suspended=con.get("exclude_suspended", False),
        suspended_assets=set(con.get("suspended_assets", [])),
    )


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

    # Build and validate constraint config
    try:
        cfg = _build_constraint_config(body)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid constraint config: {exc}")

    errors = cfg.validate()
    if errors:
        raise HTTPException(
            status_code=422,
            detail="Constraint validation failed: " + "; ".join(errors),
        )

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
    elif body.optimizer == "black_litterman":
        from cquant.portfolio_opt.black_litterman import BlackLittermanOptimizer

        optimizer = BlackLittermanOptimizer(
            risk_aversion=body.risk_aversion,
            tau=body.tau,
            risk_free_rate=body.risk_free_rate,
            long_only=body.long_only,
        )
    else:
        raise HTTPException(status_code=422, detail=f"Unknown optimizer: {body.optimizer}")

    try:
        import numpy as np

        opt_kwargs: dict = {
            "expected_returns": body.expected_returns,
            "covariance": body.covariance,
            "constraints": cfg,
        }

        # Black-Litterman extra arguments
        if body.optimizer == "black_litterman":
            n = len(body.covariance)
            assets = sorted(body.covariance.keys())
            asset_idx = {a: i for i, a in enumerate(assets)}

            opt_kwargs["market_weights"] = body.market_weights

            # Convert views to P matrix and Q vector
            if body.views:
                k = len(body.views)
                P = np.zeros((k, n))
                Q = np.zeros(k)
                confidences = np.zeros(k)
                for vi, view in enumerate(body.views):
                    if view.asset not in asset_idx:
                        raise HTTPException(
                            status_code=422,
                            detail=f"View asset {view.asset!r} not found in covariance matrix",
                        )
                    P[vi, asset_idx[view.asset]] = 1.0
                    if view.against is not None:
                        if view.against not in asset_idx:
                            raise HTTPException(
                                status_code=422,
                                detail=f"View 'against' asset {view.against!r} not found in covariance matrix",
                            )
                        P[vi, asset_idx[view.against]] = -1.0
                    Q[vi] = view.expected_return
                    confidences[vi] = view.confidence
                opt_kwargs["views_P"] = P
                opt_kwargs["views_Q"] = Q
                opt_kwargs["view_confidences"] = confidences

        result = optimizer.optimize(**opt_kwargs)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
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
