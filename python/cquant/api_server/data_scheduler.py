"""DataScheduler — 每日自动增量摄取行情数据。"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

_SCHEDULER_STATE: dict[str, Any] = {
    "enabled": True,
    "last_run": None,      # ISO datetime str
    "last_status": None,   # "success" | "error" | "running"
    "last_error": None,
    "next_run": None,      # ISO datetime str
}


def get_scheduler_state() -> dict:
    return dict(_SCHEDULER_STATE)


def run_incremental_ingest(catalog) -> None:
    """执行增量摄取：从 silver_prices_1d 找最新日期，拉取到今日。"""
    _SCHEDULER_STATE["last_status"] = "running"
    _SCHEDULER_STATE["last_run"] = datetime.now(tz=timezone.utc).isoformat()
    try:
        from cquant.datahub.ingest import MarketIngestionOrchestrator, IngestionSpec
        from cquant.datahub.connectors.akshare_connector import AkShareConnector
        from datetime import date

        # 找上次摄取的最新日期
        latest_df = catalog.query("SELECT MAX(trade_date) as last_date FROM silver_prices_1d")
        if latest_df.is_empty() or latest_df["last_date"][0] is None:
            start_date = date.today() - timedelta(days=30)
        else:
            start_date = latest_df["last_date"][0] + timedelta(days=1)

        end_date = date.today()
        if start_date > end_date:
            logger.info("DataScheduler: data is up to date, skipping ingest")
            _SCHEDULER_STATE["last_status"] = "success"
            return

        logger.info("DataScheduler: ingesting %s ~ %s", start_date, end_date)
        orchestrator = MarketIngestionOrchestrator(catalog, [AkShareConnector()])
        orchestrator.ingest(IngestionSpec(start_date=start_date, end_date=end_date))
        _SCHEDULER_STATE["last_status"] = "success"
        _SCHEDULER_STATE["last_error"] = None
        logger.info("DataScheduler: ingest completed")
    except Exception as e:
        logger.exception("DataScheduler: ingest failed")
        _SCHEDULER_STATE["last_status"] = "error"
        _SCHEDULER_STATE["last_error"] = str(e)[:200]


def start_data_scheduler(catalog) -> Any:
    """启动 APScheduler，注册每日 16:35 的摄取任务。"""
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        logger.warning("APScheduler not installed; data auto-scheduler disabled")
        return None

    scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")
    scheduler.add_job(
        run_incremental_ingest,
        CronTrigger(hour=16, minute=35, timezone="Asia/Shanghai"),
        id="daily_ingest",
        args=[catalog],
        replace_existing=True,
    )
    scheduler.start()

    # 计算下次运行时间
    job = scheduler.get_job("daily_ingest")
    if job and job.next_run_time:
        _SCHEDULER_STATE["next_run"] = job.next_run_time.isoformat()

    logger.info("DataScheduler started, next run: %s", _SCHEDULER_STATE["next_run"])
    return scheduler
