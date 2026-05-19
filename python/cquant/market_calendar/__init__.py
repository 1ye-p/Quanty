"""cquant.market_calendar — Trading calendar, price limits, and adjustment factors.

All market-specific rules for CN / US / HK live here so that other modules
(datahub, factorlab, backtest_vector, etc.) share a single source of truth.
"""

from cquant.market_calendar.service import MarketCalendarService
from cquant.market_calendar.rules.base import TradingRules
from cquant.market_calendar.adjustments.factor import AdjustmentFactor

__all__ = ["MarketCalendarService", "TradingRules", "AdjustmentFactor"]
