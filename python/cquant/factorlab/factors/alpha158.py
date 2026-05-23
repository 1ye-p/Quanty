"""Alpha158 因子完整集合（Polars 实现）。

整合 KBAR（9个）、Rolling（16个原有）、以及新增 25+ 扩展因子，
共计 ≥50 个 Alpha158 因子。

来源：Microsoft Qlib Alpha158，用 Polars 重新实现，
不直接调用 Qlib 表达式引擎，保持 cQuant 计算层独立。
"""
from __future__ import annotations

import polars as pl

from cquant.factorlab.factor import Factor, FactorContext

# ── 导入现有因子 ─────────────────────────────────────────────────────────────
from cquant.factorlab.factors.kbar import KBAR_FACTORS  # 9 个
from cquant.factorlab.factors.alpha158_rolling import ALPHA158_ROLLING_FACTORS  # 16 个


class _A158Ext(Factor):
    """Alpha158 扩展因子基类（新增，非原有）。"""

    @property
    def tags(self) -> list[str]:
        return ["alpha158", "rolling", "price"]


class _Vol(Factor):
    """Alpha158 成交量因子基类。"""

    @property
    def tags(self) -> list[str]:
        return ["alpha158", "rolling", "volume"]


# ── MAX/MIN 扩展到更多窗口 [10, 30, 60] ──────────────────────────────────────

class MAX10(_A158Ext):
    """Source: Max($high, 10)/$close"""

    @property
    def name(self) -> str:
        return "MAX10"

    @property
    def lookback_days(self) -> int:
        return 25

    def compute(self, frame: pl.DataFrame, ctx: FactorContext) -> pl.Series:
        return (
            frame.sort(["asset_id", "trade_date"])
            .with_columns(
                (pl.col("high").rolling_max(window_size=10).over("asset_id") /
                 pl.col("close").clip(lower_bound=1e-12)).alias(self.name)
            )
        )[self.name]


class MAX30(_A158Ext):
    """Source: Max($high, 30)/$close"""

    @property
    def name(self) -> str:
        return "MAX30"

    @property
    def lookback_days(self) -> int:
        return 65

    def compute(self, frame: pl.DataFrame, ctx: FactorContext) -> pl.Series:
        return (
            frame.sort(["asset_id", "trade_date"])
            .with_columns(
                (pl.col("high").rolling_max(window_size=30).over("asset_id") /
                 pl.col("close").clip(lower_bound=1e-12)).alias(self.name)
            )
        )[self.name]


class MAX60(_A158Ext):
    """Source: Max($high, 60)/$close"""

    @property
    def name(self) -> str:
        return "MAX60"

    @property
    def lookback_days(self) -> int:
        return 125

    def compute(self, frame: pl.DataFrame, ctx: FactorContext) -> pl.Series:
        return (
            frame.sort(["asset_id", "trade_date"])
            .with_columns(
                (pl.col("high").rolling_max(window_size=60).over("asset_id") /
                 pl.col("close").clip(lower_bound=1e-12)).alias(self.name)
            )
        )[self.name]


class MIN10(_A158Ext):
    """Source: Min($low, 10)/$close"""

    @property
    def name(self) -> str:
        return "MIN10"

    @property
    def lookback_days(self) -> int:
        return 25

    def compute(self, frame: pl.DataFrame, ctx: FactorContext) -> pl.Series:
        return (
            frame.sort(["asset_id", "trade_date"])
            .with_columns(
                (pl.col("low").rolling_min(window_size=10).over("asset_id") /
                 pl.col("close").clip(lower_bound=1e-12)).alias(self.name)
            )
        )[self.name]


class MIN30(_A158Ext):
    """Source: Min($low, 30)/$close"""

    @property
    def name(self) -> str:
        return "MIN30"

    @property
    def lookback_days(self) -> int:
        return 65

    def compute(self, frame: pl.DataFrame, ctx: FactorContext) -> pl.Series:
        return (
            frame.sort(["asset_id", "trade_date"])
            .with_columns(
                (pl.col("low").rolling_min(window_size=30).over("asset_id") /
                 pl.col("close").clip(lower_bound=1e-12)).alias(self.name)
            )
        )[self.name]


