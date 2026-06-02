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

from cquant.core.enums import AssetClass, AssetStatus, LimitStatus, TradabilityReason, Exchange
from cquant.core.types import Asset
from cquant.market_calendar.registry import register_rules
from cquant.market_calendar.rules.base import TradingRules, TradabilityResult

_INFINITY = Decimal("Inf")
_NEG_INFINITY = Decimal("-Inf")

# Asset ID prefixes that identify ChiNext (创业板) and STAR Market (科创板)
_CHINEXT_PREFIXES = ("SZSE:300", "SZSE:301")
_STAR_PREFIXES = ("SSE:688",)

SuspensionLookup = Callable[[str, date], bool]


@register_rules("CN")
class CNTradingRules(TradingRules):
    """Trading rules for CN A-share markets (SSE and SZSE)."""

    def __init__(
        self,
        suspension_lookup: SuspensionLookup | None = None,
        ipo_dates: dict[str, date] | None = None,
        config: dict | None = None,
    ) -> None:
        super().__init__(config=config)
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

    # --- Extended market rules ---

    def _get_board(self, asset_id: str) -> str:
        """Determine board type from asset_id."""
        code = asset_id.split(":")[-1] if ":" in asset_id else asset_id[2:]
        if code.startswith("688"):
            return "star"
        if code.startswith("300") or code.startswith("301"):
            return "chinext"
        return "main_board"

    def _get_limit_pct(self, asset_id: str, is_st: bool = False) -> float:
        """Get limit percentage from config based on board and ST status."""
        if is_st:
            return self._config.get("price_limits", {}).get("st", {}).get("up", 0.05)
        board = self._get_board(asset_id)
        defaults = {"main_board": 0.10, "chinext": 0.20, "star": 0.20}
        return self._config.get("price_limits", {}).get(board, {}).get("up", defaults.get(board, 0.10))

    def detect_limit(self, bar: dict, pre_close: float, limit_pct: float | None = None) -> LimitStatus:
        """Detect limit status from bar data."""
        if limit_pct is None:
            limit_pct = 0.10
        tolerance = self._config.get("derivation", {}).get("limit_tolerance", 0.99)
        from cquant.market_calendar.limit_detector import detect_limit
        return detect_limit(bar, pre_close, limit_pct, tolerance)

    def check_tradable(self, asset_id: str, trade_date: date, bar: dict) -> TradabilityResult:
        """综合可交易性检查：停牌、涨跌停、退市等。"""
        # Check delist via base
        base_result = super().check_tradable(asset_id, trade_date, bar)
        if not base_result.tradable:
            return base_result

        # Check suspension (use lookup directly to avoid needing full Asset object)
        if self._suspension_lookup and self._suspension_lookup(asset_id, trade_date):
            return TradabilityResult(False, TradabilityReason.SUSPENDED)

        # Check limit
        pre_close = bar.get("pre_close", bar["close"])
        is_st = False
        if self._status_tracker:
            status = self._status_tracker.get_status(asset_id, trade_date)
            is_st = status in (AssetStatus.ST.value, AssetStatus.STAR_ST.value)
        limit_pct = self._get_limit_pct(asset_id, is_st)
        limit = self.detect_limit(bar, pre_close, limit_pct)

        if limit == LimitStatus.YIZI_UP:
            return TradabilityResult(False, TradabilityReason.YIZI_LIMIT, "一字涨停不可买入")
        if limit == LimitStatus.YIZI_DOWN:
            return TradabilityResult(False, TradabilityReason.YIZI_LIMIT, "一字跌停不可卖出")
        if limit == LimitStatus.UP:
            return TradabilityResult(False, TradabilityReason.LIMIT_UP)
        if limit == LimitStatus.DOWN:
            return TradabilityResult(False, TradabilityReason.LIMIT_DOWN)

        return TradabilityResult(True, TradabilityReason.TRADABLE)

    def get_asset_status(self, asset_id: str, trade_date: date) -> str:
        """获取资产状态。"""
        if self._status_tracker:
            cached = self._status_tracker.get_status(asset_id, trade_date)
            if cached:
                return cached
        return AssetStatus.ACTIVE.value

    def get_delist_date(self, asset_id: str) -> date | None:
        """获取退市日期。"""
        if self._status_tracker:
            return self._status_tracker.get_delist_date(asset_id)
        return None

    def handle_delist(
        self, positions: dict[str, int], asset_id: str, trade_date: date, price: float
    ) -> list:
        """退市持仓强制平仓。"""
        return self._delist_handler.handle_delist(positions, asset_id, trade_date, price)
