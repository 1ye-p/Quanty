"""cquant.api_server.routes.live — Real-time monitoring and quotes.

Supports both:
- Real-time quotes via AKShare
- Historical backtest data (display mode)
"""

from __future__ import annotations

import asyncio
import json
import logging
import pathlib
import re
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from cquant.api_server.deps import CatalogDep

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/live", tags=["live"])

_DISPLAY_BANNER = "⚠️ 模拟展示模式：数据来自历史回测，非真实交易数据"

_ARTIFACTS_BASE = pathlib.Path("data/backtest_artifacts").resolve()
_UUID_RE = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')


def _safe_metrics_path(run_id: str) -> pathlib.Path | None:
    if not _UUID_RE.match(run_id):
        return None
    p = (_ARTIFACTS_BASE / f"{run_id}.json").resolve()
    if not str(p).startswith(str(_ARTIFACTS_BASE)):
        return None
    return p


_live_table_ensured = False


def _ensure_live_table(catalog) -> None:
    """幂等创建模拟策略表（进程内只执行一次）。"""
    global _live_table_ensured
    if _live_table_ensured:
        return
    try:
        catalog.execute("""
            CREATE TABLE IF NOT EXISTS meta_live_strategies (
                live_id         VARCHAR PRIMARY KEY,
                backtest_run_id VARCHAR NOT NULL,
                strategy_id     VARCHAR NOT NULL,
                initial_cash    DOUBLE DEFAULT 1000000,
                risk_mode       VARCHAR DEFAULT 'conservative',
                status          VARCHAR DEFAULT 'active',
                deployed_at     TIMESTAMP NOT NULL,
                stopped_at      TIMESTAMP
            )
        """)
        _live_table_ensured = True
    except Exception as exc:
        import logging
        logging.getLogger(__name__).debug("_ensure_live_table: %s", exc)


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


# ── Live Strategy Deployment ───────────────────────────────────────────────────

class DeployRequest(BaseModel):
    backtest_run_id: str
    initial_cash: float = Field(default=1_000_000, gt=0)
    risk_mode: str = "conservative"


@router.post("/deploy", status_code=201)
async def deploy_strategy(body: DeployRequest, catalog: CatalogDep) -> dict:
    """将回测结果部署为模拟策略。"""
    import uuid as _uuid

    run_df = catalog.query(
        "SELECT run_id, strategy_id, status FROM gold_backtest_runs WHERE run_id = ?",
        [body.backtest_run_id],
    )
    if run_df.is_empty():
        raise HTTPException(status_code=404, detail=f"Backtest run '{body.backtest_run_id}' not found")
    if run_df["status"][0] != "completed":
        raise HTTPException(status_code=422, detail="Only completed backtest runs can be deployed")

    strategy_id = run_df["strategy_id"][0]
    _ensure_live_table(catalog)

    existing = catalog.query(
        "SELECT live_id FROM meta_live_strategies "
        "WHERE backtest_run_id = ? AND status = 'active'",
        [body.backtest_run_id],
    )
    if not existing.is_empty():
        raise HTTPException(status_code=409, detail="This backtest run is already deployed and active")

    live_id = f"live_{_uuid.uuid4().hex[:10]}"
    now = datetime.now(tz=timezone.utc).isoformat()
    catalog.execute(
        "INSERT INTO meta_live_strategies "
        "(live_id, backtest_run_id, strategy_id, initial_cash, risk_mode, status, deployed_at) "
        "VALUES (?, ?, ?, ?, ?, 'active', ?)",
        [live_id, body.backtest_run_id, strategy_id,
         body.initial_cash, body.risk_mode, now],
    )
    return {
        "live_id": live_id,
        "strategy_id": strategy_id,
        "status": "active",
        "deployed_at": now,
    }


@router.post("/strategies/{live_id}/stop")
async def stop_live_strategy(live_id: str, catalog: CatalogDep) -> dict:
    """停止模拟策略。"""
    _ensure_live_table(catalog)
    existing = catalog.query(
        "SELECT live_id, status FROM meta_live_strategies WHERE live_id = ?",
        [live_id],
    )
    if existing.is_empty():
        raise HTTPException(status_code=404, detail=f"Live strategy '{live_id}' not found")
    if existing["status"][0] != "active":
        raise HTTPException(status_code=409, detail="Strategy is not active")
    catalog.execute(
        "UPDATE meta_live_strategies SET status = 'stopped', stopped_at = ? WHERE live_id = ?",
        [datetime.now(tz=timezone.utc).isoformat(), live_id],
    )
    return {"live_id": live_id, "status": "stopped"}


@router.get("/deployed")
async def list_deployed_strategies(catalog: CatalogDep) -> dict:
    """列出所有已部署的模拟策略（含回测指标摘要）。"""
    _ensure_live_table(catalog)
    df = catalog.query(
        "SELECT ls.live_id, ls.strategy_id, ls.backtest_run_id, ls.initial_cash, "
        "ls.risk_mode, ls.status, ls.deployed_at, ls.stopped_at "
        "FROM meta_live_strategies ls ORDER BY ls.deployed_at DESC"
    )
    if df.is_empty():
        return {"items": []}
    items = []
    for row in df.to_dicts():
        metrics: dict = {}
        mpath = _safe_metrics_path(row["backtest_run_id"])
        if mpath and mpath.exists():
            try:
                m = json.loads(mpath.read_text())
                metrics = {
                    "sharpe": m.get("sharpe_ratio"),
                    "max_drawdown": m.get("max_drawdown"),
                    "cagr": m.get("cagr"),
                }
            except Exception:
                pass
        items.append({**row, "metrics": metrics})
    return {"items": items}
