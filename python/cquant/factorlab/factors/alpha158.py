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
    def description(self) -> str:
        name = self.__class__.__name__
        if name.startswith("MAX"):
            return f"{name[3:]} 日最高价 / close"
        if name.startswith("MIN"):
            return f"{name[3:]} 日最低价 / close"
        if name.startswith("ROC"):
            return f"{name[3:]} 日 ROC（变动率）"
        if name.startswith("MA"):
            return f"{name[2:]} 日均线比值"
        if name.startswith("STD"):
            return f"{name[3:]} 日收盘价标准差 / close"
        if name.startswith("RSV"):
            return f"{name[3:]} 日 RSV（未成熟随机值）"
        if name.startswith("BETA"):
            return f"{name[4:]} 日线性回归斜率（close vs time）"
        if name.startswith("RSQR"):
            return f"{name[4:]} 日线性回归 R²"
        if name.startswith("RESI"):
            return f"{name[4:]} 日线性回归残差"
        if name.startswith("QTLU"):
            return f"{name[4:]} 日 80 分位 / close"
        if name.startswith("QTLD"):
            return f"{name[4:]} 日 20 分位 / close"
        if name.startswith("RANK"):
            return f"{name[4:]} 日滚动排名百分位"
        if name.startswith("IMXD"):
            return f"{name[4:]} 日 IMAX - IMIN（极值位置差）"
        if name.startswith("IMAX"):
            return f"{name[4:]} 日距最高价天数"
        if name.startswith("IMIN"):
            return f"{name[4:]} 日距最低价天数"
        return (self.__class__.__doc__ or "").strip().split("\n")[0]

    @property
    def tags(self) -> list[str]:
        return ["alpha158", "rolling", "price"]


class _Vol(Factor):
    """Alpha158 成交量因子基类。"""

    @property
    def description(self) -> str:
        name = self.__class__.__name__
        if "VMA" in name:
            return f"{self._n} 日成交量均线比值"
        if "VSTD" in name:
            return f"{self._n} 日成交量标准差"
        if "VROC" in name:
            return f"{self._n} 日成交量变动率"
        return ""

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


# ── BETA / RSQR / RESI：滚动线性回归（close vs time index）──────────────────
#
#  对每个滚动窗口，以 [0, 1, ..., n-1] 为自变量 x，close 为因变量 y，
#  计算 OLS 回归的斜率（BETA）、决定系数 R²（RSQR）、末期残差（RESI）。
#
#  使用 Polars 表达式避免 Python 循环：
#    sum_x  = n*(n-1)/2        (常数)
#    sum_x2 = n*(n-1)*(2n-1)/6 (常数)
#    slope  = (n*Σxy - Σx*Σy) / (n*Σx2 - (Σx)²)
#    预测值 ŷ_i = intercept + slope * x_i
#    residual = y_last - ŷ_last
#    R² = 1 - SS_res / SS_tot


class _Reg(_A158Ext):
    """线性回归因子基类（BETA / RSQR / RESI）。

    子类通过 _mode 指定输出类型：
        "beta"  → 斜率
        "rsqr"  → R²
        "resi"  → 末期残差
    """

    _mode: str = "beta"

    def __init__(self, n: int) -> None:
        self._n = n

    @property
    def name(self) -> str:
        prefix = {"beta": "BETA", "rsqr": "RSQR", "resi": "RESI"}[self._mode]
        return f"{prefix}{self._n}"

    @property
    def lookback_days(self) -> int:
        return self._n * 2

    def compute(self, frame: pl.DataFrame, ctx: FactorContext) -> pl.Series:
        import numpy as np

        n = self._n
        x = np.arange(n, dtype=np.float64)
        sum_x = x.sum()
        sum_x2 = (x**2).sum()
        denom = n * sum_x2 - sum_x * sum_x
        mode = self._mode

        def _ols(close_arr: np.ndarray) -> np.ndarray:
            """Vectorised rolling OLS over a single asset's close series."""
            result = np.full(len(close_arr), np.nan)
            for i in range(n - 1, len(close_arr)):
                win = close_arr[i - n + 1: i + 1]
                sum_y = win.sum()
                sum_xy = (x * win).sum()
                slope = (n * sum_xy - sum_x * sum_y) / denom
                intercept = (sum_y - slope * sum_x) / n

                if mode == "beta":
                    result[i] = slope
                elif mode == "rsqr":
                    mean_y = sum_y / n
                    pred = intercept + slope * x
                    ss_res = ((win - pred) ** 2).sum()
                    ss_tot = ((win - mean_y) ** 2).sum()
                    result[i] = 1.0 - ss_res / (ss_tot + 1e-30)
                else:  # resi
                    last_pred = intercept + slope * (n - 1)
                    result[i] = win[-1] - last_pred
            return result

        return (
            frame.sort(["asset_id", "trade_date"])
            .with_columns(
                pl.col("close")
                .map_batches(
                    lambda s: _ols(s.to_numpy()),
                    return_dtype=pl.Float64,
                )
                .over("asset_id")
                .alias(self.name)
            )
        )[self.name]


