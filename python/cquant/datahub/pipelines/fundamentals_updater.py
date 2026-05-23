"""cquant.datahub.pipelines.fundamentals_updater — 基本面数据定时更新。

Usage::

    from cquant.datahub.pipelines.fundamentals_updater import register_fundamentals_job
    from cquant.scheduler import StrategyScheduler

    scheduler = StrategyScheduler()
    register_fundamentals_job(scheduler, catalog)
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cquant.datahub.catalog import Catalog
    from cquant.scheduler import StrategyScheduler

logger = logging.getLogger(__name__)


def update_fundamentals(
    catalog: "Catalog",
    source: str = "tushare",
    asset_ids: list[str] | None = None,
) -> int:
    """从指定数据源拉取基本面数据并写入 silver_fundamentals。

    Parameters
    ----------
    catalog
        已初始化的 DuckDB Catalog 实例。
    source
        数据源：'tushare'（默认）或 'akshare'。
    asset_ids
        要更新的资产 ID 列表；传 None 时从 silver_assets 查询所有已有资产。

    Returns
    -------
    int
        成功写入/更新的行数。
    """
    if asset_ids is None:
        asset_ids = _load_asset_ids(catalog)

    if not asset_ids:
        logger.warning("fundamentals_updater: no assets found, skipping update")
        return 0

    today = date.today().isoformat()
    now = datetime.now(tz=timezone.utc).isoformat()

    if source == "tushare":
        rows_written = _update_from_tushare(catalog, asset_ids, today, now)
    elif source == "akshare":
        rows_written = _update_from_akshare(catalog, asset_ids, today, now)
    else:
        raise ValueError(f"Unsupported fundamentals source: {source!r}. Use 'tushare' or 'akshare'.")

    logger.info(
        "fundamentals_updater: updated %d rows from %s on %s",
        rows_written, source, today,
    )
    return rows_written


def _load_asset_ids(catalog: "Catalog") -> list[str]:
    """Load all asset IDs from silver_assets."""
    try:
        df = catalog.query("SELECT DISTINCT asset_id FROM silver_assets LIMIT 5000")
        return df["asset_id"].to_list() if not df.is_empty() else []
    except Exception as exc:
        logger.warning("fundamentals_updater: failed to load asset list: %s", exc)
        return []


def _update_from_tushare(
    catalog: "Catalog",
    asset_ids: list[str],
    report_date: str,
    updated_at: str,
) -> int:
    """Fetch fundamentals from Tushare and upsert into silver_fundamentals."""
    try:
        from cquant.datahub.connectors.tushare_connector import TushareConnector  # noqa: PLC0415
        connector = TushareConnector()
        records = connector.fetch_fundamentals(asset_ids=asset_ids, date=report_date)
    except (ImportError, AttributeError) as exc:
        logger.warning(
            "fundamentals_updater: TushareConnector.fetch_fundamentals unavailable (%s)", exc
        )
        records = []

    if not records:
        return 0

    return _upsert_records(catalog, records, updated_at)


def _update_from_akshare(
    catalog: "Catalog",
    asset_ids: list[str],
    report_date: str,
    updated_at: str,
) -> int:
    """Fetch fundamentals from AKShare and upsert into silver_fundamentals."""
    try:
        import akshare as ak  # noqa: PLC0415
    except ImportError:
        logger.warning("fundamentals_updater: akshare not installed")
        return 0

    records = []
    for asset_id in asset_ids[:100]:  # rate-limit: max 100 per run
        symbol = asset_id.split(":")[-1] if ":" in asset_id else asset_id
        try:
            df = ak.stock_financial_abstract(symbol=symbol)
            if df is not None and not df.empty:
                records.append({
                    "asset_id": asset_id,
                    "report_date": report_date,
                    "source": "akshare",
                    "updated_at": updated_at,
                })
        except Exception:
            continue

    if not records:
        return 0

    return _upsert_records(catalog, records, updated_at)


def _upsert_records(catalog: "Catalog", records: list[dict], updated_at: str) -> int:
    """Upsert records into silver_fundamentals via INSERT OR REPLACE."""
    if not records:
        return 0

    written = 0
    for rec in records:
        try:
            catalog.execute(
                """
                INSERT OR REPLACE INTO silver_fundamentals
                    (asset_id, report_date, pe_ttm, pb, ps_ttm, ev_ebitda, dividend_yield,
                     roe, roa, gross_margin, net_margin, revenue_growth_yoy,
                     earnings_growth_yoy, market_cap, total_assets, total_debt,
                     source, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    rec.get("asset_id"),
                    rec.get("report_date"),
                    rec.get("pe_ttm"),
                    rec.get("pb"),
                    rec.get("ps_ttm"),
                    rec.get("ev_ebitda"),
                    rec.get("dividend_yield"),
                    rec.get("roe"),
                    rec.get("roa"),
                    rec.get("gross_margin"),
                    rec.get("net_margin"),
                    rec.get("revenue_growth_yoy"),
                    rec.get("earnings_growth_yoy"),
                    rec.get("market_cap"),
                    rec.get("total_assets"),
                    rec.get("total_debt"),
                    rec.get("source", "unknown"),
                    updated_at,
                ],
            )
            written += 1
        except Exception as exc:
            logger.warning(
                "fundamentals_updater: failed to upsert %s: %s",
                rec.get("asset_id"), exc,
            )

    return written


def register_fundamentals_job(
    scheduler: "StrategyScheduler",
    catalog: "Catalog",
    source: str = "tushare",
    run_hour: int = 18,
    run_minute: int = 0,
) -> None:
    """Register a daily fundamentals update job with the scheduler.

    Parameters
    ----------
    scheduler
        StrategyScheduler instance.
    catalog
        DuckDB Catalog instance.
    source
        Data source ('tushare' or 'akshare').
    run_hour
        Hour (24h) for daily run (default 18 — after market close).
    run_minute
        Minute for daily run (default 0).
    """
    from cquant.scheduler.scheduler import ScheduleConfig, ScheduleFrequency  # noqa: PLC0415

    config = ScheduleConfig(
        job_id="daily_fundamentals_update",
        strategy_id="__system__",
        frequency=ScheduleFrequency.DAILY,
        run_time=time(run_hour, run_minute),
        enabled=True,
        metadata={"source": source, "type": "data_update"},
    )

    def _callback() -> None:
        update_fundamentals(catalog, source=source)

    scheduler.add_job(config, _callback)
    logger.info(
        "fundamentals_updater: registered daily job at %02d:%02d using source '%s'",
        run_hour, run_minute, source,
    )
