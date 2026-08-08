"""Built-in size factors: Market Cap, Log Market Cap.

These read from ``ctx.extra['valuation']`` (silver_valuation_daily) which is
per-(asset_id, trade_date) and naturally PIT.
"""

from __future__ import annotations

import math

import polars as pl

from cquant.factorlab.factor import FactorContext
from cquant.factorlab.factors._fundamental import ValuationFactor


class MarketCap(ValuationFactor):
    """Raw market capitalization."""

    _column = "market_cap"

    @property
    def description(self) -> str:
        return "总市值"

    @property
    def name(self) -> str:
        return "market_cap"

    @property
    def tags(self) -> list[str]:
        return ["fundamental", "size"]


class LogMarketCap(ValuationFactor):
    """Natural log of market capitalization (size proxy)."""

    _column = "market_cap"

    @property
    def description(self) -> str:
        return "对数总市值（规模代理变量）"

    @property
    def name(self) -> str:
        return "ln_market_cap"

    @property
    def tags(self) -> list[str]:
        return ["fundamental", "size"]

    def compute(self, frame: pl.DataFrame, ctx: FactorContext) -> pl.Series:
        # Reuse the valuation join from the base class, then apply log transform.
        raw = super().compute(frame, ctx)
        return raw.map_elements(
            lambda x: math.log(x) if x is not None and x > 0 else None,
            return_dtype=pl.Float64,
        ).alias(self.name)
