"""Built-in size factors: Market Cap, Log Market Cap."""

from __future__ import annotations

import math

import polars as pl

from cquant.factorlab.factor import FactorContext
from cquant.factorlab.factors._fundamental import FundamentalFactor


class MarketCap(FundamentalFactor):
    """Raw market capitalization."""

    _column = "market_cap"

    @property
    def name(self) -> str:
        return "market_cap"

    @property
    def tags(self) -> list[str]:
        return ["fundamental", "size"]


class LogMarketCap(FundamentalFactor):
    """Natural log of market capitalization (size proxy)."""

    _column = "market_cap"

    @property
    def name(self) -> str:
        return "ln_market_cap"

    @property
    def tags(self) -> list[str]:
        return ["fundamental", "size"]

    def compute(self, frame: pl.DataFrame, ctx: FactorContext) -> pl.Series:
        fund = ctx.extra.get("fundamentals")
        if fund is None or fund.is_empty() or self._column not in fund.columns:
            return pl.Series(name=self.name, values=[None] * len(frame))

        lookup = dict(zip(fund["asset_id"].to_list(), fund[self._column].to_list()))
        return frame["asset_id"].map_elements(
            lambda x: math.log(lookup[x]) if x in lookup else None,
            return_dtype=pl.Float64,
        ).alias(self.name)
