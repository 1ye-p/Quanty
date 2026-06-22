"""Volatility indicators — Bollinger Bands, ATR, Keltner Channels, StdDev, Variance."""

from __future__ import annotations

import polars as pl

from cquant.indicator.registry import register
from cquant.indicator.utils import true_range, wilder_smooth

CATEGORY = "volatility"


# ---------------------------------------------------------------------------
# Bollinger Bands
# ---------------------------------------------------------------------------

def _bollinger_upper(
    df: pl.DataFrame,
    *,
    period: int = 20,
    std_dev: float = 2.0,
    column: str = "close",
) -> pl.Series:
    """Bollinger Band Upper = SMA + std_dev * StdDev.

    Args:
        df: DataFrame.
        period: Lookback window.
        std_dev: Number of standard deviations.
        column: Source column.

    Returns:
        Series of upper band values.
    """
    sma = df[column].rolling_mean(window_size=period)
    std = df[column].rolling_std(window_size=period)
    return (sma + std_dev * std).alias("bb_upper")


def _bollinger_lower(
    df: pl.DataFrame,
    *,
    period: int = 20,
    std_dev: float = 2.0,
    column: str = "close",
) -> pl.Series:
    """Bollinger Band Lower = SMA - std_dev * StdDev."""
    sma = df[column].rolling_mean(window_size=period)
    std = df[column].rolling_std(window_size=period)
    return (sma - std_dev * std).alias("bb_lower")


def _bollinger_mid(
    df: pl.DataFrame,
    *,
    period: int = 20,
    std_dev: float = 2.0,
    column: str = "close",
) -> pl.Series:
    """Bollinger Band Middle = SMA."""
    return df[column].rolling_mean(window_size=period).alias("bb_mid")


def _bollinger_width(
    df: pl.DataFrame,
    *,
    period: int = 20,
    std_dev: float = 2.0,
    column: str = "close",
) -> pl.Series:
    """Bollinger Band Width = (Upper - Lower) / Middle."""
    sma = df[column].rolling_mean(window_size=period)
    std = df[column].rolling_std(window_size=period)
    upper = sma + std_dev * std
    lower = sma - std_dev * std
    return ((upper - lower) / sma).alias("bb_width")


# ---------------------------------------------------------------------------
# ATR — Average True Range
# ---------------------------------------------------------------------------

def _atr(df: pl.DataFrame, *, period: int = 14) -> pl.Series:
    """Average True Range using Wilder's smoothing.

    Args:
        df: DataFrame with 'high', 'low', 'close'.
        period: Smoothing period.

    Returns:
        Series of ATR values.
    """
    tr = true_range(df)
    return wilder_smooth(tr, period).alias("atr")


# ---------------------------------------------------------------------------
# Keltner Channels
# ---------------------------------------------------------------------------

def _keltner_upper(
    df: pl.DataFrame,
    *,
    ema_period: int = 20,
    atr_period: int = 10,
    multiplier: float = 2.0,
) -> pl.Series:
    """Keltner Channel Upper = EMA + multiplier * ATR.

    Args:
        df: DataFrame with 'high', 'low', 'close'.
        ema_period: EMA lookback for midline.
        atr_period: ATR smoothing period.
        multiplier: ATR multiplier.

    Returns:
        Series of upper channel values.
    """
    ema = df["close"].ewm_mean(span=ema_period, min_periods=ema_period)
    tr = true_range(df)
    atr_val = wilder_smooth(tr, atr_period)
    return (ema + multiplier * atr_val).alias("keltner_upper")


def _keltner_lower(
    df: pl.DataFrame,
    *,
    ema_period: int = 20,
    atr_period: int = 10,
    multiplier: float = 2.0,
) -> pl.Series:
    """Keltner Channel Lower = EMA - multiplier * ATR."""
    ema = df["close"].ewm_mean(span=ema_period, min_periods=ema_period)
    tr = true_range(df)
    atr_val = wilder_smooth(tr, atr_period)
    return (ema - multiplier * atr_val).alias("keltner_lower")


# ---------------------------------------------------------------------------
# StdDev
# ---------------------------------------------------------------------------

def _stddev(df: pl.DataFrame, *, period: int = 20, column: str = "close") -> pl.Series:
    """Rolling standard deviation.

    Args:
        df: DataFrame.
        period: Lookback window.
        column: Source column.

    Returns:
        Series of standard deviation values.
    """
    return df[column].rolling_std(window_size=period).alias("stddev")


# ---------------------------------------------------------------------------
# Variance
# ---------------------------------------------------------------------------

def _variance(df: pl.DataFrame, *, period: int = 20, column: str = "close") -> pl.Series:
    """Rolling variance.

    Args:
        df: DataFrame.
        period: Lookback window.
        column: Source column.

    Returns:
        Series of variance values.
    """
    return df[column].rolling_var(window_size=period).alias("variance")


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

register(
    name="bb_upper",
    category=CATEGORY,
    description="Bollinger Band Upper.",
    params=[("period", int, 20), ("std_dev", float, 2.0), ("column", str, "close")],
    fn=_bollinger_upper,
)

register(
    name="bb_lower",
    category=CATEGORY,
    description="Bollinger Band Lower.",
    params=[("period", int, 20), ("std_dev", float, 2.0), ("column", str, "close")],
    fn=_bollinger_lower,
)

register(
    name="bb_mid",
    category=CATEGORY,
    description="Bollinger Band Middle (SMA).",
    params=[("period", int, 20), ("std_dev", float, 2.0), ("column", str, "close")],
    fn=_bollinger_mid,
)

register(
    name="bb_width",
    category=CATEGORY,
    description="Bollinger Band Width.",
    params=[("period", int, 20), ("std_dev", float, 2.0), ("column", str, "close")],
    fn=_bollinger_width,
)

register(
    name="atr",
    category=CATEGORY,
    description="Average True Range (Wilder's smoothing).",
    params=[("period", int, 14)],
    fn=_atr,
)

register(
    name="keltner_upper",
    category=CATEGORY,
    description="Keltner Channel Upper.",
    params=[
        ("ema_period", int, 20),
        ("atr_period", int, 10),
        ("multiplier", float, 2.0),
    ],
    fn=_keltner_upper,
)

register(
    name="keltner_lower",
    category=CATEGORY,
    description="Keltner Channel Lower.",
    params=[
        ("ema_period", int, 20),
        ("atr_period", int, 10),
        ("multiplier", float, 2.0),
    ],
    fn=_keltner_lower,
)

register(
    name="stddev",
    category=CATEGORY,
    description="Rolling standard deviation.",
    params=[("period", int, 20), ("column", str, "close")],
    fn=_stddev,
)

register(
    name="variance",
    category=CATEGORY,
    description="Rolling variance.",
    params=[("period", int, 20), ("column", str, "close")],
    fn=_variance,
)
