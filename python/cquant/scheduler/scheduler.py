"""cquant.scheduler.scheduler — Strategy scheduling."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, time
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


class ScheduleFrequency(Enum):
    """Schedule frequency options."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"


@dataclass
class ScheduleConfig:
    """Configuration for a scheduled job."""
    job_id: str
    strategy_id: str
    frequency: ScheduleFrequency
    run_time: time = time(9, 30)  # Default: 9:30 AM
    days_of_week: list[int] = field(default_factory=lambda: [0, 1, 2, 3, 4])  # Mon-Fri
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class JobStatus:
    """Status of a scheduled job."""
    job_id: str
    strategy_id: str
    last_run: datetime | None = None
    next_run: datetime | None = None
    status: str = "idle"  # "idle", "running", "completed", "failed"
    error: str | None = None
    run_count: int = 0


class StrategyScheduler:
    """Schedule and manage strategy execution.

    Usage::

        scheduler = StrategyScheduler()
        scheduler.add_job(ScheduleConfig(
            job_id='daily_momentum',
            strategy_id='top10_momentum',
            frequency=ScheduleFrequency.DAILY,
            run_time=time(9, 30),
        ))
        scheduler.start()
    """

    def __init__(self) -> None:
        self._jobs: dict[str, ScheduleConfig] = {}
        self._status: dict[str, JobStatus] = {}
        self._callbacks: dict[str, Callable] = {}

    def add_job(self, config: ScheduleConfig, callback: Callable | None = None) -> None:
        """Add a scheduled job.

        Args:
            config: Schedule configuration
            callback: Function to call when job runs
        """
        self._jobs[config.job_id] = config
        self._status[config.job_id] = JobStatus(
            job_id=config.job_id,
            strategy_id=config.strategy_id,
        )
        if callback:
            self._callbacks[config.job_id] = callback

        logger.info("Added job %s for strategy %s", config.job_id, config.strategy_id)

    def remove_job(self, job_id: str) -> None:
        """Remove a scheduled job."""
        self._jobs.pop(job_id, None)
        self._status.pop(job_id, None)
        self._callbacks.pop(job_id, None)
        logger.info("Removed job %s", job_id)

    def get_job(self, job_id: str) -> ScheduleConfig | None:
        """Get job configuration."""
        return self._jobs.get(job_id)

    def get_status(self, job_id: str) -> JobStatus | None:
        """Get job status."""
        return self._status.get(job_id)

    def get_all_jobs(self) -> list[ScheduleConfig]:
        """Get all scheduled jobs."""
        return list(self._jobs.values())

    def get_all_status(self) -> list[JobStatus]:
        """Get status of all jobs."""
        return list(self._status.values())

    def enable_job(self, job_id: str) -> None:
        """Enable a scheduled job."""
        if job_id in self._jobs:
            self._jobs[job_id].enabled = True

    def disable_job(self, job_id: str) -> None:
        """Disable a scheduled job."""
        if job_id in self._jobs:
            self._jobs[job_id].enabled = False

    def should_run(self, job_id: str, current_time: datetime) -> bool:
        """Check if a job should run at the given time.

        Args:
            job_id: Job ID
            current_time: Current datetime

        Returns:
            True if job should run
        """
        config = self._jobs.get(job_id)
        if not config or not config.enabled:
            return False

        # Check day of week
        if config.frequency == ScheduleFrequency.WEEKLY:
            if current_time.weekday() not in config.days_of_week:
                return False

        # Check time
        current_time_only = current_time.time()
        # Allow 5-minute window
        run_minutes = config.run_time.hour * 60 + config.run_time.minute
        current_minutes = current_time_only.hour * 60 + current_time_only.minute
        return abs(current_minutes - run_minutes) <= 5

    def run_job(self, job_id: str) -> bool:
        """Execute a job.

        Args:
            job_id: Job ID to run

        Returns:
            True if job started successfully
        """
        config = self._jobs.get(job_id)
        if not config:
            return False

        status = self._status.get(job_id)
        if not status:
            return False

        if status.status == "running":
            logger.warning("Job %s is already running", job_id)
            return False

        # Update status
        status.status = "running"
        status.last_run = datetime.now()

        # Execute callback
        callback = self._callbacks.get(job_id)
        if callback:
            try:
                callback(config)
                status.status = "completed"
                status.run_count += 1
                logger.info("Job %s completed successfully", job_id)
            except Exception as exc:
                status.status = "failed"
                status.error = str(exc)
                logger.exception("Job %s failed: %s", job_id, exc)
                return False
        else:
            status.status = "completed"
            status.run_count += 1
            logger.info("Job %s completed (no callback)", job_id)

        return True
