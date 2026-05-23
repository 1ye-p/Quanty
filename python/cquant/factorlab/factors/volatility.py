"""Built-in volatility factors: N-day realized volatility."""

from __future__ import annotations

import polars as pl

from cquant.factorlab.factor import Factor, FactorContext


class _VolNd(Factor):
    """N-day rolling standard deviation of daily log returns (annualized)."""

    def __init__(self, n: int) -> None:
        self._n = n

    @property
    def name(self) -> str:
        return f"vol_{self._n}d"

    @property
    def tags(self) -> list[str]:
        return ["volatility", "risk"]

    @property
    def lookback_days(self) -> int:
        return max(120, int(self._n * 1.55) + 30)

    def compute(self, frame: pl.DataFrame, ctx: FactorContext) -> pl.Series:
        return (
            frame.sort(["asset_id", "trade_date"])
            .with_columns(
                pl.col("close").log().diff().over("asset_id").alias("_log_ret")
            )
            .with_columns(
                (pl.col("_log_ret").rolling_std(window_size=self._n).over("asset_id") * (252**0.5))
                .alias(self.name)
            )
        )[self.name]


class Vol20d(_VolNd):
    def __init__(self) -> None:
        super().__init__(20)


class Vol60d(_VolNd):
    def __init__(self) -> None:
        super().__init__(60)


class Vol120d(_VolNd):
    def __init__(self) -> None:
        super().__init__(120)


class DownsideVol20d(Factor):
    """20-day downside volatility (only negative returns)."""

    @property
    def name(self) -> str:
        return "downside_vol_20d"

    @property
    def tags(self) -> list[str]:
        return ["volatility", "risk"]

    def compute(self, frame: pl.DataFrame, ctx: FactorContext) -> pl.Series:
        return (
            frame.sort(["asset_id", "trade_date"])
            .with_columns(
                pl.col("close").log().diff().over("asset_id").alias("_log_ret")
            )
            .with_columns(
                # Square of negative returns only (positive -> 0)
                pl.when(pl.col("_log_ret") < 0)
                .then(pl.col("_log_ret") ** 2)
                .otherwise(0.0)
                .alias("_neg_ret_sq")
            )
            .with_columns(
                # Mean of squared negatives over window -> sqrt -> annualize
                (pl.col("_neg_ret_sq").rolling_mean(window_size=20).over("asset_id").sqrt() * (252**0.5))
                .alias(self.name)
            )
        )[self.name]


class MaxDrawdown20d(Factor):
    """20-day maximum drawdown."""

    @property
    def name(self) -> str:
        return "max_drawdown_20d"

    @property
    def tags(self) -> list[str]:
        return ["volatility", "risk"]

    def compute(self, frame: pl.DataFrame, ctx: FactorContext) -> pl.Series:
        return (
            frame.sort(["asset_id", "trade_date"])
            .with_columns(
                pl.col("close").cast(pl.Float64).rolling_max(20).over("asset_id").alias("_peak20"),
            )
            .with_columns(
                ((pl.col("close").cast(pl.Float64) - pl.col("_peak20")) / pl.col("_peak20").clip(lower_bound=1e-9))
                .alias(self.name)
            )
        )[self.name]
