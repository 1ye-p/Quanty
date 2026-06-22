"""Utility functions shared across indicator implementations."""

from __future__ import annotations

import polars as pl


def true_range(df: pl.DataFrame) -> pl.Series:
    """Compute True Range (TR).

    TR = max(high - low, |high - prev_close|, |low - prev_close|).

    Args:
        df: DataFrame with 'high', 'low', 'close' columns.

    Returns:
        Series of true range values (first row is high - low).
    """
    high = df["high"]
    low = df["low"]
    prev_close = df["close"].shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    return pl.max_horizontal(tr1, tr2, tr3).alias("true_range")


def typical_price(df: pl.DataFrame) -> pl.Series:
    """Compute Typical Price = (high + low + close) / 3."""
    return ((df["high"] + df["low"] + df["close"]) / 3.0).alias("typical_price")


def median_price(df: pl.DataFrame) -> pl.Series:
    """Compute Median Price = (high + low) / 2."""
    return ((df["high"] + df["low"]) / 2.0).alias("median_price")


def money_flow(df: pl.DataFrame) -> pl.Series:
    """Compute Money Flow = Typical Price * Volume."""
    tp = (df["high"] + df["low"] + df["close"]) / 3.0
    return (tp * df["volume"]).alias("money_flow")


def wilder_smooth(series: pl.Series, period: int) -> pl.Series:
    """Apply Wilder's smoothing (exponential with alpha = 1/period).

    This is equivalent to EMA with alpha = 1/period, commonly used
    in ATR, ADX, and RSI calculations.

    Args:
        series: Input series.
        period: Smoothing period.

    Returns:
        Smoothed series.
    """
    alpha = 1.0 / period
    return series.ewm_mean(span=period, min_periods=period)
