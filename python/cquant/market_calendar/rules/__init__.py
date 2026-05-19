"""Market trading rules: price limits, suspension, lot size, tick size."""

from cquant.market_calendar.rules.base import TradingRules
from cquant.market_calendar.rules.cn_rules import CNTradingRules

__all__ = ["TradingRules", "CNTradingRules"]
