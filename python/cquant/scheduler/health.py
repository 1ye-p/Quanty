"""cquant.scheduler.health — System health monitoring."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from cquant.datahub.catalog import Catalog

logger = logging.getLogger(__name__)


@dataclass
class HealthStatus:
    """System health status."""
    healthy: bool = True
    checks: dict[str, bool] = field(default_factory=dict)
    messages: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


class HealthChecker:
    """Monitor system health.

    Checks:
    - Database connectivity
    - Data freshness
    - Storage availability

    Usage::

        checker = HealthChecker(catalog)
        status = checker.check_all()
        if not status.healthy:
            print(status.messages)
    """

    def __init__(self, catalog: Catalog) -> None:
        self._catalog = catalog

    def check_all(self) -> HealthStatus:
        """Run all health checks.

        Returns:
            HealthStatus with check results
        """
        status = HealthStatus()

        # Check database
        status.checks["database"] = self._check_database()
        if not status.checks["database"]:
            status.healthy = False
            status.messages.append("Database connection failed")

        # Check data freshness
        status.checks["data_freshness"] = self._check_data_freshness()
        if not status.checks["data_freshness"]:
            status.messages.append("Data may be stale")

        # Check recent backtests
        status.checks["backtest_activity"] = self._check_backtest_activity()
        if not status.checks["backtest_activity"]:
            status.messages.append("No recent backtest activity")

        return status

    def _check_database(self) -> bool:
        """Check database connectivity."""
        try:
            self._catalog.initialize()
            return True
        except Exception as exc:
            logger.error("Database check failed: %s", exc)
            return False

    def _check_data_freshness(self) -> bool:
        """Check if data is fresh (within last 7 days)."""
        try:
            result = self._catalog.query('''
                SELECT MAX(trade_date) as latest
                FROM silver_prices_1d
            ''')
            if result.is_empty():
                return False

            latest = result["latest"][0]
            if latest is None:
                return False

            # Check if within 7 days
            from datetime import date, timedelta
            if isinstance(latest, str):
                from datetime import datetime
                latest = datetime.fromisoformat(latest).date()
            return (date.today() - latest) <= timedelta(days=7)
        except Exception as exc:
            logger.error("Data freshness check failed: %s", exc)
            return False

    def _check_backtest_activity(self) -> bool:
        """Check if there's been recent backtest activity."""
        try:
            result = self._catalog.query('''
                SELECT COUNT(*) as cnt
                FROM gold_backtest_runs
                WHERE started_at >= NOW() - INTERVAL '7 days'
            ''')
            return result["cnt"][0] > 0 if not result.is_empty() else False
        except Exception:
            return False

    def check_strategy(self, strategy_id: str) -> HealthStatus:
        """Check health for a specific strategy.

        Args:
            strategy_id: Strategy to check

        Returns:
            HealthStatus for the strategy
        """
        status = HealthStatus()

        try:
            # Check recent runs — parameterized to prevent SQL injection
            result = self._catalog.query(
                "SELECT COUNT(*) as cnt, MAX(started_at) as last_run "
                "FROM gold_backtest_runs WHERE strategy_id = ?",
                [strategy_id],
            )

            if result.is_empty() or result["cnt"][0] == 0:
                status.healthy = False
                status.messages.append(f"No runs found for strategy {strategy_id}")
            else:
                status.checks["strategy_runs"] = True
                last_run = result["last_run"][0]
                if last_run:
                    status.messages.append(f"Last run: {last_run}")

        except Exception as exc:
            status.healthy = False
            status.messages.append(f"Strategy check failed: {exc}")

        return status
