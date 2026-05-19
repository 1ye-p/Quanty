"""cquant.market_calendar.service — Unified market calendar service.

Single entry point for all modules that need calendar, rules, or adjustment data.
Caches calendar instances per exchange to avoid redundant construction.
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from functools import lru_cache

from cquant.core.enums import Exchange, Market
from cquant.core.errors import MarketCalendarError
from cquant.core.types import Asset
from cquant.market_calendar.adjustments.factor import AdjustmentFactor
from cquant.market_calendar.calendars.base import TradingCalendar
from cquant.market_calendar.calendars.cn import CNCalendar
from cquant.market_calendar.calendars.hk import HKCalendar
from cquant.market_calendar.calendars.us import USCalendar
from cquant.market_calendar.rules.base import TradingRules
from cquant.market_calendar.rules.cn_rules import CNTradingRules

logger = logging.getLogger(__name__)

_CN_EXCHANGES = {Exchange.SSE, Exchange.SZSE}
_US_EXCHANGES = {Exchange.NYSE, Exchange.NASDAQ, Exchange.AMEX}
_HK_EXCHANGES = {Exchange.HKEX}


class MarketCalendarService:
    """Facade providing calendar, rules, and adjustment factor access.

    Usage::

        svc = MarketCalendarService()

        # Is 2026-05-01 a trading day on SSE?
        svc.is_trading_day(date(2026, 5, 1), Exchange.SSE)   # → False (Labour Day)

        # Get all CN trading days in May 2026
        svc.trading_days(date(2026, 5, 1), date(2026, 5, 31), Exchange.SSE)

        # Next trading day after 2026-05-08
        svc.next_trading_day(date(2026, 5, 8), Exchange.SSE)

        # Settlement date for a T+1 market
        svc.settlement_date(date(2026, 5, 8), Exchange.SSE)
    """

    def __init__(self) -> None:
        self._calendars: dict[Exchange, TradingCalendar] = {}
        self._rules: dict[Exchange, TradingRules] = {}
        self._adjustment_factor = AdjustmentFactor()
        self._initialize_defaults()

    def _initialize_defaults(self) -> None:
        cn_cal = CNCalendar()
        cn_rules = CNTradingRules()
        for exc in _CN_EXCHANGES:
            self._calendars[exc] = cn_cal
            self._rules[exc] = cn_rules

        us_cal = USCalendar()
        for exc in _US_EXCHANGES:
            self._calendars[exc] = us_cal

        hk_cal = HKCalendar()
        for exc in _HK_EXCHANGES:
            self._calendars[exc] = hk_cal

    # ── Calendar API ──────────────────────────────────────────────────────────

    def is_trading_day(self, d: date, exchange: Exchange) -> bool:
        """Return True if *d* is a trading day on *exchange*."""
        return self._get_calendar(exchange).is_trading_day(d)

    def trading_days(self, start: date, end: date, exchange: Exchange) -> list[date]:
        """Return all trading days in [start, end] for *exchange*."""
        return self._get_calendar(exchange).trading_days(start, end)

    def next_trading_day(self, d: date, exchange: Exchange, n: int = 1) -> date:
        """Return the *n*-th trading day after *d* on *exchange*."""
        return self._get_calendar(exchange).next_trading_day(d, n)

    def prev_trading_day(self, d: date, exchange: Exchange, n: int = 1) -> date:
        """Return the *n*-th trading day before *d* on *exchange*."""
        return self._get_calendar(exchange).prev_trading_day(d, n)

    def settlement_date(self, trade_date: date, exchange: Exchange) -> date:
        """Return the settlement date for a trade on *trade_date*."""
        cal = self._get_calendar(exchange)
        lag = 1
        if exchange in _CN_EXCHANGES:
            lag = 1   # T+1
        elif exchange in _US_EXCHANGES or exchange in _HK_EXCHANGES:
            lag = 2   # T+2
        return cal.settlement_date(trade_date, lag_days=lag)

    # ── Rules API ─────────────────────────────────────────────────────────────

    def price_limit(self, asset: Asset, d: date) -> tuple[Decimal, Decimal]:
        """Return (lower_multiplier, upper_multiplier) price limit for *asset*.

        Multipliers are relative to the previous close, e.g. (0.9, 1.1) for ±10%.
        Returns (Decimal('-Inf'), Decimal('Inf')) when there is no price limit.
        """
        rules = self._rules.get(asset.exchange)
        if rules is None:
            return (Decimal("-Inf"), Decimal("Inf"))
        return rules.price_limit(asset, d)

    def is_suspended(self, asset: Asset, d: date) -> bool:
        """Return True if *asset* cannot be traded on *d*."""
        rules = self._rules.get(asset.exchange)
        if rules is None:
            return False
        return rules.is_suspended(asset, d)

    def lot_size(self, asset: Asset) -> int:
        rules = self._rules.get(asset.exchange)
        return rules.lot_size(asset) if rules else asset.lot_size

    def tick_size(self, asset: Asset) -> Decimal:
        rules = self._rules.get(asset.exchange)
        return rules.tick_size(asset) if rules else asset.tick_size

    # ── Adjustment factors ────────────────────────────────────────────────────

    @property
    def adjustment_factor(self) -> AdjustmentFactor:
        return self._adjustment_factor

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _get_calendar(self, exchange: Exchange) -> TradingCalendar:
        cal = self._calendars.get(exchange)
        if cal is None:
            raise MarketCalendarError(
                f"No calendar registered for exchange {exchange!r}. "
                "Register one via MarketCalendarService._calendars[exchange] = ..."
            )
        return cal

    def register_calendar(self, exchange: Exchange, calendar: TradingCalendar) -> None:
        """Register or replace the calendar for *exchange*."""
        self._calendars[exchange] = calendar

    def register_rules(self, exchange: Exchange, rules: TradingRules) -> None:
        """Register or replace the trading rules for *exchange*."""
        self._rules[exchange] = rules
