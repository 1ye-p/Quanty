"""Basic OHLCV indicators — returns, log returns, VWAP."""

from __future__ import annotations

import math

import polars as pl

from cquant.indicator.registry import register

CATEGORY = "ohlcv"


def _returns(df: pl.DataFrame, *, period: int = 1) -> pl.Series:
    """Simple percentage returns: (close / close.shift(period)) - 1.

    Args:
        df: DataFrame with 'close' column.
        period: Number of periods to look back.

    Returns:
        Series of percentage returns.
    """
    return (
        (df["close"] / df["close"].shift(period) - 1.0)
        .alias("returns")
    )


def _log_returns(df: pl.DataFrame, *, period: int = 1) -> pl.Series:
    """Logarithmic returns: ln(close / close.shift(period)).

    Args:
        df: DataFrame with 'close' column.
        period: Number of periods to look back.

    Returns:
        Series of log returns.
    """
    return (
        (df["close"] / df["close"].shift(period))
        .log()
        .alias("log_returns")
    )


def _vwap(df: pl.DataFrame) -> pl.Series:
    """Volume Weighted Average Price (cumulative within the dataset).

    VWAP = cumulative(sum(amount) / sum(volume)).

    Args:
        df: DataFrame with 'amount' and 'volume' columns.

    Returns:
        Series of VWAP values.
    """
    cum_amount = df["amount"].cum_sum()
    cum_volume = df["volume"].cum_sum()
    return (cum_amount / cum_volume).alias("vwap")


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

register(
    name="returns",
    category=CATEGORY,
    description="Simple percentage returns over N periods.",
    params=[("period", int, 1)],
    fn=_returns,
)

register(
    name="log_returns",
    category=CATEGORY,
    description="Logarithmic returns over N periods.",
    params=[("period", int, 1)],
    fn=_log_returns,
)

register(
    name="vwap",
    category=CATEGORY,
    description="Volume Weighted Average Price (cumulative).",
    params=[],
    fn=_vwap,
)
