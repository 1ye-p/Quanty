"""cquant.market_calendar — Trading calendar, price limits, and adjustment factors.

All market-specific rules for CN / US / HK live here so that other modules
(datahub, factorlab, backtest_vector, etc.) share a single source of truth.
"""

from cquant.market_calendar.adjustments.factor import AdjustmentFactor
from cquant.market_calendar.config_loader import load_market_config
from cquant.market_calendar.delist_handler import DelistHandler
from cquant.market_calendar.limit_detector import LimitStatus, detect_limit
from cquant.market_calendar.registry import get_market_rules, list_registered_markets, register_rules
from cquant.market_calendar.rules.base import TradabilityResult, TradingRules
from cquant.market_calendar.service import MarketCalendarService
from cquant.market_calendar.status_tracker import StatusTracker

__all__ = [
    "AdjustmentFactor",
    "DelistHandler",
    "LimitStatus",
    "MarketCalendarService",
    "StatusTracker",
    "TradabilityResult",
    "TradingRules",
    "detect_limit",
    "get_market_rules",
    "list_registered_markets",
    "load_market_config",
    "register_rules",
]