# Concrete classes: BETA / RSQR / RESI × windows [5, 10, 20, 30, 60]


class BETA5(_Reg):
    _mode = "beta"
    def __init__(self) -> None:
        super().__init__(5)


class BETA10(_Reg):
    _mode = "beta"
    def __init__(self) -> None:
        super().__init__(10)


class BETA20(_Reg):
    _mode = "beta"
    def __init__(self) -> None:
        super().__init__(20)


class BETA30(_Reg):
    _mode = "beta"
    def __init__(self) -> None:
        super().__init__(30)


class BETA60(_Reg):
    _mode = "beta"
    def __init__(self) -> None:
        super().__init__(60)


class RSQR5(_Reg):
    _mode = "rsqr"
    def __init__(self) -> None:
        super().__init__(5)


class RSQR10(_Reg):
    _mode = "rsqr"
    def __init__(self) -> None:
        super().__init__(10)


class RSQR20(_Reg):
    _mode = "rsqr"
    def __init__(self) -> None:
        super().__init__(20)


class RSQR30(_Reg):
    _mode = "rsqr"
    def __init__(self) -> None:
        super().__init__(30)


class RSQR60(_Reg):
    _mode = "rsqr"
    def __init__(self) -> None:
        super().__init__(60)


class RESI5(_Reg):
    _mode = "resi"
    def __init__(self) -> None:
        super().__init__(5)


class RESI10(_Reg):
    _mode = "resi"
    def __init__(self) -> None:
        super().__init__(10)


class RESI20(_Reg):
    _mode = "resi"
    def __init__(self) -> None:
        super().__init__(20)


class RESI30(_Reg):
    _mode = "resi"
    def __init__(self) -> None:
        super().__init__(30)


class RESI60(_Reg):
    _mode = "resi"
    def __init__(self) -> None:
        super().__init__(60)


# ── QTLU / QTLD：滚动分位数 ──────────────────────────────────────────────────
#
#  QTLU = rolling_quantile(close, q=0.8, n) / close
#  QTLD = rolling_quantile(close, q=0.2, n) / close


class _Qtl(_A158Ext):
    """滚动分位数因子基类（QTLU / QTLD）。

    子类通过 _quantile 指定分位数（0.0~1.0）。
    """

    _quantile: float = 0.5

    def __init__(self, n: int) -> None:
        self._n = n

    @property
    def name(self) -> str:
        prefix = "QTLU" if self._quantile >= 0.5 else "QTLD"
        return f"{prefix}{self._n}"

    @property
    def lookback_days(self) -> int:
        return self._n * 2

    def compute(self, frame: pl.DataFrame, ctx: FactorContext) -> pl.Series:
        return (
            frame.sort(["asset_id", "trade_date"])
            .with_columns(
                (pl.col("close")
                 .rolling_quantile(self._quantile, window_size=self._n)
                 .over("asset_id") /
                 pl.col("close").clip(lower_bound=1e-12))
                .alias(self.name)
            )
        )[self.name]


class QTLU5(_Qtl):
    _quantile = 0.8
    def __init__(self) -> None:
        super().__init__(5)


class QTLU10(_Qtl):
    _quantile = 0.8
    def __init__(self) -> None:
        super().__init__(10)


class QTLU20(_Qtl):
    _quantile = 0.8
    def __init__(self) -> None:
        super().__init__(20)


class QTLU30(_Qtl):
    _quantile = 0.8
    def __init__(self) -> None:
        super().__init__(30)


class QTLU60(_Qtl):
    _quantile = 0.8
    def __init__(self) -> None:
        super().__init__(60)


class QTLD5(_Qtl):
    _quantile = 0.2
    def __init__(self) -> None:
        super().__init__(5)


class QTLD10(_Qtl):
    _quantile = 0.2
    def __init__(self) -> None:
        super().__init__(10)


