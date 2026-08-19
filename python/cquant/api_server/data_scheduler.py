"""DataScheduler — 每日自动增量摄取行情数据。"""
from cquant.core.errors import IngestError

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
}
_SCHEDULER_INSTANCE: Any = None  # set by start_data_scheduler()


def mark_scheduler_running() -> None:
    """Mark the scheduler as running (called before enqueuing a trigger job)."""
    _SCHEDULER_STATE["last_status"] = "running"


def get_scheduler_state() -> dict:
    state = dict(_SCHEDULER_STATE)
    # Dynamically read next_run_time so it stays fresh after each job fires
    try:
        if _SCHEDULER_INSTANCE is not None:
            job = _SCHEDULER_INSTANCE.get_job("daily_ingest")
            state["next_run"] = job.next_run_time.isoformat() if job and job.next_run_time else None
        else:
            state["next_run"] = None
    except Exception:
        state["next_run"] = None
    return state


def run_incremental_ingest(catalog) -> None:
    """执行增量摄取：从 silver_prices_1d 找最新日期，拉取到今日。"""
    _SCHEDULER_STATE["last_status"] = "running"
    _SCHEDULER_STATE["last_run"] = datetime.now(tz=timezone.utc).isoformat()
    try:
        from cquant.datahub.ingest import MarketIngestionOrchestrator, IngestionSpec
        from cquant.datahub.connectors.akshare_connector import AKShareConnector
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
        from cquant.core.enums import Market, Frequency
        import time
        
        # 尝试多个数据源，按优先级排序
        connectors = []
        
        # 1. 优先尝试 Tushare（如果配置了 token）
        try:
            from cquant.datahub.connectors.tushare_connector import TushareConnector
            import os
            if os.environ.get("TUSHARE_TOKEN"):
                connectors.append(("tushare", TushareConnector()))
                logger.info("DataScheduler: Tushare connector available")
        except Exception as e:
            logger.debug("DataScheduler: Tushare not available: %s", e)
        
        # 2. 尝试 AKShare
        try:
            from cquant.datahub.connectors.akshare_connector import AKShareConnector
            connectors.append(("akshare", AKShareConnector()))
            logger.info("DataScheduler: AKShare connector available")
        except Exception as e:
            logger.debug("DataScheduler: AKShare not available: %s", e)
        
        if not connectors:
            raise IngestError("No data connectors available")
        
        # 逐个尝试数据源
        last_error = None
        for name, connector in connectors:
            try:
                logger.info("DataScheduler: trying %s connector", name)
                orchestrator = MarketIngestionOrchestrator(catalog, [connector])
                spec = IngestionSpec(
                    market=Market.CN,
                    symbols=[],
                    start_date=start_date,
                    end_date=end_date,
                    frequency=Frequency.D1,
                )
                orchestrator.ingest(spec)
                logger.info("DataScheduler: %s connector succeeded", name)
                break
            except Exception as e:
                last_error = e
                logger.warning("DataScheduler: %s connector failed: %s", name, e)
                if name != connectors[-1][0]:
                    logger.info("DataScheduler: waiting 5s before trying next connector...")
                    time.sleep(5)
        else:
            raise IngestError(f"All connectors failed. Last error: {last_error}")
        _SCHEDULER_STATE["last_status"] = "success"
        _SCHEDULER_STATE["last_error"] = None
        logger.info("DataScheduler: ingest completed")
    except Exception as e:
        logger.exception("DataScheduler: ingest failed")
        _SCHEDULER_STATE["last_status"] = "error"
        _SCHEDULER_STATE["last_error"] = repr(e)[:200]


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
    global _SCHEDULER_INSTANCE
    _SCHEDULER_INSTANCE = scheduler

    job = scheduler.get_job("daily_ingest")
    next_run = job.next_run_time.isoformat() if job and job.next_run_time else None
    logger.info("DataScheduler started, next run: %s", next_run)
    return scheduler
