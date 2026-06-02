"""cquant.market_calendar.rules.base — Abstract trading rules interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from cquant.core.enums import TradabilityReason
from cquant.core.types import Asset


@dataclass
class TradabilityResult:
    """综合可交易性检查结果"""
    tradable: bool
    reason: TradabilityReason
    message: str = ""


class TradingRules(ABC):
    """Abstract interface for exchange-specific trading rules."""

    @abstractmethod
    def price_limit(self, asset: Asset, d: date) -> tuple[Decimal, Decimal]:
        """Return (lower_limit, upper_limit) price bounds for *asset* on *d*.

        Returns (Decimal("-Inf"), Decimal("Inf")) when there is no price limit.
        """

    @abstractmethod
    def is_suspended(self, asset: Asset, d: date) -> bool:
        """Return True if *asset* is suspended (cannot trade) on *d*."""

    @abstractmethod
    def lot_size(self, asset: Asset) -> int:
        """Minimum tradable unit in shares."""

    @abstractmethod
    def tick_size(self, asset: Asset) -> Decimal:
        """Minimum price increment."""

    def settlement_lag(self, asset: Asset) -> int:
        """Number of trading days between trade date and settlement (T+N)."""
        return 1  # Subclasses should override
