"""Moving average indicators — SMA, EMA, WMA, DEMA, TEMA, KAMA."""

from __future__ import annotations

import polars as pl

from cquant.indicator.registry import register

CATEGORY = "moving_average"


def _sma(df: pl.DataFrame, *, period: int = 20, column: str = "close") -> pl.Series:
    """Simple Moving Average.

    Args:
        df: DataFrame.
        period: Lookback window.
        column: Column to compute SMA on.

    Returns:
        Series of SMA values.
    """
    return df[column].rolling_mean(window_size=period).alias("sma")


def _ema(df: pl.DataFrame, *, period: int = 20, column: str = "close") -> pl.Series:
    """Exponential Moving Average (span-based).

    Args:
        df: DataFrame.
        period: EMA span.
        column: Column to compute EMA on.

    Returns:
        Series of EMA values.
    """
    return df[column].ewm_mean(span=period, min_periods=period).alias("ema")


def _wma(df: pl.DataFrame, *, period: int = 20, column: str = "close") -> pl.Series:
    """Weighted Moving Average — linear weights (1, 2, ..., period).

    Args:
        df: DataFrame.
        period: Lookback window.
        column: Column to compute WMA on.

    Returns:
        Series of WMA values.
    """
    weights = list(range(1, period + 1))
    total_weight = period * (period + 1) / 2.0

    # Use rolling_map with a custom function for WMA
    return (
        df[column]
        .rolling_map(
            function=lambda s: sum(v * w for v, w in zip(s, weights)) / total_weight,
            window_size=period,
            min_periods=period,
        )
        .alias("wma")
    )


def _dema(df: pl.DataFrame, *, period: int = 20, column: str = "close") -> pl.Series:
    """Double Exponential Moving Average.

    DEMA = 2 * EMA(series, period) - EMA(EMA(series, period), period).

    Args:
        df: DataFrame.
        period: EMA span.
        column: Column to compute DEMA on.

    Returns:
        Series of DEMA values.
    """
    s = df[column]
    ema1 = s.ewm_mean(span=period, min_periods=period)
    ema2 = ema1.ewm_mean(span=period, min_periods=period)
    return (2.0 * ema1 - ema2).alias("dema")


def _tema(df: pl.DataFrame, *, period: int = 20, column: str = "close") -> pl.Series:
    """Triple Exponential Moving Average.

    TEMA = 3*EMA - 3*EMA(EMA) + EMA(EMA(EMA)).

    Args:
        df: DataFrame.
        period: EMA span.
        column: Column to compute TEMA on.

    Returns:
        Series of TEMA values.
    """
    s = df[column]
    ema1 = s.ewm_mean(span=period, min_periods=period)
    ema2 = ema1.ewm_mean(span=period, min_periods=period)
    ema3 = ema2.ewm_mean(span=period, min_periods=period)
    return (3.0 * ema1 - 3.0 * ema2 + ema3).alias("tema")


def _kama(
    df: pl.DataFrame, *, period: int = 10, fast_period: int = 2, slow_period: int = 30, column: str = "close"
) -> pl.Series:
    """Kaufman Adaptive Moving Average.

    ER = |close - close.shift(period)| / sum(|close.diff|, period).
    SC = (ER * (2/(fast+1) - 2/(slow+1)) + 2/(slow+1))^2.
    KAMA = KAMA_prev + SC * (close - KAMA_prev).

    Args:
        df: DataFrame.
        period: Efficiency ratio lookback.
        fast_period: Fast smoothing constant period.
        slow_period: Slow smoothing constant period.
        column: Column to compute KAMA on.

    Returns:
        Series of KAMA values.
    """
    close = df[column]
    direction = (close - close.shift(period)).abs()
    volatility = close.diff().abs().rolling_sum(window_size=period)
    er = direction / volatility

    fast_sc = 2.0 / (fast_period + 1.0)
    slow_sc = 2.0 / (slow_period + 1.0)
    sc = (er * (fast_sc - slow_sc) + slow_sc) ** 2

    # Iterative KAMA — use scan-based approach
    close_arr = close.to_list()
    sc_arr = sc.to_list()
    n = len(close_arr)
    kama_values = [None] * n

    # Initialize first valid KAMA at index = period
    first_valid = period
    if first_valid < n and close_arr[first_valid] is not None:
        kama_values[first_valid] = close_arr[first_valid]
        for i in range(first_valid + 1, n):
            if close_arr[i] is None or sc_arr[i] is None or kama_values[i - 1] is None:
                kama_values[i] = None
            else:
                kama_values[i] = kama_values[i - 1] + sc_arr[i] * (close_arr[i] - kama_values[i - 1])

    return pl.Series("kama", kama_values)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

register(
    name="sma",
    category=CATEGORY,
    description="Simple Moving Average.",
    params=[("period", int, 20), ("column", str, "close")],
    fn=_sma,
)

register(
    name="ema",
    category=CATEGORY,
    description="Exponential Moving Average.",
    params=[("period", int, 20), ("column", str, "close")],
    fn=_ema,
)

register(
    name="wma",
    category=CATEGORY,
    description="Weighted Moving Average with linear weights.",
    params=[("period", int, 20), ("column", str, "close")],
    fn=_wma,
)

register(
    name="dema",
    category=CATEGORY,
    description="Double Exponential Moving Average.",
    params=[("period", int, 20), ("column", str, "close")],
    fn=_dema,
)

register(
    name="tema",
    category=CATEGORY,
    description="Triple Exponential Moving Average.",
    params=[("period", int, 20), ("column", str, "close")],
    fn=_tema,
)

register(
    name="kama",
    category=CATEGORY,
    description="Kaufman Adaptive Moving Average.",
    params=[
        ("period", int, 10),
        ("fast_period", int, 2),
        ("slow_period", int, 30),
        ("column", str, "close"),
    ],
    fn=_kama,
)