class MIN60(_A158Ext):
    """Source: Min($low, 60)/$close"""

    @property
    def name(self) -> str:
        return "MIN60"

    @property
    def lookback_days(self) -> int:
        return 125

    def compute(self, frame: pl.DataFrame, ctx: FactorContext) -> pl.Series:
        return (
            frame.sort(["asset_id", "trade_date"])
            .with_columns(
                (pl.col("low").rolling_min(window_size=60).over("asset_id") /
                 pl.col("close").clip(lower_bound=1e-12)).alias(self.name)
            )
        )[self.name]


# ── 60 日 ROC/MA/STD ──────────────────────────────────────────────────────────

class ROC60(_A158Ext):
    """Source: Ref($close, 60)/$close"""

    @property
    def name(self) -> str:
        return "ROC60"

    @property
    def lookback_days(self) -> int:
        return 125

    def compute(self, frame: pl.DataFrame, ctx: FactorContext) -> pl.Series:
        return (
            frame.sort(["asset_id", "trade_date"])
            .with_columns(
                (pl.col("close").shift(60).over("asset_id") /
                 pl.col("close").clip(lower_bound=1e-12)).alias(self.name)
            )
        )[self.name]


class MA60(_A158Ext):
    """Source: Mean($close, 60)/$close"""

    @property
    def name(self) -> str:
        return "MA60"

    @property
    def lookback_days(self) -> int:
        return 125

    def compute(self, frame: pl.DataFrame, ctx: FactorContext) -> pl.Series:
        return (
            frame.sort(["asset_id", "trade_date"])
            .with_columns(
                (pl.col("close").rolling_mean(window_size=60).over("asset_id") /
                 pl.col("close").clip(lower_bound=1e-12)).alias(self.name)
            )
        )[self.name]


class STD60(_A158Ext):
    """Source: Std($close, 60)/$close"""

    @property
    def name(self) -> str:
        return "STD60"

    @property
    def lookback_days(self) -> int:
        return 125

    def compute(self, frame: pl.DataFrame, ctx: FactorContext) -> pl.Series:
        return (
            frame.sort(["asset_id", "trade_date"])
            .with_columns(
                (pl.col("close").rolling_std(window_size=60).over("asset_id") /
                 pl.col("close").clip(lower_bound=1e-12)).alias(self.name)
            )
        )[self.name]


# ── VMA：成交量均值 ──────────────────────────────────────────────────────────

class _VMA(_Vol):
    """VMA = rolling_mean(volume, n) / (volume + 1e-12)"""

    def __init__(self, n: int) -> None:
        self._n = n

    @property
    def name(self) -> str:
        return f"VMA{self._n}"

    @property
    def lookback_days(self) -> int:
        return self._n * 2

    def compute(self, frame: pl.DataFrame, ctx: FactorContext) -> pl.Series:
        return (
            frame.sort(["asset_id", "trade_date"])
            .with_columns(
                (pl.col("volume").rolling_mean(window_size=self._n).over("asset_id") /
                 (pl.col("volume") + 1e-12)).alias(self.name)
            )
        )[self.name]


class VMA5(_VMA):
    def __init__(self) -> None:
        super().__init__(5)


class VMA10(_VMA):
    def __init__(self) -> None:
        super().__init__(10)


class VMA20(_VMA):
    def __init__(self) -> None:
        super().__init__(20)


class VMA30(_VMA):
    def __init__(self) -> None:
        super().__init__(30)


# ── VSTD：成交量标准差 ────────────────────────────────────────────────────────

class _VSTD(_Vol):
    """VSTD = rolling_std(volume, n) / (volume + 1e-12)"""

    def __init__(self, n: int) -> None:
        self._n = n

    @property
    def name(self) -> str:
        return f"VSTD{self._n}"

    @property
    def lookback_days(self) -> int:
        return self._n * 2

    def compute(self, frame: pl.DataFrame, ctx: FactorContext) -> pl.Series:
        return (
            frame.sort(["asset_id", "trade_date"])
            .with_columns(
                (pl.col("volume").rolling_std(window_size=self._n).over("asset_id") /
                 (pl.col("volume") + 1e-12)).alias(self.name)
            )
        )[self.name]


