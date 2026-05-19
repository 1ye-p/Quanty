"""cquant.api_server.routes.live — Real-time monitoring and quotes.

Supports both:
- Real-time quotes via AKShare
- Historical backtest data (display mode)
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

from cquant.api_server.deps import CatalogDep

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/live", tags=["live"])

_DISPLAY_BANNER = "⚠️ 模拟展示模式：数据来自历史回测，非真实交易数据"


# ── Real-time Quote Endpoints ──────────────────────────────────────────────────


@router.get("/quote/{symbol}")
async def get_quote(symbol: str) -> dict[str, Any]:
    """Get real-time quote for a single symbol."""
    from cquant.datahub.connectors.realtime_connector import QuoteFeed

    feed = QuoteFeed()
    try:
        quotes = await run_in_threadpool(feed.get_quotes, [symbol])
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch quote: {exc}")

    if symbol not in quotes:
        raise HTTPException(status_code=404, detail=f"No quote available for {symbol}")

    return quotes[symbol].to_dict()


@router.get("/quotes")
async def get_quotes(symbols: str = "") -> dict[str, Any]:
    """Get real-time quotes for multiple symbols (comma-separated)."""
    from cquant.datahub.connectors.realtime_connector import QuoteFeed

    if not symbols:
        raise HTTPException(status_code=400, detail="Provide ?symbols=600036,000001")

    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()][:20]  # Cap at 20
    feed = QuoteFeed()
    try:
        quotes = await run_in_threadpool(feed.get_quotes, symbol_list)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch quotes: {exc}")

    return {
        "items": {s: q.to_dict() for s, q in quotes.items()},
        "count": len(quotes),
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
    }


@router.get("/market")
async def get_market_snapshot(limit: int = Query(20, ge=1, le=200)) -> dict[str, Any]:
    """Get market-wide quote snapshot."""
    from cquant.datahub.connectors.realtime_connector import QuoteFeed

    feed = QuoteFeed()
    try:
        quotes = await run_in_threadpool(feed.get_all_quotes, limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch market snapshot: {exc}")

    return {
        "items": {s: q.to_dict() for s, q in quotes.items()},
        "count": len(quotes),
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
    }


# ── SSE Stream ─────────────────────────────────────────────────────────────────


@router.get("/stream")
async def live_stream(
    request: Request,
    symbols: str = "",
    interval: float = Query(5.0, ge=1.0, le=60.0),
):
    """SSE endpoint for real-time quote streaming.

    Args:
        symbols: Comma-separated stock codes
        interval: Update interval in seconds (default 5, min 1, max 60)
    """
    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()][:20] if symbols else []

    async def event_generator():
        from cquant.datahub.connectors.realtime_connector import QuoteFeed
        feed = QuoteFeed()

        while True:
            # Check if client disconnected
            if await request.is_disconnected():
                break

            try:
                if symbol_list:
                    quotes = await run_in_threadpool(feed.get_quotes, symbol_list)
                else:
                    quotes = await run_in_threadpool(feed.get_all_quotes, 10)

                data = {
                    "type": "quotes",
                    "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                    "items": {s: q.to_dict() for s, q in quotes.items()},
                }
                yield f"data: {json.dumps(data)}\n\n"
            except Exception as exc:
                logger.error("SSE error: %s", exc)
                yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

            await asyncio.sleep(interval)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Historical Backtest Data (display mode) ────────────────────────────────────


@router.get("/strategies")
async def list_live_strategies(catalog: CatalogDep) -> dict:
    """List strategies that have at least one completed backtest run."""
    df = catalog.query(
        """
        SELECT strategy_id, run_id AS last_run_id, completed_at AS last_update, status
        FROM gold_backtest_runs
        WHERE status = 'completed'
          AND (strategy_id, completed_at) IN (
              SELECT strategy_id, MAX(completed_at)
              FROM gold_backtest_runs
              WHERE status = 'completed'
              GROUP BY strategy_id
          )
        ORDER BY last_update DESC
        """
    )
    return {
        "items": df.to_dicts(),
        "total": df.height,
        "display_mode": _DISPLAY_BANNER,
    }


@router.get("/strategies/{strategy_id}/pnl")
async def strategy_pnl(
    strategy_id: str,
    catalog: CatalogDep,
    from_date: str | None = None,
    to_date: str | None = None,
) -> dict:
    """Return PnL time series from the most recent backtest run."""
    run_df = catalog.query(
        "SELECT run_id FROM gold_backtest_runs WHERE strategy_id = ? AND status = 'completed' "
        "ORDER BY completed_at DESC LIMIT 1",
        [strategy_id],
    )
    if run_df.is_empty():
        raise HTTPException(status_code=404, detail=f"No completed runs for strategy '{strategy_id}'")

    run_id = run_df["run_id"].item()
    conditions = ["run_id = ?"]
    params: list = [run_id]
    if from_date:
        conditions.append("snapshot_ts >= ?")
        params.append(from_date)
    if to_date:
        conditions.append("snapshot_ts <= ?")
        params.append(to_date)

    where = " AND ".join(conditions)
    params.append(500)
    snap_df = catalog.query(
        f"SELECT snapshot_ts, drawdown, gross_leverage, net_leverage, var_95 "
        f"FROM gold_risk_snapshots WHERE {where} ORDER BY snapshot_ts LIMIT ?",
        params,
    )

    return {
        "strategy_id": strategy_id,
        "run_id": run_id,
        "series": snap_df.to_dicts(),
        "display_mode": _DISPLAY_BANNER,
    }


@router.get("/strategies/{strategy_id}/positions")
async def strategy_positions(strategy_id: str, catalog: CatalogDep) -> dict:
    """Return latest simulated positions from the most recent backtest."""
    run_df = catalog.query(
        "SELECT run_id FROM gold_backtest_runs WHERE strategy_id = ? AND status = 'completed' "
        "ORDER BY completed_at DESC LIMIT 1",
        [strategy_id],
    )
    if run_df.is_empty():
        raise HTTPException(status_code=404, detail=f"No completed runs for strategy '{strategy_id}'")
    run_id = run_df["run_id"].item()

    sig_df = catalog.query(
        "SELECT asset_id, trade_date, signal, target_weight "
        "FROM gold_signals WHERE strategy_id = ? "
        "ORDER BY trade_date DESC LIMIT 50",
        [strategy_id],
    )
    return {
        "strategy_id": strategy_id,
        "run_id": run_id,
        "items": sig_df.to_dicts(),
        "display_mode": _DISPLAY_BANNER,
    }


@router.get("/strategies/{strategy_id}/risk")
async def strategy_risk(strategy_id: str, catalog: CatalogDep) -> dict:
    """Return latest risk snapshot for a strategy."""
    df = catalog.query(
        "SELECT * FROM gold_risk_snapshots WHERE strategy_id = ? ORDER BY snapshot_ts DESC LIMIT 1",
        [strategy_id],
    )
    history_df = catalog.query(
        "SELECT snapshot_ts, drawdown, gross_leverage, var_95 "
        "FROM gold_risk_snapshots WHERE strategy_id = ? ORDER BY snapshot_ts DESC LIMIT 50",
        [strategy_id],
    )
    return {
        "latest_snapshot": df.to_dicts()[0] if not df.is_empty() else None,
        "history": history_df.to_dicts(),
        "display_mode": _DISPLAY_BANNER,
    }