class QTLD20(_Qtl):
    _quantile = 0.2
    def __init__(self) -> None:
        super().__init__(20)


class QTLD30(_Qtl):
    _quantile = 0.2
    def __init__(self) -> None:
        super().__init__(30)


class QTLD60(_Qtl):
    _quantile = 0.2
    def __init__(self) -> None:
        super().__init__(60)


# ── RANK：当前价格在滚动窗口中的排名百分位 ──────────────────────────────────
#
#  RANK = (close < current_close).sum() / window_size
#  使用 Polars rank 然后归一化到 [0, 1]


class _Rank(_A158Ext):
    """滚动窗口内排名百分位因子。

    RANK = (count of close_j < close_i in window) / window_size，
    值在 [0, 1] 之间，1 表示当前 close 是窗口内最高。
    使用 map_batches + numpy 实现滚动 rank。
    """

    def __init__(self, n: int) -> None:
        self._n = n

    @property
    def name(self) -> str:
        return f"RANK{self._n}"

    @property
    def lookback_days(self) -> int:
        return self._n * 2

    def compute(self, frame: pl.DataFrame, ctx: FactorContext) -> pl.Series:
        import numpy as np

        n = self._n

        def _rolling_rank(arr: np.ndarray) -> np.ndarray:
            """Rolling rank percentile: (count of values < current) / window_size."""
            result = np.full(len(arr), np.nan)
            for i in range(n - 1, len(arr)):
                win = arr[i - n + 1: i + 1]
                current = win[-1]
                result[i] = np.sum(win < current) / n
            return result

        return (
            frame.sort(["asset_id", "trade_date"])
            .with_columns(
                pl.col("close")
                .map_batches(
                    lambda s: _rolling_rank(s.to_numpy()),
                    return_dtype=pl.Float64,
                )
                .over("asset_id")
                .alias(self.name)
            )
        )[self.name]


class RANK5(_Rank):
    def __init__(self) -> None:
        super().__init__(5)


class RANK10(_Rank):
    def __init__(self) -> None:
        super().__init__(10)


class RANK20(_Rank):
    def __init__(self) -> None:
        super().__init__(20)


class RANK30(_Rank):
    def __init__(self) -> None:
        super().__init__(30)


class RANK60(_Rank):
    def __init__(self) -> None:
        super().__init__(60)


# ── IMAX / IMIN / IMXD：滚动窗口内极值位置 ──────────────────────────────────
#
#  IMAX = days since highest high in rolling window (0 = today is the max)
#  IMIN = days since lowest low in rolling window (0 = today is the min)
#  IMXD = IMAX - IMIN
#
#  使用 map_batches + numpy 实现 rolling argmax/argmin from end


class _ImaxMin(_A158Ext):
    """滚动窗口内极值位置因子基类（IMAX / IMIN / IMXD）。

    子类通过 _mode 指定类型：
        "imax"  → 天数 since 最高价
        "imin"  → 天数 since 最低价
        "imxd"  → IMAX - IMIN
    """

    _mode: str = "imax"

    def __init__(self, n: int) -> None:
        self._n = n

    @property
    def name(self) -> str:
        prefix = {"imax": "IMAX", "imin": "IMIN", "imxd": "IMXD"}[self._mode]
        return f"{prefix}{self._n}"

    @property
    def lookback_days(self) -> int:
        return self._n * 2

    def compute(self, frame: pl.DataFrame, ctx: FactorContext) -> pl.Series:
        import numpy as np

        n = self._n
        mode = self._mode

        def _rolling_days_since_extreme(arr: np.ndarray, kind: str) -> np.ndarray:
            """Compute days since max/min in rolling window from the end."""
            result = np.full(len(arr), np.nan)
            for i in range(n - 1, len(arr)):
                win = arr[i - n + 1: i + 1]
                if kind == "max":
                    arg = np.argmax(win)
                else:
                    arg = np.argmin(win)
                result[i] = n - 1 - arg
            return result

        if mode in ("imax", "imin"):
            col = "high" if mode == "imax" else "low"
            kind = "max" if mode == "imax" else "min"
            return (
                frame.sort(["asset_id", "trade_date"])
                .with_columns(
                    pl.col(col)
                    .map_batches(
                        lambda s: _rolling_days_since_extreme(s.to_numpy(), kind),
                        return_dtype=pl.Float64,
                    )
                    .over("asset_id")
                    .alias(self.name)
                )
            )[self.name]
        else:  # imxd
            return (
                frame.sort(["asset_id", "trade_date"])
                .with_columns([
                    pl.col("high")
                    .map_batches(
                        lambda s: _rolling_days_since_extreme(s.to_numpy(), "max"),
                        return_dtype=pl.Float64,
                    )
                    .over("asset_id")
                    .alias("_imax_tmp"),
                    pl.col("low")
                    .map_batches(
                        lambda s: _rolling_days_since_extreme(s.to_numpy(), "min"),
                        return_dtype=pl.Float64,
                    )
                    .over("asset_id")
                    .alias("_imin_tmp"),
                ])
                .with_columns(
                    (pl.col("_imax_tmp") - pl.col("_imin_tmp")).alias(self.name)
                )
            )[self.name]


