"""cquant.market_calendar.calendars.base — Abstract trading calendar."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, timedelta

from cquant.core.enums import Exchange


class TradingCalendar(ABC):
    """Abstract base for exchange-specific trading calendars."""

    @property
    @abstractmethod
    def exchange(self) -> Exchange:
        """The exchange this calendar governs."""

    @abstractmethod
    def is_trading_day(self, d: date) -> bool:
        """Return True if *d* is a regular trading day on this exchange."""

    def trading_days(self, start: date, end: date) -> list[date]:
        """Return all trading days in [start, end] inclusive."""
        result: list[date] = []
        current = start
        while current <= end:
            if self.is_trading_day(current):
                result.append(current)
            current += timedelta(days=1)
        return result

    def next_trading_day(self, d: date, n: int = 1) -> date:
        """Return the *n*-th trading day strictly after *d*."""
        if n < 1:
            raise ValueError("n must be >= 1")
        current = d + timedelta(days=1)
        count = 0
        while True:
            if self.is_trading_day(current):
                count += 1
                if count == n:
                    return current
            current += timedelta(days=1)

    def prev_trading_day(self, d: date, n: int = 1) -> date:
        """Return the *n*-th trading day strictly before *d*."""
        if n < 1:
            raise ValueError("n must be >= 1")
        current = d - timedelta(days=1)
        count = 0
        while True:
            if self.is_trading_day(current):
                count += 1
                if count == n:
                    return current
            current -= timedelta(days=1)

    def settlement_date(self, trade_date: date, lag_days: int = 1) -> date:
        """Return the settlement date *lag_days* trading days after *trade_date*."""
        return self.next_trading_day(trade_date, n=lag_days)
