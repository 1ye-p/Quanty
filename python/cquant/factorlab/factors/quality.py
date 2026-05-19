"""Built-in quality factors: ROE, ROA, Gross Margin."""

from __future__ import annotations

from cquant.factorlab.factors._fundamental import FundamentalFactor


class ROE(FundamentalFactor):
    """Return on Equity."""

    _column = "roe"

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
    def name(self) -> str:
        return "roa"

    @property
    def tags(self) -> list[str]:
        return ["fundamental", "quality"]


class GrossMargin(FundamentalFactor):
    """Gross profit margin."""

    _column = "gross_margin"

    @property
    def name(self) -> str:
        return "gross_margin"

    @property
    def tags(self) -> list[str]:
        return ["fundamental", "quality"]
