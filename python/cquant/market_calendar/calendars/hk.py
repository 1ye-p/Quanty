"""cquant.market_calendar.calendars.hk — Hong Kong Stock Exchange calendar.

Minimal built-in holiday set. For production use, replace with authoritative data
from HKEX or a market calendar library.
"""

from __future__ import annotations

from datetime import date

from cquant.core.enums import Exchange
from cquant.market_calendar.calendars.base import TradingCalendar

# HK public holidays that close the stock market (2024-2026, partial).
_HK_HOLIDAYS: frozenset[date] = frozenset(
    [
        # 2024
        date(2024, 1, 1), date(2024, 2, 12), date(2024, 2, 13),
        date(2024, 3, 29), date(2024, 4, 1), date(2024, 4, 4),
        date(2024, 5, 1), date(2024, 5, 15), date(2024, 6, 10),
        date(2024, 7, 1), date(2024, 9, 18), date(2024, 10, 1),
        date(2024, 10, 11), date(2024, 12, 25), date(2024, 12, 26),
        # 2025
        date(2025, 1, 1), date(2025, 1, 29), date(2025, 1, 30), date(2025, 1, 31),
        date(2025, 4, 4), date(2025, 4, 18), date(2025, 4, 21),
        date(2025, 5, 1), date(2025, 5, 5), date(2025, 6, 2),
        date(2025, 7, 1), date(2025, 10, 1), date(2025, 10, 7),
        date(2025, 12, 25), date(2025, 12, 26),
        # 2026
        date(2026, 1, 1), date(2026, 2, 17), date(2026, 2, 18), date(2026, 2, 19),
    ]
)


class HKCalendar(TradingCalendar):
    """Trading calendar for Hong Kong Stock Exchange (HKEX)."""

    def __init__(self, holiday_override: frozenset[date] | None = None) -> None:
        self._holidays = holiday_override if holiday_override is not None else _HK_HOLIDAYS

    @property
    def exchange(self) -> Exchange:
        return Exchange.HKEX

    def is_trading_day(self, d: date) -> bool:
        if d.weekday() >= 5:
            return False
        return d not in self._holidays
