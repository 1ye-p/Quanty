"""cquant.market_calendar.calendars.us — US equity trading calendar (NYSE/NASDAQ).

Uses a minimal built-in holiday set. For production use, populate via
pandas_market_calendars or a similar authoritative source.
"""

from __future__ import annotations

from datetime import date

from cquant.core.enums import Exchange
from cquant.market_calendar.calendars.base import TradingCalendar

# Fixed and near-fixed NYSE/NASDAQ holidays (2020-2026, partial list).
# Does not include observed dates when holidays fall on weekends.
_US_HOLIDAYS: frozenset[date] = frozenset(
    [
        # New Year's Day
        date(2020, 1, 1), date(2021, 1, 1), date(2022, 1, 17),  # observed
        date(2023, 1, 2), date(2024, 1, 1), date(2025, 1, 1), date(2026, 1, 1),
        # MLK Day (3rd Monday Jan)
        date(2020, 1, 20), date(2021, 1, 18), date(2022, 1, 17),
        date(2023, 1, 16), date(2024, 1, 15), date(2025, 1, 20), date(2026, 1, 19),
        # Presidents Day (3rd Monday Feb)
        date(2020, 2, 17), date(2021, 2, 15), date(2022, 2, 21),
        date(2023, 2, 20), date(2024, 2, 19), date(2025, 2, 17), date(2026, 2, 16),
        # Good Friday
        date(2020, 4, 10), date(2021, 4, 2), date(2022, 4, 15),
        date(2023, 4, 7), date(2024, 3, 29), date(2025, 4, 18), date(2026, 4, 3),
        # Memorial Day (last Monday May)
        date(2020, 5, 25), date(2021, 5, 31), date(2022, 5, 30),
        date(2023, 5, 29), date(2024, 5, 27), date(2025, 5, 26), date(2026, 5, 25),
        # Juneteenth
        date(2022, 6, 20), date(2023, 6, 19), date(2024, 6, 19),
        date(2025, 6, 19), date(2026, 6, 19),
        # Independence Day
        date(2020, 7, 3), date(2021, 7, 5), date(2022, 7, 4),
        date(2023, 7, 4), date(2024, 7, 4), date(2025, 7, 4), date(2026, 7, 3),
        # Labor Day (1st Monday Sep)
        date(2020, 9, 7), date(2021, 9, 6), date(2022, 9, 5),
        date(2023, 9, 4), date(2024, 9, 2), date(2025, 9, 1), date(2026, 9, 7),
        # Thanksgiving (4th Thursday Nov)
        date(2020, 11, 26), date(2021, 11, 25), date(2022, 11, 24),
        date(2023, 11, 23), date(2024, 11, 28), date(2025, 11, 27), date(2026, 11, 26),
        # Christmas
        date(2020, 12, 25), date(2021, 12, 24), date(2022, 12, 26),
        date(2023, 12, 25), date(2024, 12, 25), date(2025, 12, 25), date(2026, 12, 25),
    ]
)


class USCalendar(TradingCalendar):
    """Trading calendar for NYSE and NASDAQ (identical holiday schedule)."""

    def __init__(self, holiday_override: frozenset[date] | None = None) -> None:
        self._holidays = holiday_override if holiday_override is not None else _US_HOLIDAYS

    @property
    def exchange(self) -> Exchange:
        return Exchange.NYSE

    def is_trading_day(self, d: date) -> bool:
        if d.weekday() >= 5:
            return False
        return d not in self._holidays
