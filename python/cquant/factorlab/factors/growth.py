"""Built-in growth factors: Revenue Growth, Earnings Growth."""

from __future__ import annotations

from cquant.factorlab.factors._fundamental import FundamentalFactor


class RevenueGrowth(FundamentalFactor):
    """Year-over-year revenue growth rate."""

    _column = "revenue_growth_yoy"

    @property
    def description(self) -> str:
        return "营业收入同比增长率"

    @property
    def name(self) -> str:
        return "revenue_growth_yoy"

    @property
    def tags(self) -> list[str]:
        return ["fundamental", "growth"]


class EarningsGrowth(FundamentalFactor):
    """Year-over-year earnings growth rate."""

    _column = "earnings_growth_yoy"

    @property
    def description(self) -> str:
        return "净利润同比增长率"

    @property
    def name(self) -> str:
        return "earnings_growth_yoy"

    @property
    def tags(self) -> list[str]:
        return ["fundamental", "growth"]
