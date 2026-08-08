"""cquant.datahub.pipelines.valuation_daily_updater — Daily valuation data updater.

Usage::

    from cquant.datahub.pipelines.valuation_daily_updater import (
        ValuationDailyUpdater,
        register_valuation_daily_job,
    )
    from cquant.scheduler import StrategyScheduler

    updater = ValuationDailyUpdater(catalog, connector)
    updater.update(asset_ids, trade_date)

    # Or register with scheduler:
    scheduler = StrategyScheduler()
    register_valuation_daily_job(scheduler, catalog, connector)
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cquant.datahub.catalog import Catalog
    from cquant.datahub.connectors.tushare_connector import TushareConnector
    from cquant.scheduler.scheduler import StrategyScheduler

logger = logging.getLogger(__name__)


class ValuationDailyUpdater:
    """Daily incremental update for silver_valuation_daily.

    Operates on a single trade_date per invocation (latest trading day),
    independent of the quarterly fundamentals_updater rhythm.
    Designed for scheduler daily task registration.
    """

    def __init__(self, catalog: "Catalog", connector: "TushareConnector") -> None:
        self.catalog = catalog
        self.connector = connector

    def update(self, asset_ids: list[str], trade_date: str) -> int:
        """Fetch and upsert valuation data for all *asset_ids* on *trade_date*.

        Parameters
        ----------
        asset_ids
            List of Tushare ts_code values (e.g. ``['000001.SZ', '600000.SH']``).
        trade_date
            Trading date in ``YYYYMMDD`` or ``YYYY-MM-DD`` format.

        Returns
        -------
        int
            Number of assets with non-empty data written.
        """
        written = 0
        for ts_code in asset_ids:
            try:
                df = self.connector.fetch_valuation_daily(ts_code, trade_date, trade_date)
                if len(df) > 0:
                    self.catalog.upsert("silver_valuation_daily", df)
                    written += 1
            except Exception as exc:
                logger.warning(
                    "ValuationDailyUpdater: failed to update %s on %s: %s",
                    ts_code, trade_date, exc,
                )
        logger.info(
            "ValuationDailyUpdater: updated %d/%d assets for %s",
            written, len(asset_ids), trade_date,
        )
        return written


def _load_asset_ids(catalog: "Catalog") -> list[str]:
    """Load all asset IDs from silver_assets."""
    try:
        df = catalog.query("SELECT DISTINCT asset_id FROM silver_assets LIMIT 5000")
        return df["asset_id"].to_list() if not df.is_empty() else []
    except Exception as exc:
        logger.warning("valuation_daily_updater: failed to load asset list: %s", exc)
        return []


def register_valuation_daily_job(
    scheduler: "StrategyScheduler",
    catalog: "Catalog",
    connector: "TushareConnector",
    run_hour: int = 18,
    run_minute: int = 10,
) -> None:
    """Register a daily valuation update job with the scheduler.

    Scheduled 10 minutes after fundamentals update (default 18:10 CST).

    Parameters
    ----------
    scheduler
        StrategyScheduler instance.
    catalog
        DuckDB Catalog instance.
    connector
        TushareConnector instance.
    run_hour
        Hour (24h) for daily run (default 18 — after market close).
    run_minute
        Minute for daily run (default 10).
    """
    from cquant.scheduler.scheduler import ScheduleConfig, ScheduleFrequency  # noqa: PLC0415

    config = ScheduleConfig(
        job_id="daily_valuation_update",
        strategy_id="__system__",
        frequency=ScheduleFrequency.DAILY,
        run_time=time(run_hour, run_minute),
        enabled=True,
        metadata={"type": "data_update"},
    )

    updater = ValuationDailyUpdater(catalog, connector)

    def _callback() -> None:
        asset_ids = _load_asset_ids(catalog)
        if not asset_ids:
            logger.warning("valuation_daily_updater: no assets found, skipping")
            return
        trade_date = date.today().isoformat()
        updater.update(asset_ids, trade_date)

    scheduler.add_job(config, _callback)
    logger.info(
        "valuation_daily_updater: registered daily job at %02d:%02d",
        run_hour, run_minute,
    )
