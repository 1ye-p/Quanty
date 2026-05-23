"""Tests for CNCalendar bisect-based trading_days optimization."""

from __future__ import annotations

import time
from datetime import date

from cquant.market_calendar.calendars.cn import CNCalendar


class TestCNCalendarBisect:
    def setup_method(self) -> None:
        self.cal = CNCalendar()

    # ── Correctness ───────────────────────────────────────────────────────────

    def test_trading_days_excludes_weekends(self) -> None:
        days = self.cal.trading_days(date(2026, 5, 18), date(2026, 5, 22))
        for d in days:
            assert d.weekday() < 5, f"{d} is a weekend"

    def test_trading_days_excludes_holiday(self) -> None:
        # 2026-02-17 is in CNY holiday period
        days = self.cal.trading_days(date(2026, 2, 17), date(2026, 2, 23))
        assert date(2026, 2, 17) not in days

    def test_trading_days_result_is_sorted(self) -> None:
        days = self.cal.trading_days(date(2025, 1, 1), date(2025, 3, 31))
        assert days == sorted(days)

    def test_next_trading_day_skips_weekend(self) -> None:
        # 2026-05-15 is Friday; next trading day should be Mon 2026-05-18
        nxt = self.cal.next_trading_day(date(2026, 5, 15))
        assert nxt == date(2026, 5, 18)

    def test_prev_trading_day_skips_weekend(self) -> None:
        # 2026-05-18 is Monday; prev trading day should be Fri 2026-05-15
        prv = self.cal.prev_trading_day(date(2026, 5, 18))
        assert prv == date(2026, 5, 15)

    def test_next_trading_day_n2(self) -> None:
        # 2026-05-15 (Fri) → 2nd next = 2026-05-19 (Tue)
        assert self.cal.next_trading_day(date(2026, 5, 15), n=2) == date(2026, 5, 19)

    def test_prev_trading_day_n2(self) -> None:
        # 2026-05-18 (Mon) → 2nd prev = 2026-05-14 (Thu)
        assert self.cal.prev_trading_day(date(2026, 5, 18), n=2) == date(2026, 5, 14)

    def test_trading_days_same_day(self) -> None:
        d = date(2026, 5, 22)  # Friday
        days = self.cal.trading_days(d, d)
        assert days == [d]

    def test_trading_days_weekend_only_range_returns_empty(self) -> None:
        # 2026-05-16 (Sat) to 2026-05-17 (Sun)
        days = self.cal.trading_days(date(2026, 5, 16), date(2026, 5, 17))
        assert days == []

    # ── Performance ───────────────────────────────────────────────────────────

    def test_trading_days_10yr_completes_under_50ms(self) -> None:
        """10-year range should be fast after cache warm-up."""
        # Warm up cache
        self.cal.trading_days(date(2015, 1, 1), date(2025, 12, 31))
        # Measure 100 calls
        t0 = time.perf_counter()
        for _ in range(100):
            self.cal.trading_days(date(2015, 1, 1), date(2025, 12, 31))
        elapsed_ms = (time.perf_counter() - t0) * 10  # avg ms per call
        assert elapsed_ms < 50, f"trading_days 10yr took {elapsed_ms:.1f}ms avg, expected < 50ms"

    # ── Cache invalidation ────────────────────────────────────────────────────

    def test_load_from_tushare_invalidates_cache(self) -> None:
        # Trigger cache build with built-in data
        _ = self.cal._sorted_trading_days
        assert "_sorted_trading_days" in self.cal.__dict__  # cached

        # Load new data
        new_trading_days = [date(2026, 1, 5), date(2026, 1, 6)]
        self.cal.load_from_tushare(new_trading_days)

        # Cache should be cleared
        assert "_sorted_trading_days" not in self.cal.__dict__

        # After next access, should reflect new data
        new_days = self.cal._sorted_trading_days
        assert new_days == sorted(new_trading_days)
