"""Technical indicator API routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from cquant.indicator import registry

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/indicators", tags=["indicators"])


@router.get("")
async def list_indicators(category: str | None = None) -> dict:
    """List all available indicators, optionally filtered by category."""
    specs = registry.list_indicators(category)
    return {
        "indicators": [
            {
                "name": s.name,
                "category": s.category,
                "description": s.description,
                "params": [
                    {"name": p[0], "type": p[1].__name__, "default": p[2]}
                    for p in s.params
                ],
            }
            for s in specs
        ],
        "total": len(specs),
    }


@router.get("/categories")
async def list_categories() -> dict:
    """List indicator categories with counts."""
    all_specs = registry.list_indicators()
    categories: dict[str, list[str]] = {}
    for s in all_specs:
        categories.setdefault(s.category, []).append(s.name)
    return {
        "categories": {
            k: {"count": len(v), "indicators": v} for k, v in categories.items()
        }
    }


class IndicatorParam(BaseModel):
    """A single indicator to compute."""

    name: str
    params: dict = Field(default_factory=dict)


class ComputeBody(BaseModel):
    """Request body for /indicators/compute."""

    data: list[dict]
    indicators: list[IndicatorParam]


@router.post("/compute")
async def compute_indicators(body: ComputeBody) -> dict:
    """Compute indicators on provided OHLCV data."""
    import polars as pl

    if not body.data:
        raise HTTPException(status_code=400, detail="data must not be empty")
    if len(body.data) > 50_000:
        raise HTTPException(status_code=400, detail="data exceeds maximum 50,000 rows")
    if not body.indicators:
        raise HTTPException(status_code=400, detail="indicators must not be empty")

    df = pl.DataFrame(body.data)
    ind_list = [{"name": i.name, "params": i.params} for i in body.indicators]

    try:
        result = registry.compute(df, ind_list)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.exception("Indicator compute failed")
        raise HTTPException(status_code=400, detail=str(exc))

    return {"columns": result.columns, "rows": result.to_dicts()}


@router.get("/ohlcv/{asset_id}")
async def get_ohlcv(
    asset_id: str,
    catalog: CatalogDep,
    days: int = Query(default=252, ge=1, le=1000),
) -> dict:
    """Get OHLCV data for an asset for indicator preview."""
    df = catalog.query(
        "SELECT trade_date, open, high, low, close, volume "
        "FROM silver_prices_1d WHERE asset_id = ? "
        "ORDER BY trade_date DESC LIMIT ?",
        [asset_id, days],
    )
    if df.is_empty():
        return {"asset_id": asset_id, "data": [], "count": 0}
    rows = df.sort("trade_date").to_dicts()
    return {"asset_id": asset_id, "data": rows, "count": len(rows)}
