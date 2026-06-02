"""cquant.market_calendar.rules.base — Abstract trading rules interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from cquant.core.enums import AssetStatus, LimitStatus, TradabilityReason
from cquant.core.types import Asset
from cquant.market_calendar.delist_handler import DelistHandler, ForcedLiquidationTrade
from cquant.market_calendar.limit_detector import detect_limit as _detect_limit
from cquant.market_calendar.status_tracker import StatusTracker


@dataclass
class TradabilityResult:
    """综合可交易性检查结果"""
    tradable: bool
    reason: TradabilityReason
    message: str = ""


class TradingRules(ABC):
    """Abstract interface for exchange-specific trading rules."""

    def __init__(self, config: dict | None = None) -> None:
        self._config = config or {}
        self._status_tracker: StatusTracker | None = None
        self._delist_handler: DelistHandler = DelistHandler()

    def set_status_tracker(self, tracker: StatusTracker) -> None:
        """注入状态追踪器"""
        self._status_tracker = tracker

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

    # --- New methods for market rules ---

    def check_tradable(self, asset_id: str, trade_date: date, bar: dict) -> TradabilityResult:
        """综合可交易性检查。子类可覆盖。"""
        if self._status_tracker:
            status = self._status_tracker.get_status(asset_id, trade_date)
            if status == AssetStatus.DELISTED.value:
                return TradabilityResult(False, TradabilityReason.DELISTED)
        return TradabilityResult(True, TradabilityReason.TRADABLE)

    def detect_limit(self, bar: dict, pre_close: float, limit_pct: float) -> LimitStatus:
        """检测涨跌停状态。委托给 limit_detector。"""
        tolerance = self._config.get("derivation", {}).get("limit_tolerance", 0.99)
        return _detect_limit(bar, pre_close, limit_pct, tolerance)

    def get_asset_status(self, asset_id: str, trade_date: date) -> str:
        """获取资产状态。子类应覆盖以接入数据源。"""
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
    ) -> list[ForcedLiquidationTrade]:
        """退市持仓强制平仓。"""
        return self._delist_handler.handle_delist(positions, asset_id, trade_date, price)