class VSTD5(_VSTD):
    def __init__(self) -> None:
        super().__init__(5)


class VSTD10(_VSTD):
    def __init__(self) -> None:
        super().__init__(10)


class VSTD20(_VSTD):
    def __init__(self) -> None:
        super().__init__(20)


class VSTD30(_VSTD):
    def __init__(self) -> None:
        super().__init__(30)


# ── VROC：成交量变化率 ────────────────────────────────────────────────────────

class _VROC(_Vol):
    """VROC = volume.shift(n) / (volume + 1e-12)"""

    def __init__(self, n: int) -> None:
        self._n = n

    @property
    def name(self) -> str:
        return f"VROC{self._n}"

    @property
    def lookback_days(self) -> int:
        return self._n * 2

    def compute(self, frame: pl.DataFrame, ctx: FactorContext) -> pl.Series:
        return (
            frame.sort(["asset_id", "trade_date"])
            .with_columns(
                (pl.col("volume").shift(self._n).over("asset_id") /
                 (pl.col("volume") + 1e-12)).alias(self.name)
            )
        )[self.name]


class VROC5(_VROC):
    def __init__(self) -> None:
        super().__init__(5)


class VROC10(_VROC):
    def __init__(self) -> None:
        super().__init__(10)


class VROC20(_VROC):
    def __init__(self) -> None:
        super().__init__(20)


class VROC30(_VROC):
    def __init__(self) -> None:
        super().__init__(30)


# ── RSV：相对强弱值（%K）──────────────────────────────────────────────────────

class _RSV(_A158Ext):
    """Source: ($close-Min($low,n))/(Max($high,n)-Min($low,n)+1e-12)"""

    def __init__(self, n: int) -> None:
        self._n = n

    @property
    def name(self) -> str:
        return f"RSV{self._n}"

    @property
    def lookback_days(self) -> int:
        return self._n * 2

    def compute(self, frame: pl.DataFrame, ctx: FactorContext) -> pl.Series:
        return (
            frame.sort(["asset_id", "trade_date"])
            .with_columns([
                pl.col("low").rolling_min(window_size=self._n).over("asset_id").alias("_min_low"),
                pl.col("high").rolling_max(window_size=self._n).over("asset_id").alias("_max_high"),
            ])
            .with_columns(
                ((pl.col("close") - pl.col("_min_low")) /
                 (pl.col("_max_high") - pl.col("_min_low") + 1e-12)).alias(self.name)
            )
        )[self.name]


class RSV5(_RSV):
    def __init__(self) -> None:
        super().__init__(5)


class RSV10(_RSV):
    def __init__(self) -> None:
        super().__init__(10)


class RSV20(_RSV):
    def __init__(self) -> None:
        super().__init__(20)


class RSV30(_RSV):
    def __init__(self) -> None:
        super().__init__(30)


# ── 合并所有 Alpha158 因子 ───────────────────────────────────────────────────
# 9 KBAR + 16 Rolling + 6 MAX/MIN扩展 + 3 ROC/MA/STD-60
# + 4 VMA + 4 VSTD + 4 VROC + 4 RSV = 50

_EXTENDED: list[Factor] = [
    MAX10(), MAX30(), MAX60(),
    MIN10(), MIN30(), MIN60(),
    ROC60(), MA60(), STD60(),
    VMA5(), VMA10(), VMA20(), VMA30(),
    VSTD5(), VSTD10(), VSTD20(), VSTD30(),
    VROC5(), VROC10(), VROC20(), VROC30(),
    RSV5(), RSV10(), RSV20(), RSV30(),
]

ALPHA158_FACTORS: list[Factor] = (
    list(KBAR_FACTORS)
    + list(ALPHA158_ROLLING_FACTORS)
    + _EXTENDED
)
