"""Built-in momentum factors: N-day returns."""

from __future__ import annotations

import polars as pl

from cquant.factorlab.factor import Factor, FactorContext


class _ReturnNd(Factor):
    """N-day simple return: (close_t / close_{t-n}) - 1."""

    def __init__(self, n: int) -> None:
        self._n = n

    @property
    def name(self) -> str:
        return f"ret_{self._n}d"

    @property
    def tags(self) -> list[str]:
        return ["momentum", "price"]

    @property
    def lookback_days(self) -> int:
        # 1 trading day ≈ 1.55 calendar days, plus 30-day safety buffer
        return int(self._n * 1.55) + 30

    def compute(self, frame: pl.DataFrame, ctx: FactorContext) -> pl.Series:
        return (
            frame.sort(["asset_id", "trade_date"])
            .with_columns(
                (pl.col("close") / pl.col("close").shift(self._n).over("asset_id") - 1)
                .clip(lower_bound=-0.5, upper_bound=0.5)
                .alias(self.name)
            )
        )[self.name]


class Return1d(_ReturnNd):
    def __init__(self) -> None:
        super().__init__(1)


class Return5d(_ReturnNd):
    def __init__(self) -> None:
        super().__init__(5)


class Return20d(_ReturnNd):
    def __init__(self) -> None:
        super().__init__(20)


class Return60d(_ReturnNd):
    def __init__(self) -> None:
        super().__init__(60)


class Return120d(_ReturnNd):
    def __init__(self) -> None:
        super().__init__(120)


class Return240d(_ReturnNd):
    def __init__(self) -> None:
        super().__init__(240)


class Momentum12_1(Factor):
    """12-month momentum excluding the most recent month (classic Jegadeesh-Titman)."""

    @property
    def name(self) -> str:
        return "momentum_12_1"

    @property
    def tags(self) -> list[str]:
        return ["momentum", "price"]

    @property
    def lookback_days(self) -> int:
        # Shifts by 252 trading days ≈ 390 + 30 buffer = 420 calendar days
        return 420

    def compute(self, frame: pl.DataFrame, ctx: FactorContext) -> pl.Series:
        return (
            frame.sort(["asset_id", "trade_date"])
            .with_columns(
                (pl.col("close").shift(21).over("asset_id") / pl.col("close").shift(252).over("asset_id") - 1)
                .alias(self.name)
            )
        )[self.name]
