"""Alpha158 Rolling 因子 — 滑动窗口技术因子。

来源：Microsoft Qlib Alpha158DL.get_feature_config() Rolling 组
窗口：[5, 10, 20, 30]
"""
from __future__ import annotations

import polars as pl

from cquant.factorlab.factor import Factor, FactorContext


class _RollingBase(Factor):
    @property
    def tags(self) -> list[str]:
        return ["alpha158", "rolling", "price"]


class _ROC(_RollingBase):
    """ROC = close.shift(n) / close（n 天前收盘价 / 当前收盘价）"""
    def __init__(self, n: int) -> None:
        self._n = n

    @property
    def description(self) -> str:
        return f"{self._n} 日 ROC（变动率指标）：close.shift({self._n}) / close"

    @property
    def name(self) -> str:
        return f"ROC{self._n}"

    @property
    def lookback_days(self) -> int:
        return self._n * 2

    def compute(self, frame: pl.DataFrame, ctx: FactorContext) -> pl.Series:
        return (
            frame.sort(["asset_id", "trade_date"])
            .with_columns(
                (pl.col("close").shift(self._n).over("asset_id") /
                 pl.col("close").clip(lower_bound=1e-12))
                .alias(self.name)
            )
        )[self.name]


class ROC5(_ROC):
    def __init__(self) -> None:
        super().__init__(5)


class ROC10(_ROC):
    def __init__(self) -> None:
        super().__init__(10)


class ROC20(_ROC):
    def __init__(self) -> None:
        super().__init__(20)


class ROC30(_ROC):
    def __init__(self) -> None:
        super().__init__(30)


class _MA(_RollingBase):
    """MA = rolling_mean(close, n) / close（n 天均价 / 当前价）"""
    def __init__(self, n: int) -> None:
        self._n = n

    @property
    def description(self) -> str:
        return f"{self._n} 日均线比值：rolling_mean(close, {self._n}) / close"

    @property
    def name(self) -> str:
        return f"MA{self._n}"

    @property
    def lookback_days(self) -> int:
        return self._n * 2

    def compute(self, frame: pl.DataFrame, ctx: FactorContext) -> pl.Series:
        return (
            frame.sort(["asset_id", "trade_date"])
            .with_columns(
                (pl.col("close").rolling_mean(window_size=self._n).over("asset_id") /
                 pl.col("close").clip(lower_bound=1e-12))
                .alias(self.name)
            )
        )[self.name]


class MA5(_MA):
    def __init__(self) -> None:
        super().__init__(5)


class MA10(_MA):
    def __init__(self) -> None:
        super().__init__(10)


class MA20(_MA):
    def __init__(self) -> None:
        super().__init__(20)


class MA30(_MA):
    def __init__(self) -> None:
        super().__init__(30)


class _STD(_RollingBase):
    """STD = rolling_std(close, n) / close（n 天波动率 / 当前价）"""
    def __init__(self, n: int) -> None:
        self._n = n

    @property
    def description(self) -> str:
        return f"{self._n} 日收盘价标准差 / close"

    @property
    def name(self) -> str:
        return f"STD{self._n}"

    @property
    def lookback_days(self) -> int:
        return self._n * 2

    def compute(self, frame: pl.DataFrame, ctx: FactorContext) -> pl.Series:
        return (
            frame.sort(["asset_id", "trade_date"])
            .with_columns(
                (pl.col("close").rolling_std(window_size=self._n).over("asset_id") /
                 pl.col("close").clip(lower_bound=1e-12))
                .alias(self.name)
            )
        )[self.name]


class STD5(_STD):
    def __init__(self) -> None:
        super().__init__(5)


class STD10(_STD):
    def __init__(self) -> None:
        super().__init__(10)


class STD20(_STD):
    def __init__(self) -> None:
        super().__init__(20)


class STD30(_STD):
    def __init__(self) -> None:
        super().__init__(30)


class _MAX(_RollingBase):
    """MAX = rolling_max(high, n) / close（n 天最高价 / 当前价）"""
    def __init__(self, n: int) -> None:
        self._n = n

    @property
    def description(self) -> str:
        return f"{self._n} 日最高价 / close"

    @property
    def name(self) -> str:
        return f"MAX{self._n}"

    @property
    def lookback_days(self) -> int:
        return self._n * 2

    def compute(self, frame: pl.DataFrame, ctx: FactorContext) -> pl.Series:
        return (
            frame.sort(["asset_id", "trade_date"])
            .with_columns(
                (pl.col("high").rolling_max(window_size=self._n).over("asset_id") /
                 pl.col("close").clip(lower_bound=1e-12))
                .alias(self.name)
            )
        )[self.name]


class MAX5(_MAX):
    def __init__(self) -> None:
        super().__init__(5)


class MAX20(_MAX):
    def __init__(self) -> None:
        super().__init__(20)


class _MIN(_RollingBase):
    """MIN = rolling_min(low, n) / close（n 天最低价 / 当前价）"""
    def __init__(self, n: int) -> None:
        self._n = n

    @property
    def description(self) -> str:
        return f"{self._n} 日最低价 / close"

    @property
    def name(self) -> str:
        return f"MIN{self._n}"

    @property
    def lookback_days(self) -> int:
        return self._n * 2

    def compute(self, frame: pl.DataFrame, ctx: FactorContext) -> pl.Series:
        return (
            frame.sort(["asset_id", "trade_date"])
            .with_columns(
                (pl.col("low").rolling_min(window_size=self._n).over("asset_id") /
                 pl.col("close").clip(lower_bound=1e-12))
                .alias(self.name)
            )
        )[self.name]


class MIN5(_MIN):
    def __init__(self) -> None:
        super().__init__(5)


class MIN20(_MIN):
    def __init__(self) -> None:
        super().__init__(20)


ALPHA158_ROLLING_FACTORS: list[Factor] = [
    ROC5(), ROC10(), ROC20(), ROC30(),
    MA5(), MA10(), MA20(), MA30(),
    STD5(), STD10(), STD20(), STD30(),
    MAX5(), MAX20(),
    MIN5(), MIN20(),
]
