"""Oscillator indicators — RSI, KDJ, Stochastic, Williams %R, ROC, Momentum, Ultimate Oscillator."""

from __future__ import annotations

import polars as pl

from cquant.indicator.registry import register
from cquant.indicator.utils import wilder_smooth

CATEGORY = "oscillator"


# ---------------------------------------------------------------------------
# RSI — Relative Strength Index
# ---------------------------------------------------------------------------

def _rsi(df: pl.DataFrame, *, period: int = 14, column: str = "close") -> pl.Series:
    """Relative Strength Index.

    RSI = 100 - 100 / (1 + avg_gain / avg_loss).
    Uses Wilder's smoothing for the gain/loss averages.

    Args:
        df: DataFrame.
        period: Lookback period.
        column: Source column.

    Returns:
        Series of RSI values (0-100).
    """
    delta = df[column].diff()
    gain = delta.clip(lower_bound=0.0)
    loss = (-delta).clip(lower_bound=0.0)

    avg_gain = wilder_smooth(gain, period)
    avg_loss = wilder_smooth(loss, period)

    rsi = 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)
    return rsi.alias("rsi")


# ---------------------------------------------------------------------------
# KDJ
# ---------------------------------------------------------------------------

def _kdj(
    df: pl.DataFrame,
    *,
    k_period: int = 9,
    d_period: int = 3,
    j_period: int = 3,
) -> pl.Series:
    """KDJ J-line.

    RSV = (close - lowest_low) / (highest_high - lowest_low) * 100.
    K = SMA(RSV, d_period)  [using EWM as approximation].
    D = SMA(K, d_period).
    J = 3*K - 2*D.

    Returns the J line.

    Args:
        df: DataFrame with 'high', 'low', 'close'.
        k_period: RSV lookback period.
        d_period: K smoothing period.
        j_period: D smoothing period.

    Returns:
        Series of J values.
    """
    highest = df["high"].rolling_max(window_size=k_period)
    lowest = df["low"].rolling_min(window_size=k_period)
    rsv = (df["close"] - lowest) / (highest - lowest) * 100.0

    k = rsv.ewm_mean(span=d_period, min_periods=d_period - 1)
    d = k.ewm_mean(span=j_period, min_periods=j_period - 1)
    j = 3.0 * k - 2.0 * d
    return j.alias("kdj_j")


def _kdj_k(df: pl.DataFrame, *, k_period: int = 9, d_period: int = 3) -> pl.Series:
    """KDJ K-line."""
    highest = df["high"].rolling_max(window_size=k_period)
    lowest = df["low"].rolling_min(window_size=k_period)
    rsv = (df["close"] - lowest) / (highest - lowest) * 100.0
    return rsv.ewm_mean(span=d_period, min_periods=d_period - 1).alias("kdj_k")


def _kdj_d(df: pl.DataFrame, *, k_period: int = 9, d_period: int = 3, j_period: int = 3) -> pl.Series:
    """KDJ D-line."""
    highest = df["high"].rolling_max(window_size=k_period)
    lowest = df["low"].rolling_min(window_size=k_period)
    rsv = (df["close"] - lowest) / (highest - lowest) * 100.0
    k = rsv.ewm_mean(span=d_period, min_periods=d_period - 1)
    return k.ewm_mean(span=j_period, min_periods=j_period - 1).alias("kdj_d")


# ---------------------------------------------------------------------------
# Stochastic Oscillator
# ---------------------------------------------------------------------------

def _stochastic(
    df: pl.DataFrame, *, k_period: int = 14, d_period: int = 3
) -> pl.Series:
    """Stochastic %K.

    %K = (close - lowest_low_N) / (highest_high_N - lowest_low_N) * 100.

    Args:
        df: DataFrame with 'high', 'low', 'close'.
        k_period: Lookback for high/low.
        d_period: Smoothing period for %D (unused here).

    Returns:
        Series of %K values.
    """
    highest = df["high"].rolling_max(window_size=k_period)
    lowest = df["low"].rolling_min(window_size=k_period)
    return ((df["close"] - lowest) / (highest - lowest) * 100.0).alias("stoch_k")


def _stochastic_d(
    df: pl.DataFrame, *, k_period: int = 14, d_period: int = 3
) -> pl.Series:
    """Stochastic %D = SMA(%K, d_period)."""
    highest = df["high"].rolling_max(window_size=k_period)
    lowest = df["low"].rolling_min(window_size=k_period)
    k = (df["close"] - lowest) / (highest - lowest) * 100.0
    return k.rolling_mean(window_size=d_period).alias("stoch_d")


# ---------------------------------------------------------------------------
# Williams %R
# ---------------------------------------------------------------------------

def _williams_r(df: pl.DataFrame, *, period: int = 14) -> pl.Series:
    """Williams %R.

    %R = (highest_high - close) / (highest_high - lowest_low) * -100.

    Args:
        df: DataFrame with 'high', 'low', 'close'.
        period: Lookback period.

    Returns:
        Series of Williams %R values (-100 to 0).
    """
    highest = df["high"].rolling_max(window_size=period)
    lowest = df["low"].rolling_min(window_size=period)
    return ((highest - df["close"]) / (highest - lowest) * -100.0).alias("williams_r")


