"""cquant.scheduler.runner — Job execution runner."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Callable

from cquant.scheduler.scheduler import ScheduleConfig, StrategyScheduler

logger = logging.getLogger(__name__)


class JobRunner:
    """Execute scheduled jobs.

    Works with StrategyScheduler to run jobs at their scheduled times.

    Usage::

        scheduler = StrategyScheduler()
        scheduler.add_job(config, callback)
        runner = JobRunner(scheduler)
        runner.check_and_run()  # Run any due jobs
    """

    def __init__(self, scheduler: StrategyScheduler) -> None:
        self._scheduler = scheduler
        self._running = False

    def check_and_run(self) -> list[str]:
        """Check for due jobs and run them.

        Returns:
            List of job IDs that were run
        """
        now = datetime.now()
        run_jobs = []

        for job in self._scheduler.get_all_jobs():
            if self._scheduler.should_run(job.job_id, now):
                status = self._scheduler.get_status(job.job_id)
                if status and status.status != "running":
                    logger.info("Running job %s", job.job_id)
                    if self._scheduler.run_job(job.job_id):
                        run_jobs.append(job.job_id)

        return run_jobs

    def run_all(self) -> dict[str, bool]:
        """Run all enabled jobs immediately.

        Returns:
            Dict of job_id -> success status
        """
        results = {}
        for job in self._scheduler.get_all_jobs():
            if job.enabled:
                results[job.job_id] = self._scheduler.run_job(job.job_id)
        return results

    def run_job(self, job_id: str) -> bool:
        """Run a specific job.

        Args:
            job_id: Job ID to run

        Returns:
            True if job started successfully
        """
        return self._scheduler.run_job(job_id)
