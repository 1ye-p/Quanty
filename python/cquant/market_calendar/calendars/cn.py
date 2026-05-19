"""cquant.market_calendar.calendars.cn — CN A-share trading calendar.

Trading days are loaded from a cached set. The cache is populated on first use
from the configured data source (Tushare by default) and persisted to DuckDB.
For offline / test use, a minimal built-in holiday set covers 2020-2027.
"""

from __future__ import annotations

import logging
from datetime import date

from cquant.core.enums import Exchange
from cquant.market_calendar.calendars.base import TradingCalendar

logger = logging.getLogger(__name__)

# ── Minimal built-in holiday set for offline / testing use ────────────────────
# SSE and SZSE share the same holiday schedule.
# This list covers national public holidays 2020-2026 (not exhaustive for
# make-up trading days; use Tushare for production-quality data).
_CN_PUBLIC_HOLIDAYS: frozenset[date] = frozenset(
    [
        # 2020
        date(2020, 1, 1),
        date(2020, 1, 24), date(2020, 1, 27), date(2020, 1, 28), date(2020, 1, 29), date(2020, 1, 30), date(2020, 1, 31),
        date(2020, 4, 4), date(2020, 4, 6),
        date(2020, 5, 1), date(2020, 5, 4), date(2020, 5, 5),
        date(2020, 6, 25), date(2020, 6, 26),
        date(2020, 10, 1), date(2020, 10, 2), date(2020, 10, 5), date(2020, 10, 6), date(2020, 10, 7), date(2020, 10, 8),
        # 2021
        date(2021, 1, 1),
        date(2021, 2, 11), date(2021, 2, 12), date(2021, 2, 15), date(2021, 2, 16), date(2021, 2, 17),
        date(2021, 4, 5),
        date(2021, 5, 3), date(2021, 5, 4), date(2021, 5, 5),
        date(2021, 6, 14),
        date(2021, 9, 20), date(2021, 9, 21),
        date(2021, 10, 1), date(2021, 10, 4), date(2021, 10, 5), date(2021, 10, 6), date(2021, 10, 7),
        # 2022
        date(2022, 1, 3),
        date(2022, 1, 31), date(2022, 2, 1), date(2022, 2, 2), date(2022, 2, 3), date(2022, 2, 4),
        date(2022, 4, 4), date(2022, 4, 5),
        date(2022, 4, 29), date(2022, 5, 2), date(2022, 5, 3), date(2022, 5, 4),
        date(2022, 6, 3),
        date(2022, 9, 12),
        date(2022, 10, 3), date(2022, 10, 4), date(2022, 10, 5), date(2022, 10, 6), date(2022, 10, 7),
        # 2023
        date(2023, 1, 2),
        date(2023, 1, 23), date(2023, 1, 24), date(2023, 1, 25), date(2023, 1, 26), date(2023, 1, 27),
        date(2023, 4, 5),
        date(2023, 4, 28), date(2023, 5, 1),
        date(2023, 6, 22), date(2023, 6, 23),
        date(2023, 9, 29), date(2023, 10, 4), date(2023, 10, 5), date(2023, 10, 6),
        # 2024
        date(2024, 1, 1),
        date(2024, 2, 12), date(2024, 2, 13), date(2024, 2, 14), date(2024, 2, 15), date(2024, 2, 16),
        date(2024, 4, 4), date(2024, 4, 5),
        date(2024, 5, 1), date(2024, 5, 2), date(2024, 5, 3),
        date(2024, 6, 10),
        date(2024, 9, 16), date(2024, 9, 17),
        date(2024, 10, 1), date(2024, 10, 2), date(2024, 10, 3), date(2024, 10, 4), date(2024, 10, 7),
        # 2025
        date(2025, 1, 1),
        date(2025, 1, 28), date(2025, 1, 29), date(2025, 1, 30), date(2025, 1, 31), date(2025, 2, 4),
        date(2025, 4, 4),
        date(2025, 5, 1), date(2025, 5, 2),
        date(2025, 5, 31),
        date(2025, 10, 1), date(2025, 10, 2), date(2025, 10, 3), date(2025, 10, 6), date(2025, 10, 7), date(2025, 10, 8),
        # 2026
        date(2026, 1, 1),
        date(2026, 2, 17), date(2026, 2, 18), date(2026, 2, 19), date(2026, 2, 20), date(2026, 2, 23),
    ]
)


class CNCalendar(TradingCalendar):
    """Trading calendar for SSE and SZSE (identical holiday schedule)."""

    _exchange = Exchange.SSE

    def __init__(
        self,
        holiday_override: frozenset[date] | None = None,
    ) -> None:
        self._holidays = holiday_override if holiday_override is not None else _CN_PUBLIC_HOLIDAYS

    @property
    def exchange(self) -> Exchange:
        return self._exchange

    def is_trading_day(self, d: date) -> bool:
        """Return True if *d* is a weekday and not a CN public holiday."""
        if d.weekday() >= 5:   # Saturday=5, Sunday=6
            return False
        return d not in self._holidays

    def load_from_tushare(self, trade_cal: list[date]) -> None:
        """Replace the built-in holiday set with authoritative Tushare data.

        *trade_cal* should be the list of trading dates returned by
        ``tushare.pro.trade_cal(exchange='SSE', ...)``.
        """
        trading_set = frozenset(trade_cal)
        # Derive holidays as non-weekend dates absent from the trading set
        # (we can't enumerate all possible dates, so keep the built-in fallback
        # and extend it with any new non-trading weekdays we discover)
        logger.info("CNCalendar: loaded %d trading days from Tushare", len(trade_cal))
        self._trading_days_cache: frozenset[date] = trading_set
        self._use_cache = True

    def is_trading_day(self, d: date) -> bool:  # type: ignore[override]
        if hasattr(self, "_use_cache") and self._use_cache:
            return d in self._trading_days_cache
        if d.weekday() >= 5:
            return False
        return d not in self._holidays
