"""Shared base for fundamental factors that map a column from ctx.extra['fundamentals']."""

from __future__ import annotations

import polars as pl

from cquant.factorlab.factor import Factor, FactorContext


class FundamentalFactor(Factor):
    """Base class for factors that pull a single column from ctx.extra['fundamentals'].

    Subclasses must set ``_column`` and ``name``.
    """

    _column: str

    @property
    def tags(self) -> list[str]:
        return ["fundamental"]

    def compute(self, frame: pl.DataFrame, ctx: FactorContext) -> pl.Series:
        fund = ctx.extra.get("fundamentals")
        if fund is None or fund.is_empty() or self._column not in fund.columns:
            return pl.Series(name=self.name, values=[None] * len(frame))

        # Build asset_id -> value lookup to avoid join cardinality issues on multi-date frames
        lookup = dict(zip(fund["asset_id"].to_list(), fund[self._column].to_list()))
        return frame["asset_id"].map_elements(
            lambda x: lookup.get(x), return_dtype=pl.Float64
        ).alias(self.name)
