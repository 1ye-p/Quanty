"""Built-in value factors: PE-TTM, PB, Dividend Yield.

These read from ``ctx.extra['valuation']`` (silver_valuation_daily) which is
per-(asset_id, trade_date) and naturally PIT.
"""

from __future__ import annotations

from cquant.factorlab.factors._fundamental import ValuationFactor


class PETTM(ValuationFactor):
    """Price-to-Earnings (trailing twelve months)."""

    _column = "pe_ttm"

    @property
    def description(self) -> str:
        return "市盈率（TTM，滚动 12 个月）"

    @property
    def name(self) -> str:
        return "pe_ttm"

    @property
    def tags(self) -> list[str]:
        return ["fundamental", "value"]


class PB(ValuationFactor):
    """Price-to-Book ratio."""

    _column = "pb"

    @property
    def description(self) -> str:
        return "市净率（Price-to-Book）"

    @property
    def name(self) -> str:
        return "pb"

    @property
    def tags(self) -> list[str]:
        return ["fundamental", "value"]


class DividendYield(ValuationFactor):
    """Dividend yield (annual dividend / price)."""

    _column = "dividend_yield"

    @property
    def description(self) -> str:
        return "股息率（年化股息 / 股价）"

    @property
    def name(self) -> str:
        return "dividend_yield"

    @property
    def tags(self) -> list[str]:
        return ["fundamental", "value"]
