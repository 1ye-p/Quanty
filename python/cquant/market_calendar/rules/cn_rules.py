"""cquant.market_calendar.rules.cn_rules — CN A-share trading rules.

Covers:
- Price limits: ±10% (normal), ±5% (ST/*ST), ±20% (ChiNext/STAR Market),
  and unlimited for IPO first 5 trading days (post-2023 reform).
- Settlement: T+1 for A-shares.
- Lot size: 100 shares standard board; 1 share allowed for STAR/ChiNext IPO
  under certain conditions (implementation simplified here).
- Tick size: CNY 0.01.
- Stamp duty side flag is defined here for reference (applied by CostModel).

Suspension data must be injected at runtime from datahub; this class exposes
a hook for that injection rather than hard-coding a static list.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Callable

from cquant.core.enums import AssetClass, AssetStatus, Exchange
from cquant.core.types import Asset
from cquant.market_calendar.rules.base import TradingRules

_INFINITY = Decimal("Inf")
_NEG_INFINITY = Decimal("-Inf")

# Asset ID prefixes that identify ChiNext (创业板) and STAR Market (科创板)
_CHINEXT_PREFIXES = ("SZSE:300", "SZSE:301")
_STAR_PREFIXES = ("SSE:688",)

SuspensionLookup = Callable[[str, date], bool]


class CNTradingRules(TradingRules):
    """Trading rules for CN A-share markets (SSE and SZSE)."""

    def __init__(
        self,
        suspension_lookup: SuspensionLookup | None = None,
        ipo_dates: dict[str, date] | None = None,
    ) -> None:
        # Injection point for datahub suspension data.
        # If None, is_suspended() always returns False (safe default for research).
        self._suspension_lookup = suspension_lookup
        # Optional map of asset_id → IPO date for IPO first-5-days unlimited rule.
        self._ipo_dates: dict[str, date] = ipo_dates or {}

    def price_limit(self, asset: Asset, d: date) -> tuple[Decimal, Decimal]:
        """Return (lower_limit_pct, upper_limit_pct) as multipliers of prev close.

        Note: returns *rate* not absolute price; CostModel / backtest engine
        must multiply by the previous close to get the actual price bound.
        """
        # ST / *ST stocks: ±5%
        if asset.status in (AssetStatus.ST, AssetStatus.STAR_ST):
            rate = Decimal("0.05")
            return (Decimal("1") - rate, Decimal("1") + rate)

        # ChiNext and STAR Market: ±20%
        if any(asset.asset_id.startswith(p) for p in _CHINEXT_PREFIXES + _STAR_PREFIXES):
            # IPO first 5 trading days: no limit (post-2023 reform)
            if asset.asset_id in self._ipo_dates:
                ipo_date = self._ipo_dates[asset.asset_id]
                # Simple calendar-day check; for production use trading-day count
                delta = (d - ipo_date).days
                if 0 <= delta <= 10:  # ~5 trading days ≈ 7-10 calendar days
                    return (_NEG_INFINITY, _INFINITY)
            rate = Decimal("0.20")
            return (Decimal("1") - rate, Decimal("1") + rate)

        # Standard board: ±10%
        rate = Decimal("0.10")
        return (Decimal("1") - rate, Decimal("1") + rate)

    def is_suspended(self, asset: Asset, d: date) -> bool:
        if self._suspension_lookup is None:
            return False
        return self._suspension_lookup(asset.asset_id, d)

    def lot_size(self, asset: Asset) -> int:
        # Star Market and ChiNext allow 1-share lots at IPO auction;
        # for secondary market the standard 100-share lot applies.
        return asset.lot_size if asset.lot_size > 0 else 100

    def tick_size(self, asset: Asset) -> Decimal:
        return asset.tick_size if asset.tick_size > Decimal("0") else Decimal("0.01")

    def settlement_lag(self, asset: Asset) -> int:
        return 1  # T+1 for all A-share securities
