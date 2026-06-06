"""Dataset catalog routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks

from cquant.api_server.deps import CatalogDep
from cquant.api_server.schemas.common import UniverseCreateBody

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/datasets", tags=["datasets"])

_UNIVERSE_DDL = """
CREATE TABLE IF NOT EXISTS meta_custom_universes (
    universe_id VARCHAR PRIMARY KEY,
    name        VARCHAR NOT NULL,
    asset_ids   VARCHAR NOT NULL,
    filter_type VARCHAR DEFAULT 'custom',
    filter_value VARCHAR DEFAULT '',
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""
_universe_table_ensured = False


def _ensure_universe_table(catalog) -> None:
    global _universe_table_ensured
    if _universe_table_ensured:
        return
    try:
        catalog.execute(_UNIVERSE_DDL)
        _universe_table_ensured = True
    except Exception as exc:
        logger.debug("_ensure_universe_table: %s", exc)


@router.get("")
async def list_datasets(catalog: CatalogDep, limit: int = 50) -> dict:
    """List registered dataset versions."""
    df = catalog.query(
        "SELECT version_id, dataset_name, frequency, start_date, end_date, "
        "asset_count, row_count, source, created_at, is_current "
        "FROM silver_dataset_versions "
        "ORDER BY created_at DESC LIMIT ?",
        [limit],
    )
    return {"items": df.to_dicts(), "total": df.height}


@router.get("/quality")
async def get_dataset_quality(
    catalog: CatalogDep,
    version: str = "",
    sample_assets: int = 20,
) -> dict:
    """返回数据集的数据质量报告。"""
    import polars as pl

    has_version_col = False
    if version:
        try:
            catalog.execute("SELECT dataset_version FROM silver_prices_1d LIMIT 1")
            has_version_col = True
        except Exception:
            pass

    ver_cond = "AND dataset_version = ?" if has_version_col and version else ""
    ver_params = [version] if has_version_col and version else []

    basic_df = catalog.query(
        f"SELECT COUNT(DISTINCT asset_id) as n_assets, "
        f"MIN(trade_date) as min_date, "
        f"MAX(trade_date) as max_date, "
        f"COUNT(*) as total_rows "
        f"FROM silver_prices_1d WHERE 1=1 {ver_cond}",
        ver_params,
    )
    stats = basic_df.to_dicts()[0] if not basic_df.is_empty() else {}

    recent_df = catalog.query(
        f"SELECT COUNT(DISTINCT asset_id) as recent_assets "
        f"FROM silver_prices_1d "
        f"WHERE trade_date >= CURRENT_DATE - INTERVAL '30 days' {ver_cond}",
        ver_params,
    )
    stats["recent_assets"] = (
        recent_df.to_dicts()[0].get("recent_assets", 0) if not recent_df.is_empty() else 0
    )

    null_df = catalog.query(
        f"SELECT "
        f"  CAST(SUM(CASE WHEN close IS NULL THEN 1 ELSE 0 END) AS DOUBLE) / COUNT(*) as null_rate "
        f"FROM silver_prices_1d WHERE 1=1 {ver_cond}",
        ver_params,
    )
    stats["null_rate"] = (
        null_df.to_dicts()[0].get("null_rate") or 0.0 if not null_df.is_empty() else 0.0
    )

    try:
        outlier_df = catalog.query(
            f"SELECT COUNT(*) as n_outliers FROM ("
            f"  SELECT ABS(close / LAG(close) OVER (PARTITION BY asset_id ORDER BY trade_date) - 1) as dr "
            f"  FROM silver_prices_1d WHERE 1=1 {ver_cond}"
            f") t WHERE dr > 0.25",
            ver_params,
        )
        stats["outlier_count"] = (
            outlier_df.to_dicts()[0].get("n_outliers", 0) if not outlier_df.is_empty() else 0
        )
    except Exception:
        stats["outlier_count"] = 0

    daily_df = catalog.query(
        f"SELECT trade_date, COUNT(DISTINCT asset_id) as n_assets "
        f"FROM silver_prices_1d "
        f"WHERE trade_date >= CURRENT_DATE - INTERVAL '30 days' {ver_cond} "
        f"GROUP BY trade_date ORDER BY trade_date",
        ver_params,
    )
    daily_coverage = (
        [{"trade_date": str(r["trade_date"]), "n_assets": r["n_assets"]}
         for r in daily_df.to_dicts()]
        if not daily_df.is_empty()
        else []
    )

    bottom_df = catalog.query(
        f"SELECT asset_id, COUNT(*) as valid_days "
        f"FROM silver_prices_1d "
        f"WHERE trade_date >= CURRENT_DATE - INTERVAL '90 days' {ver_cond} "
        f"GROUP BY asset_id ORDER BY valid_days ASC LIMIT ?",
        ver_params + [sample_assets],
    )
    bottom_assets = bottom_df.to_dicts() if not bottom_df.is_empty() else []

    return {
        "version": version or "all",
        "stats": stats,
        "daily_coverage": daily_coverage,
        "bottom_assets": bottom_assets,
    }


@router.get("/universes")
async def list_universes(catalog: CatalogDep) -> dict:
    """列出可用的股票池。"""
    predefined = [
        {"id": "all", "name": "全部股票", "description": "不限制股票池"},
        {"id": "sse", "name": "沪市主板", "description": "仅上海证券交易所主板"},
        {"id": "szse", "name": "深市主板", "description": "仅深圳证券交易所主板"},
        {"id": "cyb", "name": "创业板", "description": "深圳创业板 (300xxx)"},
        {"id": "kcb", "name": "科创板", "description": "上海科创板 (688xxx)"},
        {"id": "bse", "name": "北交所", "description": "北京证券交易所 (8xxxxx)"},
        {"id": "idx_sse", "name": "上证指数成分股", "description": "上海证券交易所综合指数成分股"},
        {"id": "idx_szse", "name": "深证成指成分股", "description": "深圳证券交易所成份指数成分股"},
        {"id": "idx_hs300", "name": "沪深300", "description": "沪深300指数成分股（大盘蓝筹）"},
        {"id": "idx_zz500", "name": "中证500", "description": "中证500指数成分股（中盘成长）"},
        {"id": "idx_zz1000", "name": "中证1000", "description": "中证1000指数成分股（小盘）"},
        {"id": "idx_cyb", "name": "创业板指", "description": "创业板指数成分股 (399006)"},
        {"id": "idx_kcb50", "name": "科创50", "description": "上证科创板50成分指数"},
    ]
    try:
        count_df = catalog.query(
            "SELECT COUNT(DISTINCT asset_id) AS n FROM silver_prices_1d "
            "WHERE trade_date >= CURRENT_DATE - INTERVAL '30 days'"
        )
        total_assets = int(count_df["n"][0]) if not count_df.is_empty() else 0
    except Exception:
        total_assets = 0
    return {
        "predefined": predefined,
        "total_assets": total_assets,
    }


@router.post("/universes")
async def create_universe(body: UniverseCreateBody, catalog: CatalogDep) -> dict:
    """创建自定义股票池。"""
    import json
    import uuid

    _ensure_universe_table(catalog)
    universe_id = f"custom_{uuid.uuid4().hex[:8]}"
    catalog.execute(
        "INSERT INTO meta_custom_universes (universe_id, name, asset_ids, filter_type, filter_value) "
        "VALUES (?, ?, ?, ?, ?)",
        [universe_id, body.name, json.dumps(body.asset_ids), body.filter_type, body.filter_value],
    )
    return {"universe_id": universe_id, "name": body.name}


@router.get("/schedule")
async def get_schedule_status(catalog: CatalogDep) -> dict:
    """返回数据调度状态。"""
    from cquant.api_server.data_scheduler import get_scheduler_state
    state = get_scheduler_state()
    # 同时返回 freshness（最后一次 silver 数据日期）
    try:
        df = catalog.query("SELECT MAX(trade_date) as d FROM silver_prices_1d")
        last_data = str(df["d"][0]) if not df.is_empty() and df["d"][0] else None
    except Exception:
        last_data = None
    return {**state, "last_data_date": last_data}


@router.post("/schedule/trigger")
async def trigger_ingest(background_tasks: BackgroundTasks, catalog: CatalogDep) -> dict:
    """手动触发一次增量摄取。"""
    from cquant.api_server.data_scheduler import run_incremental_ingest, get_scheduler_state, mark_scheduler_running
    if get_scheduler_state().get("last_status") == "running":
        return {"status": "already_running"}
    # Set running BEFORE enqueuing to prevent TOCTOU race on concurrent requests
    mark_scheduler_running()
    background_tasks.add_task(run_incremental_ingest, catalog)
    return {"status": "triggered"}


@router.get("/freshness")
async def get_data_freshness(catalog: CatalogDep) -> dict:
    """返回最近一次数据更新时间和距今天数。"""
    try:
        df = catalog.query("SELECT MAX(trade_date) as last_date FROM silver_prices_1d")
        if df.is_empty() or df["last_date"][0] is None:
            return {"last_updated": None, "days_stale": -1}
        last_date = str(df["last_date"][0])
        from datetime import date
        days_stale = (date.today() - date.fromisoformat(last_date)).days
        return {"last_updated": last_date, "days_stale": days_stale}
    except Exception as exc:
        logger.debug("get_data_freshness failed: %s", exc)
        return {"last_updated": None, "days_stale": -1}


@router.get("/backtest-trend")
async def get_backtest_trend(catalog: CatalogDep, days: int = 30) -> dict:
    """返回近 N 天每日回测数量趋势。"""
    try:
        df = catalog.query(
            "SELECT DATE(started_at) as date, COUNT(*) as count "
            "FROM meta_backtest_runs "
            "WHERE started_at >= CURRENT_DATE - INTERVAL '? days' "
            "GROUP BY DATE(started_at) "
            "ORDER BY date",
            [days],
        )
        items = [
            {"date": str(r["date"]), "count": r["count"]}
            for r in df.to_dicts()
        ] if not df.is_empty() else []
        return {"items": items, "days": days}
    except Exception as exc:
        logger.debug("get_backtest_trend failed: %s", exc)
        return {"items": [], "days": days}


@router.get("/{version_id}")
async def get_dataset(version_id: str, catalog: CatalogDep) -> dict:
    """Get a specific dataset version."""
    df = catalog.query(
        "SELECT * FROM silver_dataset_versions WHERE version_id = ?",
        [version_id],
    )
    if df.is_empty():
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Dataset version '{version_id}' not found")
    return df.to_dicts()[0]