class IMAX5(_ImaxMin):
    _mode = "imax"
    def __init__(self) -> None:
        super().__init__(5)


class IMAX10(_ImaxMin):
    _mode = "imax"
    def __init__(self) -> None:
        super().__init__(10)


class IMAX20(_ImaxMin):
    _mode = "imax"
    def __init__(self) -> None:
        super().__init__(20)


class IMAX30(_ImaxMin):
    _mode = "imax"
    def __init__(self) -> None:
        super().__init__(30)


class IMAX60(_ImaxMin):
    _mode = "imax"
    def __init__(self) -> None:
        super().__init__(60)


class IMIN5(_ImaxMin):
    _mode = "imin"
    def __init__(self) -> None:
        super().__init__(5)


class IMIN10(_ImaxMin):
    _mode = "imin"
    def __init__(self) -> None:
        super().__init__(10)


class IMIN20(_ImaxMin):
    _mode = "imin"
    def __init__(self) -> None:
        super().__init__(20)


class IMIN30(_ImaxMin):
    _mode = "imin"
    def __init__(self) -> None:
        super().__init__(30)


class IMIN60(_ImaxMin):
    _mode = "imin"
    def __init__(self) -> None:
        super().__init__(60)


class IMXD5(_ImaxMin):
    _mode = "imxd"
    def __init__(self) -> None:
        super().__init__(5)


class IMXD10(_ImaxMin):
    _mode = "imxd"
    def __init__(self) -> None:
        super().__init__(10)


class IMXD20(_ImaxMin):
    _mode = "imxd"
    def __init__(self) -> None:
        super().__init__(20)


class IMXD30(_ImaxMin):
    _mode = "imxd"
    def __init__(self) -> None:
        super().__init__(30)


class IMXD60(_ImaxMin):
    _mode = "imxd"
    def __init__(self) -> None:
        super().__init__(60)


# ── 合并所有 Alpha158 因子 ───────────────────────────────────────────────────
# 9 KBAR + 16 Rolling + 6 MAX/MIN扩展 + 3 ROC/MA/STD-60
# + 4 VMA + 4 VSTD + 4 VROC + 4 RSV + 15 REG(BETA/RSQR/RESI)
# + 10 QTLU/QTLD + 5 RANK + 15 IMAX/IMIN/IMXD = 95

_EXTENDED: list[Factor] = [
    MAX10(), MAX30(), MAX60(),
    MIN10(), MIN30(), MIN60(),
    ROC60(), MA60(), STD60(),
    VMA5(), VMA10(), VMA20(), VMA30(),
    VSTD5(), VSTD10(), VSTD20(), VSTD30(),
    VROC5(), VROC10(), VROC20(), VROC30(),
    RSV5(), RSV10(), RSV20(), RSV30(),
    BETA5(), BETA10(), BETA20(), BETA30(), BETA60(),
    RSQR5(), RSQR10(), RSQR20(), RSQR30(), RSQR60(),
    RESI5(), RESI10(), RESI20(), RESI30(), RESI60(),
    QTLU5(), QTLU10(), QTLU20(), QTLU30(), QTLU60(),
    QTLD5(), QTLD10(), QTLD20(), QTLD30(), QTLD60(),
    RANK5(), RANK10(), RANK20(), RANK30(), RANK60(),
    IMAX5(), IMAX10(), IMAX20(), IMAX30(), IMAX60(),
    IMIN5(), IMIN10(), IMIN20(), IMIN30(), IMIN60(),
    IMXD5(), IMXD10(), IMXD20(), IMXD30(), IMXD60(),
]

ALPHA158_FACTORS: list[Factor] = (
    list(KBAR_FACTORS)
    + list(ALPHA158_ROLLING_FACTORS)
    + _EXTENDED
)
