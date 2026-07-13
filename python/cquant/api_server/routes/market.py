"""Market data routes."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Query

from cquant.api_server.deps import CatalogDep

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/market", tags=["market"])


@router.get("/prices")
async def get_prices(
    asset_id: str = Query(..., description="Asset ID, e.g. SSE:600036"),
    start: str = Query(..., description="Start date YYYY-MM-DD", pattern=r"^\d{4}-\d{2}-\d{2}$"),
    end: str = Query(..., description="End date YYYY-MM-DD", pattern=r"^\d{4}-\d{2}-\d{2}$"),
    period: str = Query("daily", description="K-line period: daily, weekly, monthly", pattern=r"^(daily|weekly|monthly)$"),
    catalog: CatalogDep = None,
):
    """Get OHLCV price data with summary statistics."""
    if period == "weekly":
        sql = """
            SELECT
                date_trunc('week', trade_date)::DATE AS trade_date,
                (ARRAY_AGG(open ORDER BY trade_date))[1] AS open,
                MAX(high) AS high,
                MIN(low) AS low,
                (ARRAY_AGG(close ORDER BY trade_date DESC))[1] AS close,
                SUM(volume) AS volume
            FROM silver_prices_1d
            WHERE asset_id = $1 AND trade_date BETWEEN $2 AND $3
            GROUP BY date_trunc('week', trade_date)
            ORDER BY 1
        """
    elif period == "monthly":
        sql = """
            SELECT
                date_trunc('month', trade_date)::DATE AS trade_date,
                (ARRAY_AGG(open ORDER BY trade_date))[1] AS open,
                MAX(high) AS high,
                MIN(low) AS low,
                (ARRAY_AGG(close ORDER BY trade_date DESC))[1] AS close,
                SUM(volume) AS volume
            FROM silver_prices_1d
            WHERE asset_id = $1 AND trade_date BETWEEN $2 AND $3
            GROUP BY date_trunc('month', trade_date)
            ORDER BY 1
        """
    else:
        sql = """
            SELECT trade_date, open, high, low, close, volume
            FROM silver_prices_1d
            WHERE asset_id = $1 AND trade_date BETWEEN $2 AND $3
            ORDER BY trade_date
        """
    df = catalog.query(sql, [asset_id, start, end])
    prices = df.to_dicts()

    # Compute summary stats
    stats = {}
    if prices:
        closes = [p["close"] for p in prices]
        volumes = [p["volume"] for p in prices]
        prev_close = closes[-2] if len(closes) > 1 and closes[-2] != 0 else None
        stats = {
            "latest_price": closes[-1],
            "change_pct": (closes[-1] - prev_close) / prev_close if prev_close else 0,
            "high_in_range": max(closes),
            "low_in_range": min(closes),
            "avg_volume": sum(volumes) / len(volumes) if volumes else 0,
        }
    return {"asset_id": asset_id, "prices": prices, "stats": stats}


@router.get("/assets")
async def search_assets(
    q: str = Query(..., min_length=2, description="Search keyword (min 2 chars)"),
    limit: int = Query(20, ge=1, le=100),
    catalog: CatalogDep = None,
):
    """Search assets by ID or name."""
    df = catalog.query(
        "SELECT asset_id, name, exchange FROM silver_assets "
        "WHERE asset_id ILIKE ? OR name ILIKE ? "
        "ORDER BY asset_id LIMIT ?",
        [f"%{q}%", f"%{q}%", limit],
    )
    return {"assets": df.to_dicts()}
