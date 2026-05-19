"""Built-in technical factors: z-score, MA ratio, RSI, Bollinger Bands."""

from __future__ import annotations

import polars as pl

from cquant.factorlab.factor import Factor, FactorContext


class ZscoreClose60d(Factor):
    """60-day z-score of close price (mean-reversion signal)."""

    @property
    def name(self) -> str:
        return "zscore_close_60d"

    @property
    def tags(self) -> list[str]:
        return ["technical", "mean_reversion"]

    def compute(self, frame: pl.DataFrame, ctx: FactorContext) -> pl.Series:
        return (
            frame.sort(["asset_id", "trade_date"])
            .with_columns(
                pl.col("close").rolling_mean(60).over("asset_id").alias("_ma60"),
                pl.col("close").rolling_std(60).over("asset_id").alias("_std60"),
            )
            .with_columns(
                ((pl.col("close") - pl.col("_ma60")) / pl.col("_std60").clip(lower_bound=1e-9))
                .alias(self.name)
            )
        )[self.name]


class MA20dRatio(Factor):
    """Price relative to 20-day moving average (trend strength indicator)."""

    @property
    def name(self) -> str:
        return "ma_20d_ratio"

    @property
    def tags(self) -> list[str]:
        return ["technical", "trend"]

    def compute(self, frame: pl.DataFrame, ctx: FactorContext) -> pl.Series:
        return (
            frame.sort(["asset_id", "trade_date"])
            .with_columns(
                pl.col("close").rolling_mean(20).over("asset_id").alias("_ma20")
            )
            .with_columns(
                (pl.col("close") / pl.col("_ma20").clip(lower_bound=1e-9)).alias(self.name)
            )
        )[self.name]


class RSI14d(Factor):
    """14-day Relative Strength Index (momentum oscillator)."""

    @property
    def name(self) -> str:
        return "rsi_14d"

    @property
    def tags(self) -> list[str]:
        return ["technical", "momentum"]

    def compute(self, frame: pl.DataFrame, ctx: FactorContext) -> pl.Series:
        return (
            frame.sort(["asset_id", "trade_date"])
            .with_columns(
                pl.col("close").diff().over("asset_id").alias("_price_change")
            )
            .with_columns(
                pl.when(pl.col("_price_change") > 0)
                .then(pl.col("_price_change"))
                .otherwise(0.0)
                .alias("_gain"),
                pl.when(pl.col("_price_change") < 0)
                .then(-pl.col("_price_change"))
                .otherwise(0.0)
                .alias("_loss"),
            )
            .with_columns(
                pl.col("_gain").rolling_mean(14).over("asset_id").alias("_avg_gain"),
                pl.col("_loss").rolling_mean(14).over("asset_id").alias("_avg_loss"),
            )
            .with_columns(
                (100.0 - 100.0 / (1.0 + pl.col("_avg_gain") / pl.col("_avg_loss").clip(lower_bound=1e-9)))
                .alias(self.name)
            )
        )[self.name]


class BollingerBandWidth20d(Factor):
    """20-day Bollinger Band width (volatility indicator)."""

    @property
    def name(self) -> str:
        return "bollinger_width_20d"

    @property
    def tags(self) -> list[str]:
        return ["technical", "volatility"]

    def compute(self, frame: pl.DataFrame, ctx: FactorContext) -> pl.Series:
        return (
            frame.sort(["asset_id", "trade_date"])
            .with_columns(
                pl.col("close").rolling_mean(20).over("asset_id").alias("_ma20"),
                pl.col("close").rolling_std(20).over("asset_id").alias("_std20"),
            )
            .with_columns(
                (2.0 * pl.col("_std20") / pl.col("_ma20").clip(lower_bound=1e-9))
                .alias(self.name)
            )
        )[self.name]


class PriceHigh20dRatio(Factor):
    """Current price relative to 20-day high (breakout signal)."""

    @property
    def name(self) -> str:
        return "price_high_20d_ratio"

    @property
    def tags(self) -> list[str]:
        return ["technical", "breakout"]

    def compute(self, frame: pl.DataFrame, ctx: FactorContext) -> pl.Series:
        return (
            frame.sort(["asset_id", "trade_date"])
            .with_columns(
                pl.col("high").cast(pl.Float64).rolling_max(20).over("asset_id").alias("_high20"),
            )
            .with_columns(
                (pl.col("close").cast(pl.Float64) / pl.col("_high20").clip(lower_bound=1e-9))
                .alias(self.name)
            )
        )[self.name]
