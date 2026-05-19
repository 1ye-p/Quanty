"""Unit tests for cquant.market_calendar."""

from datetime import date

import pytest

from cquant.market_calendar.calendars.cn import CNCalendar
from cquant.market_calendar.service import MarketCalendarService
from cquant.core.enums import Exchange


class TestCNCalendar:
    def setup_method(self) -> None:
        self.cal = CNCalendar()

    def test_weekday_is_trading_day(self) -> None:
        assert self.cal.is_trading_day(date(2026, 5, 11)) is True  # Monday

    def test_saturday_is_not_trading_day(self) -> None:
        assert self.cal.is_trading_day(date(2026, 5, 9)) is False

    def test_sunday_is_not_trading_day(self) -> None:
        assert self.cal.is_trading_day(date(2026, 5, 10)) is False

    def test_cn_labour_day_is_not_trading_day(self) -> None:
        assert self.cal.is_trading_day(date(2025, 5, 1)) is False  # Labour Day

    def test_next_trading_day(self) -> None:
        # Friday → Monday (no holiday)
        nxt = self.cal.next_trading_day(date(2026, 5, 8))
        assert nxt == date(2026, 5, 11)

    def test_trading_days_count(self) -> None:
        # May 11 (Mon) to May 15 (Fri) = 5 trading days
        days = self.cal.trading_days(date(2026, 5, 11), date(2026, 5, 15))
        assert len(days) == 5


class TestMarketCalendarService:
    def setup_method(self) -> None:
        self.svc = MarketCalendarService()

    def test_sse_settlement_is_t1(self) -> None:
        settlement = self.svc.settlement_date(date(2026, 5, 11), Exchange.SSE)
        assert settlement == date(2026, 5, 12)

    def test_nyse_settlement_is_t2(self) -> None:
        settlement = self.svc.settlement_date(date(2026, 5, 11), Exchange.NYSE)
        assert settlement == date(2026, 5, 13)
