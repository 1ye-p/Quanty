"""cquant.core.clock — Simulation clock abstraction.

Provides a unified time interface so that backtest engines and live execution
can be swapped without modifying strategy code.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, datetime, timezone


class Clock(ABC):
    """Abstract clock used by all cQuant engines and modules."""

    @abstractmethod
    def now(self) -> datetime:
        """Return the current simulation or wall-clock datetime (UTC-aware)."""

    @abstractmethod
    def today(self) -> date:
        """Return the current local exchange date."""


class WallClock(Clock):
    """Real-time clock backed by the system clock."""

    def now(self) -> datetime:
        return datetime.now(tz=timezone.utc)

    def today(self) -> date:
        return datetime.now(tz=timezone.utc).date()


class SimulationClock(Clock):
    """Deterministic clock for backtesting — time advances only when set."""

    def __init__(self, initial: datetime) -> None:
        if initial.tzinfo is None:
            raise ValueError("SimulationClock requires a timezone-aware datetime")
        self._current: datetime = initial

    def now(self) -> datetime:
        return self._current

    def today(self) -> date:
        return self._current.date()

    def advance(self, new_time: datetime) -> None:
        """Advance the clock to *new_time*; must not move backwards."""
        if new_time.tzinfo is None:
            raise ValueError("advance() requires a timezone-aware datetime")
        if new_time < self._current:
            raise ValueError(
                f"Clock cannot go backwards: {new_time} < {self._current}"
            )
        self._current = new_time