# ---------------------------------------------------------------------------
# ROC — Rate of Change
# ---------------------------------------------------------------------------

def _roc(df: pl.DataFrame, *, period: int = 12, column: str = "close") -> pl.Series:
    """Rate of Change.

    ROC = (close - close.shift(period)) / close.shift(period) * 100.

    Args:
        df: DataFrame.
        period: Lookback.
        column: Source column.

    Returns:
        Series of ROC values.
    """
    prev = df[column].shift(period)
    return ((df[column] - prev) / prev * 100.0).alias("roc")


# ---------------------------------------------------------------------------
# Momentum
# ---------------------------------------------------------------------------

def _momentum(df: pl.DataFrame, *, period: int = 10, column: str = "close") -> pl.Series:
    """Momentum.

    MOM = close - close.shift(period).

    Args:
        df: DataFrame.
        period: Lookback.
        column: Source column.

    Returns:
        Series of momentum values.
    """
    return (df[column] - df[column].shift(period)).alias("momentum")


# ---------------------------------------------------------------------------
# Ultimate Oscillator
# ---------------------------------------------------------------------------

def _ultimate_oscillator(
    df: pl.DataFrame,
    *,
    period1: int = 7,
    period2: int = 14,
    period3: int = 28,
    weight1: float = 4.0,
    weight2: float = 2.0,
    weight3: float = 1.0,
) -> pl.Series:
    """Ultimate Oscillator.

    BP = close - min(low, prev_close).
    TR = max(high, prev_close) - min(low, prev_close).
    UO = 100 * (w1*avg(BP,TR,p1) + w2*avg(BP,TR,p2) + w3*avg(BP,TR,p3)) / (w1+w2+w3).

    Args:
        df: DataFrame with 'high', 'low', 'close'.
        period1/2/3: Lookback periods.
        weight1/2/3: Weights for each period.

    Returns:
        Series of UO values (0-100).
    """
    prev_close = df["close"].shift(1)
    bp = df["close"] - pl.min_horizontal(df["low"], prev_close)
    tr = pl.max_horizontal(df["high"], prev_close) - pl.min_horizontal(df["low"], prev_close)

    avg1 = bp.rolling_sum(window_size=period1) / tr.rolling_sum(window_size=period1)
    avg2 = bp.rolling_sum(window_size=period2) / tr.rolling_sum(window_size=period2)
    avg3 = bp.rolling_sum(window_size=period3) / tr.rolling_sum(window_size=period3)

    total_weight = weight1 + weight2 + weight3
    uo = 100.0 * (weight1 * avg1 + weight2 * avg2 + weight3 * avg3) / total_weight
    return uo.alias("ultimate_oscillator")


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

register(
    name="rsi",
    category=CATEGORY,
    description="Relative Strength Index.",
    params=[("period", int, 14), ("column", str, "close")],
    fn=_rsi,
)

register(
    name="kdj_j",
    category=CATEGORY,
    description="KDJ J-line.",
    params=[("k_period", int, 9), ("d_period", int, 3), ("j_period", int, 3)],
    fn=_kdj,
)

register(
    name="kdj_k",
    category=CATEGORY,
    description="KDJ K-line.",
    params=[("k_period", int, 9), ("d_period", int, 3)],
    fn=_kdj_k,
)

register(
    name="kdj_d",
    category=CATEGORY,
    description="KDJ D-line.",
    params=[("k_period", int, 9), ("d_period", int, 3), ("j_period", int, 3)],
    fn=_kdj_d,
)

register(
    name="stoch_k",
    category=CATEGORY,
    description="Stochastic Oscillator %K.",
    params=[("k_period", int, 14), ("d_period", int, 3)],
    fn=_stochastic,
)

register(
    name="stoch_d",
    category=CATEGORY,
    description="Stochastic Oscillator %D.",
    params=[("k_period", int, 14), ("d_period", int, 3)],
    fn=_stochastic_d,
)

register(
    name="williams_r",
    category=CATEGORY,
    description="Williams %R.",
    params=[("period", int, 14)],
    fn=_williams_r,
)

register(
    name="roc",
    category=CATEGORY,
    description="Rate of Change.",
    params=[("period", int, 12), ("column", str, "close")],
    fn=_roc,
)

register(
    name="momentum",
    category=CATEGORY,
    description="Momentum (close - prev_close).",
    params=[("period", int, 10), ("column", str, "close")],
    fn=_momentum,
)

register(
    name="ultimate_oscillator",
    category=CATEGORY,
    description="Ultimate Oscillator.",
    params=[
        ("period1", int, 7),
        ("period2", int, 14),
        ("period3", int, 28),
        ("weight1", float, 4.0),
        ("weight2", float, 2.0),
        ("weight3", float, 1.0),
    ],
    fn=_ultimate_oscillator,
)
