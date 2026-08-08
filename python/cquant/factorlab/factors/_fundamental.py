"""Shared base classes for fundamental and valuation factors.

``FundamentalFactor`` reads a single column from ``ctx.extra['fundamentals']``
(earnings fields, one latest-disclosed row per asset — announce_date PIT).

``ValuationFactor`` reads a single column from ``ctx.extra['valuation']``
(silver_valuation_daily, per-(asset_id, trade_date) rows — naturally PIT) and
aligns by both ``asset_id`` and ``trade_date``.
"""

from __future__ import annotations

import polars as pl

from cquant.factorlab.factor import Factor, FactorContext


class FundamentalFactor(Factor):
    """Base class for factors that pull a single column from ctx.extra['fundamentals'].

    Earnings factors (ROE/ROA/margins/growth): ``fundamentals`` holds one
    latest-disclosed row per asset (announce_date PIT), so a simple
    ``asset_id`` lookup is correct.

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


class ValuationFactor(Factor):
    """Base class for factors that pull a single column from ctx.extra['valuation'].

    Valuation factors (PE/PB/PS/MarketCap/DividendYield/TurnoverRate):
    ``valuation`` is silver_valuation_daily with one row per
    ``(asset_id, trade_date)``, so we must align on *both* keys. The join is
    naturally PIT because valuation only contains rows up to ``spec.end_date``.

    Subclasses must set ``_column`` and ``name``.
    """

    _column: str

    @property
    def tags(self) -> list[str]:
        return ["fundamental", "value"]

    def _align_trade_date(self, df: pl.DataFrame, ref: pl.DataFrame) -> pl.DataFrame:
        """Coerce valuation trade_date to the same dtype as the price frame's."""
        ref_dtype = ref["trade_date"].dtype
        if df["trade_date"].dtype == ref_dtype:
            return df
        if ref_dtype == pl.Date:
            if df["trade_date"].dtype == pl.Utf8:
                return df.with_columns(pl.col("trade_date").str.to_date())
            return df.with_columns(pl.col("trade_date").cast(pl.Date))
        # Fall back to string representation for any non-date ref dtype
        return df.with_columns(pl.col("trade_date").cast(pl.Utf8))

    def compute(self, frame: pl.DataFrame, ctx: FactorContext) -> pl.Series:
        val = ctx.extra.get("valuation")
        if (
            val is None
            or val.is_empty()
            or self._column not in val.columns
            or "trade_date" not in val.columns
        ):
            return pl.Series(name=self.name, values=[None] * len(frame))

        val = self._align_trade_date(val, frame)
        col = (
            frame.select(["asset_id", "trade_date"])
            .join(
                val.select(["asset_id", "trade_date", self._column]),
                on=["asset_id", "trade_date"],
                how="left",
            )
            .rename({self._column: self.name})
        )
        # Cast to Float64 so downstream consumers get a consistent numeric dtype
        if col[self.name].dtype != pl.Float64:
            col = col.with_columns(pl.col(self.name).cast(pl.Float64))
        return col[self.name]
