"""Built-in quality factors: ROE, ROA, Gross Margin."""

from __future__ import annotations

from cquant.factorlab.factors._fundamental import FundamentalFactor


class ROE(FundamentalFactor):
    """Return on Equity."""

    _column = "roe"

    @property
    def description(self) -> str:
        return "净资产收益率（Return on Equity）"

    @property
    def name(self) -> str:
        return "roe"

    @property
    def tags(self) -> list[str]:
        return ["fundamental", "quality"]


class ROA(FundamentalFactor):
    """Return on Assets."""

    _column = "roa"

    @property
    def description(self) -> str:
        return "总资产收益率（Return on Assets）"

    @property
    def name(self) -> str:
        return "roa"

    @property
    def tags(self) -> list[str]:
        return ["fundamental", "quality"]


class GrossMargin(FundamentalFactor):
    """Gross profit margin."""

    _column = "gross_margin"

    @property
    def description(self) -> str:
        return "毛利率（毛利润 / 营业收入）"

    @property
    def name(self) -> str:
        return "gross_margin"

    @property
    def tags(self) -> list[str]:
        return ["fundamental", "quality"]
