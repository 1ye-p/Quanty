"""Unit tests for scheduler module."""

from __future__ import annotations

from datetime import datetime, time
from unittest.mock import MagicMock, patch

import pytest

from cquant.scheduler.health import HealthChecker, HealthStatus
from cquant.scheduler.runner import JobRunner
from cquant.scheduler.scheduler import (
    JobStatus,
    ScheduleConfig,
    ScheduleFrequency,
    StrategyScheduler,
)


class TestStrategyScheduler:
    """Tests for StrategyScheduler."""

    def test_add_job(self):
        scheduler = StrategyScheduler()
        config = ScheduleConfig(
            job_id="test-job",
            strategy_id="test-strategy",
            frequency=ScheduleFrequency.DAILY,
            run_time=time(9, 30),
        )
        scheduler.add_job(config)
        assert scheduler.get_job("test-job") is config

    def test_remove_job(self):
        scheduler = StrategyScheduler()
        config = ScheduleConfig(
            job_id="test-job",
            strategy_id="test-strategy",
            frequency=ScheduleFrequency.DAILY,
        )
        scheduler.add_job(config)
        scheduler.remove_job("test-job")
        assert scheduler.get_job("test-job") is None

    def test_enable_disable_job(self):
        scheduler = StrategyScheduler()
        config = ScheduleConfig(
            job_id="test-job",
            strategy_id="test-strategy",
            frequency=ScheduleFrequency.DAILY,
        )
        scheduler.add_job(config)

        scheduler.disable_job("test-job")
        assert not scheduler.get_job("test-job").enabled

        scheduler.enable_job("test-job")
        assert scheduler.get_job("test-job").enabled

    def test_should_run_within_window(self):
        scheduler = StrategyScheduler()
        config = ScheduleConfig(
            job_id="test-job",
            strategy_id="test-strategy",
            frequency=ScheduleFrequency.DAILY,
            run_time=time(9, 30),
        )
        scheduler.add_job(config)
        assert scheduler.should_run("test-job", datetime(2025, 1, 6, 9, 32))

    def test_should_run_outside_window(self):
        scheduler = StrategyScheduler()
        config = ScheduleConfig(
            job_id="test-job",
            strategy_id="test-strategy",
            frequency=ScheduleFrequency.DAILY,
            run_time=time(9, 30),
        )
        scheduler.add_job(config)
        assert not scheduler.should_run("test-job", datetime(2025, 1, 6, 10, 0))

    def test_should_run_disabled_job(self):
        scheduler = StrategyScheduler()
        config = ScheduleConfig(
            job_id="test-job",
            strategy_id="test-strategy",
            frequency=ScheduleFrequency.DAILY,
            enabled=False,
        )
        scheduler.add_job(config)
        assert not scheduler.should_run("test-job", datetime(2025, 1, 6, 9, 30))

    def test_should_run_weekly_wrong_day(self):
        scheduler = StrategyScheduler()
        config = ScheduleConfig(
            job_id="test-job",
            strategy_id="test-strategy",
            frequency=ScheduleFrequency.WEEKLY,
            run_time=time(9, 30),
            days_of_week=[0],  # Monday only
        )
        scheduler.add_job(config)
        # Tuesday
        assert not scheduler.should_run("test-job", datetime(2025, 1, 7, 9, 30))

    def test_run_job_executes_callback(self):
        scheduler = StrategyScheduler()
        config = ScheduleConfig(
            job_id="test-job",
            strategy_id="test-strategy",
            frequency=ScheduleFrequency.DAILY,
        )
        callback = MagicMock()
        scheduler.add_job(config, callback)

        result = scheduler.run_job("test-job")
        assert result is True
        callback.assert_called_once_with(config)

    def test_run_job_updates_status(self):
        scheduler = StrategyScheduler()
        config = ScheduleConfig(
            job_id="test-job",
            strategy_id="test-strategy",
            frequency=ScheduleFrequency.DAILY,
        )
        scheduler.add_job(config)

        scheduler.run_job("test-job")
        status = scheduler.get_status("test-job")
        assert status.status == "completed"
        assert status.run_count == 1

    def test_run_job_handles_exception(self):
        scheduler = StrategyScheduler()
        config = ScheduleConfig(
            job_id="test-job",
            strategy_id="test-strategy",
            frequency=ScheduleFrequency.DAILY,
        )
        callback = MagicMock(side_effect=RuntimeError("boom"))
        scheduler.add_job(config, callback)

        result = scheduler.run_job("test-job")
        assert result is False
        status = scheduler.get_status("test-job")
        assert status.status == "failed"
        assert "boom" in status.error

    def test_run_job_prevents_concurrent(self):
        scheduler = StrategyScheduler()
        config = ScheduleConfig(
            job_id="test-job",
            strategy_id="test-strategy",
            frequency=ScheduleFrequency.DAILY,
        )
        scheduler.add_job(config)

        scheduler._status["test-job"].status = "running"
        result = scheduler.run_job("test-job")
        assert result is False


class TestJobRunner:
    """Tests for JobRunner."""

    def test_check_and_run_calls_due_jobs(self):
        scheduler = StrategyScheduler()
        config = ScheduleConfig(
            job_id="test-job",
            strategy_id="test-strategy",
            frequency=ScheduleFrequency.DAILY,
            run_time=datetime.now().time(),
        )
        callback = MagicMock()
        scheduler.add_job(config, callback)

        runner = JobRunner(scheduler)
        runner.check_and_run()
        callback.assert_called_once()

    def test_run_all_runs_all_jobs(self):
        scheduler = StrategyScheduler()
        callback1 = MagicMock()
        callback2 = MagicMock()

        scheduler.add_job(
            ScheduleConfig(job_id="j1", strategy_id="s1", frequency=ScheduleFrequency.DAILY),
            callback1,
        )
        scheduler.add_job(
            ScheduleConfig(job_id="j2", strategy_id="s2", frequency=ScheduleFrequency.DAILY),
            callback2,
        )

        runner = JobRunner(scheduler)
        runner.run_all()
        callback1.assert_called_once()
        callback2.assert_called_once()


class TestHealthChecker:
    """Tests for HealthChecker."""

    def test_check_strategy_uses_parameterized_query(self):
        """Verify SQL injection is prevented via parameterized queries."""
        mock_catalog = MagicMock()
        mock_catalog.query.return_value = MagicMock(
            is_empty=lambda: False,
            __getitem__=lambda self, key: [1, "2025-01-01"] if key in ("cnt",) else ["2025-01-01"],
        )
        checker = HealthChecker(mock_catalog)

        checker.check_strategy("test'; DROP TABLE gold_backtest_runs; --")

        call_args = mock_catalog.query.call_args
        query_str = call_args[0][0]
        params = call_args[0][1]

        assert "?" in query_str
        assert "DROP TABLE" not in query_str
        assert len(params) == 1

    def test_check_all_returns_health_status(self):
        mock_catalog = MagicMock()
        mock_catalog.initialize.return_value = None
        mock_catalog.query.return_value = MagicMock(
            is_empty=lambda: False,
            __getitem__=lambda self, key: ["2025-01-10"],
        )
        checker = HealthChecker(mock_catalog)
        status = checker.check_all()
        assert isinstance(status, HealthStatus)
        assert status.healthy is True

    def test_check_database_failure(self):
        mock_catalog = MagicMock()
        mock_catalog.initialize.side_effect = RuntimeError("connection refused")
        checker = HealthChecker(mock_catalog)
        status = checker.check_all()
        assert status.healthy is False
        assert "Database connection failed" in status.messages
