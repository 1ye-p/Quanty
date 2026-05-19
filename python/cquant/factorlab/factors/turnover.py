"""Built-in turnover factors: volume-based liquidity signals."""

from __future__ import annotations

import polars as pl

from cquant.factorlab.factor import Factor, FactorContext


class TurnoverRate20d(Factor):
    """20-day average turnover rate (volume / 20-day avg volume)."""

    @property
    def name(self) -> str:
        return "turnover_rate_20d"

    @property
    def tags(self) -> list[str]:
        return ["turnover", "liquidity"]

    def compute(self, frame: pl.DataFrame, ctx: FactorContext) -> pl.Series:
        return (
            frame.sort(["asset_id", "trade_date"])
            .with_columns(
                pl.col("volume").rolling_mean(20).over("asset_id").alias("_vol_ma20"),
            )
            .with_columns(
                (pl.col("volume") / pl.col("_vol_ma20").clip(lower_bound=1e-9))
                .alias(self.name)
            )
        )[self.name]


class VolumeRatio5d(Factor):
    """5-day volume ratio (short-term vs 20-day average)."""

    @property
    def name(self) -> str:
        return "volume_ratio_5d"

    @property
    def tags(self) -> list[str]:
        return ["turnover", "liquidity"]

    def compute(self, frame: pl.DataFrame, ctx: FactorContext) -> pl.Series:
        return (
            frame.sort(["asset_id", "trade_date"])
            .with_columns(
                pl.col("volume").rolling_mean(5).over("asset_id").alias("_vol_ma5"),
                pl.col("volume").rolling_mean(20).over("asset_id").alias("_vol_ma20"),
            )
            .with_columns(
                (pl.col("_vol_ma5") / pl.col("_vol_ma20").clip(lower_bound=1e-9))
                .alias(self.name)
            )
        )[self.name]


class AmountRatio5d(Factor):
    """5-day amount ratio (short-term vs 20-day average)."""

    @property
    def name(self) -> str:
        return "amount_ratio_5d"

    @property
    def tags(self) -> list[str]:
        return ["turnover", "liquidity"]

    def compute(self, frame: pl.DataFrame, ctx: FactorContext) -> pl.Series:
        return (
            frame.sort(["asset_id", "trade_date"])
            .with_columns(
                pl.col("amount").rolling_mean(5).over("asset_id").alias("_amt_ma5"),
                pl.col("amount").rolling_mean(20).over("asset_id").alias("_amt_ma20"),
            )
            .with_columns(
                (pl.col("_amt_ma5") / pl.col("_amt_ma20").clip(lower_bound=1e-9))
                .alias(self.name)
            )
        )[self.name]
