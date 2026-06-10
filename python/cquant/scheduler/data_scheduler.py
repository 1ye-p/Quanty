"""cquant.scheduler.data_scheduler — APScheduler-based data pipeline scheduler.

Runs four recurring jobs:
  1. Price ingest       — daily at 16:35 CST
  2. Fundamentals update — daily at 17:00 CST
  3. Alert check        — hourly
  4. Health check       — daily at 08:00 CST
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Callable

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Retry helper
# ---------------------------------------------------------------------------

def _with_retry(
    fn: Callable[..., Any],
    *args: Any,
    max_retries: int = 3,
    base_delay: float = 2.0,
    **kwargs: Any,
) -> Any:
    """Call *fn* with exponential-backoff retry.

    Parameters
    ----------
    fn
        Callable to invoke.
    *args, **kwargs
        Forwarded to *fn*.
    max_retries
        Maximum number of retry attempts (default 3).
    base_delay
        Initial delay in seconds; doubled on each retry.

    Returns
    -------
    Any
        Return value of *fn* on success.

    Raises
    ------
    Exception
        Re-raises the last exception after all retries exhausted.
    """
    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            last_exc = exc
            delay = base_delay * (2 ** (attempt - 1))
            logger.warning(
                "Attempt %d/%d failed (%s), retrying in %.1fs ...",
                attempt, max_retries, exc, delay,
            )
            time.sleep(delay)
    raise last_exc  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Job implementations
# ---------------------------------------------------------------------------

def _job_price_ingest(catalog: Any) -> None:
    """Incremental price ingestion: latest silver date -> today."""
    from cquant.core.enums import Frequency, Market
    from cquant.datahub.ingest import IngestionSpec, MarketIngestionOrchestrator
    from cquant.datahub.connectors.akshare_connector import AKShareConnector

    latest_df = catalog.query("SELECT MAX(trade_date) as last_date FROM silver_prices_1d")
    if latest_df.is_empty() or latest_df["last_date"][0] is None:
        from datetime import date, timedelta
        start_date = date.today() - timedelta(days=30)
    else:
        from datetime import date, timedelta
        start_date = latest_df["last_date"][0] + timedelta(days=1)

    from datetime import date
    end_date = date.today()
    if start_date > end_date:
        logger.info("DataScheduler: data is up to date, skipping price ingest")
        return

    logger.info("DataScheduler: price ingest %s -> %s", start_date, end_date)
    orchestrator = MarketIngestionOrchestrator(catalog, [AKShareConnector()])
    spec = IngestionSpec(
        market=Market.CN,
        symbols=[],  # empty = ingest all available
        start_date=start_date,
        end_date=end_date,
        frequency=Frequency.D1,
    )
    orchestrator.ingest(spec)
    logger.info("DataScheduler: price ingest completed")


def _job_fundamentals(catalog: Any) -> None:
    """Update fundamentals from the configured data source."""
    from cquant.datahub.pipelines.fundamentals_updater import update_fundamentals

    count = update_fundamentals(catalog, source="akshare")
    logger.info("DataScheduler: fundamentals updated (%d rows)", count)


def _job_alerts(catalog: Any) -> None:
    """Check for alert conditions (price limits, drawdown, etc.)."""
    logger.info("DataScheduler: alert check started")
    # Placeholder — integrate with riskguard alerts when available
    try:
        # Example: check for any positions exceeding risk thresholds
        df = catalog.query(
            "SELECT COUNT(*) AS cnt FROM gold_portfolio_snapshots "
            "WHERE trade_date = CURRENT_DATE"
        )
        if not df.is_empty():
            logger.info("DataScheduler: alert check completed, %d snapshots today", df["cnt"][0])
        else:
            logger.info("DataScheduler: alert check completed, no snapshots today")
    except Exception:
        logger.info("DataScheduler: alert check completed (no snapshot table)")


def _job_daily_prediction(catalog: Any) -> None:
    """Run daily prediction using the production model from the registry."""
    logger.info("DataScheduler: daily prediction started")
    try:
        from cquant.ml_lab.model_registry import ModelRegistry

        registry = ModelRegistry(catalog)

        # Find all production models
        prod_models = registry.list_models(stage="production")
        if not prod_models:
            logger.info("DataScheduler: no production models registered, skipping prediction")
            return

        from cquant.ml_lab.predict_service import run_online_prediction

        for model in prod_models:
            model_id = model["model_id"]
            model_version = model["model_version"]
            logger.info("DataScheduler: running prediction for %s (%s)", model_id, model_version)
            try:
                result = run_online_prediction(
                    catalog=catalog,
                    model_version=model_version,
                    top_n=50,
                )
                logger.info(
                    "DataScheduler: prediction completed for %s — %d assets, date=%s",
                    model_id, result.get("total_assets", 0), result.get("date", "unknown"),
                )
            except Exception as exc:
                logger.error("DataScheduler: prediction failed for %s: %s", model_id, exc)
    except Exception as exc:
        logger.error("DataScheduler: daily prediction job failed: %s", exc)


def _job_health(catalog: Any) -> None:
    """Daily health check: verify data freshness and table integrity."""
    logger.info("DataScheduler: health check started")
    checks: dict[str, str] = {}

    # Check silver_prices_1d freshness
    try:
        df = catalog.query("SELECT MAX(trade_date) AS latest FROM silver_prices_1d")
        if not df.is_empty() and df["latest"][0] is not None:
            checks["silver_prices_1d"] = f"latest={df['latest'][0]}"
        else:
            checks["silver_prices_1d"] = "EMPTY"
    except Exception as exc:
        checks["silver_prices_1d"] = f"ERROR: {exc}"

    # Check silver_fundamentals
    try:
        df = catalog.query("SELECT COUNT(*) AS cnt FROM silver_fundamentals")
        checks["silver_fundamentals"] = f"{df['cnt'][0]} rows"
    except Exception:
        checks["silver_fundamentals"] = "table missing"

    for table, status in checks.items():
        logger.info("  %-25s %s", table, status)

    logger.info("DataScheduler: health check completed")


# ---------------------------------------------------------------------------
# DataScheduler
# ---------------------------------------------------------------------------

class DataScheduler:
    """APScheduler-based scheduler for cQuant data pipelines.

    Parameters
    ----------
    catalog
        An initialised ``Catalog`` (DuckDB) instance.
    timezone
        IANA timezone string (default ``"Asia/Shanghai"``).
    """

    def __init__(self, catalog: Any, timezone: str = "Asia/Shanghai") -> None:
        self._catalog = catalog
        self._tz = timezone
        self._scheduler: Any = None
        self._running = False

        # Ensure run-tracking table exists
        try:
            self._catalog.execute(
                "CREATE TABLE IF NOT EXISTS _scheduler_runs "
                "(job_id VARCHAR, last_run TIMESTAMP, status VARCHAR)"
            )
        except Exception as exc:
            logger.warning("Failed to create _scheduler_runs table: %s", exc)

    # ---- public API -------------------------------------------------------

    def start(self) -> None:
        """Start the scheduler (blocking call)."""
        from apscheduler.schedulers.blocking import BlockingScheduler
        from apscheduler.triggers.cron import CronTrigger
        from apscheduler.triggers.interval import IntervalTrigger

        sched = BlockingScheduler(timezone=self._tz)

        # 1. Price ingest — daily at 16:35
        sched.add_job(
            self._run_price_ingest,
            CronTrigger(hour=16, minute=35, timezone=self._tz),
            id="price_ingest",
            name="Price Ingest",
            replace_existing=True,
        )

        # 2. Fundamentals — daily at 17:00
        sched.add_job(
            self._run_fundamentals,
            CronTrigger(hour=17, minute=0, timezone=self._tz),
            id="fundamentals",
            name="Fundamentals Update",
            replace_existing=True,
        )

        # 3. Alerts — daily at 18:00 (placeholder: logging only until riskguard integration)
        sched.add_job(
            self._run_alerts,
            CronTrigger(hour=18, minute=0, timezone=self._tz),
            id="alerts",
            name="Alert Check",
            replace_existing=True,
        )

        # 4. Health — daily at 08:00
        sched.add_job(
            self._run_health,
            CronTrigger(hour=8, minute=0, timezone=self._tz),
            id="health",
            name="Health Check",
            replace_existing=True,
        )

        # 5. Daily Prediction — daily at 18:05 (after market close + data ingest)
        sched.add_job(
            self._run_daily_prediction,
            CronTrigger(hour=18, minute=5, timezone=self._tz),
            id="daily_prediction",
            name="Daily Prediction",
            replace_existing=True,
        )

        self._scheduler = sched
        self._running = True
        logger.info("DataScheduler started with 5 jobs (tz=%s)", self._tz)

        try:
            sched.start()
        except (KeyboardInterrupt, SystemExit):
            self.stop()

    def stop(self) -> None:
        """Shut down the scheduler gracefully."""
        if self._scheduler is not None:
            self._scheduler.shutdown(wait=False)
            self._running = False
            logger.info("DataScheduler stopped")

    def status(self) -> dict[str, Any]:
        """Return a snapshot of scheduler state and job info."""
        jobs_info: list[dict[str, Any]] = []
        if self._scheduler is not None:
            for job in self._scheduler.get_jobs():
                jobs_info.append({
                    "id": job.id,
                    "name": job.name,
                    "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                })
        return {
            "running": self._running,
            "timezone": self._tz,
            "jobs": jobs_info,
        }

    def run_task(self, task_name: str) -> None:
        """Manually trigger a single task by name.

        Parameters
        ----------
        task_name
            One of ``price-ingest``, ``fundamentals``, ``alerts``, ``health``.
        """
        dispatch = {
            "price-ingest": self._run_price_ingest,
            "fundamentals": self._run_fundamentals,
            "alerts": self._run_alerts,
            "health": self._run_health,
            "daily-prediction": self._run_daily_prediction,
        }
        fn = dispatch.get(task_name)
        if fn is None:
            raise ValueError(
                f"Unknown task {task_name!r}. "
                f"Available: {', '.join(dispatch)}"
            )
        fn()

    # ---- internal runners -------------------------------------------------

    def _run_price_ingest(self) -> None:
        logger.info("Running price ingest ...")
        try:
            _with_retry(_job_price_ingest, self._catalog)
            self._record_run("price_ingest")
        except Exception as exc:
            logger.error("Price ingest failed after retries: %s", exc)
            self._record_run("price_ingest", "failure")

    def _run_fundamentals(self) -> None:
        logger.info("Running fundamentals update ...")
        try:
            _with_retry(_job_fundamentals, self._catalog)
            self._record_run("fundamentals")
        except Exception as exc:
            logger.error("Fundamentals update failed after retries: %s", exc)
            self._record_run("fundamentals", "failure")

    def _run_alerts(self) -> None:
        logger.info("Running alert check ...")
        try:
            _with_retry(_job_alerts, self._catalog)
            self._record_run("alerts")
        except Exception as exc:
            logger.error("Alert check failed after retries: %s", exc)
            self._record_run("alerts", "failure")

    def _run_health(self) -> None:
        logger.info("Running health check ...")
        try:
            _with_retry(_job_health, self._catalog)
            self._record_run("health")
        except Exception as exc:
            logger.error("Health check failed after retries: %s", exc)
            self._record_run("health", "failure")

    def _run_daily_prediction(self) -> None:
        logger.info("Running daily prediction ...")
        try:
            _with_retry(_job_daily_prediction, self._catalog)
            self._record_run("daily_prediction")
        except Exception as exc:
            logger.error("Daily prediction failed after retries: %s", exc)
            self._record_run("daily_prediction", "failure")

    def _record_run(self, job_id: str, status: str = "success") -> None:
        """Persist last-run metadata into the catalog (best-effort)."""
        try:
            self._catalog.execute(
                "INSERT INTO _scheduler_runs VALUES (?, ?, ?)",
                [job_id, datetime.now(tz=timezone.utc), status],
            )
        except Exception:
            logger.debug("Failed to record scheduler run for %s", job_id, exc_info=True)
