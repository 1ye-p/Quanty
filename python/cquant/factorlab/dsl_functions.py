"""DSL function registry — maps function names to Polars expressions."""

from __future__ import annotations
import math
from typing import Callable
import polars as pl


def _lag(col: pl.Expr, n: int) -> pl.Expr:
    return col.shift(n)

def _ma(col: pl.Expr, n: int) -> pl.Expr:
    return col.rolling_mean(window_size=n)

def _sma(col: pl.Expr, n: int) -> pl.Expr:
    return col.rolling_mean(window_size=n)

def _ema(col: pl.Expr, n: int) -> pl.Expr:
    return col.ewm_mean(span=n)

def _std(col: pl.Expr, n: int) -> pl.Expr:
    return col.rolling_std(window_size=n)

def _rank(col: pl.Expr) -> pl.Expr:
    return col.rank() / col.count()

def _delta(col: pl.Expr, n: int) -> pl.Expr:
    return col - col.shift(n)

def _max(col: pl.Expr, n: int) -> pl.Expr:
    return col.rolling_max(window_size=n)

def _min(col: pl.Expr, n: int) -> pl.Expr:
    return col.rolling_min(window_size=n)

def _sum(col: pl.Expr, n: int) -> pl.Expr:
    return col.rolling_sum(window_size=n)

def _abs(col: pl.Expr) -> pl.Expr:
    return col.abs()

def _log(col: pl.Expr) -> pl.Expr:
    return col.log(base=math.e)

def _sign(col: pl.Expr) -> pl.Expr:
    return col.sign()

def _ts_rank(col: pl.Expr, n: int) -> pl.Expr:
    """Current value's percentile rank (0~1) within the last n values."""
    return col.rolling_rank(window_size=n) / n

def _corr(col1: pl.Expr, col2: pl.Expr, n: int) -> pl.Expr:
    return pl.rolling_corr(col1, col2, window_size=n)

def _cov(col1: pl.Expr, col2: pl.Expr, n: int) -> pl.Expr:
    return pl.rolling_cov(col1, col2, window_size=n)


FUNCTIONS: dict[str, tuple[Callable, int, int, str]] = {
    "lag":     (_lag,     2, 2, "滞后 n 期: lag(close, 5)"),
    "ma":      (_ma,      2, 2, "简单移动平均: ma(close, 20)"),
    "sma":     (_sma,     2, 2, "简单移动平均 (= ma): sma(close, 20)"),
    "ema":     (_ema,     2, 2, "指数移动平均: ema(close, 20)"),
    "std":     (_std,     2, 2, "滚动标准差: std(close, 20)"),
    "rank":    (_rank,    1, 1, "截面排名百分位 (1/n~1): rank(close)"),
    "delta":   (_delta,   2, 2, "差分: delta(close, 5)"),
    "max":     (_max,     2, 2, "滚动最大值: max(high, 20)"),
    "min":     (_min,     2, 2, "滚动最小值: min(low, 20)"),
    "sum":     (_sum,     2, 2, "滚动求和: sum(volume, 5)"),
    "abs":     (_abs,     1, 1, "绝对值: abs(close)"),
    "log":     (_log,     1, 1, "自然对数: log(close)"),
    "sign":    (_sign,    1, 1, "符号 (-1/0/1): sign(close)"),
    "ts_rank": (_ts_rank, 2, 2, "时序排名: ts_rank(close, 20)"),
    "corr":    (_corr,    3, 3, "滚动相关系数: corr(close, volume, 10)"),
    "cov":     (_cov,     3, 3, "滚动协方差: cov(close, volume, 10)"),
}

AVAILABLE_COLUMNS = {"close", "open", "high", "low", "volume", "amount", "turnover"}


def get_function_descriptions() -> list[dict]:
    """Return function metadata for frontend autocomplete."""
    return [
        {"name": name, "minArgs": min_a, "maxArgs": max_a, "description": desc}
        for name, (_, min_a, max_a, desc) in FUNCTIONS.items()
    ]
