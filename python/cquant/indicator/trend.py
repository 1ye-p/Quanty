"""Trend indicators — MACD, ADX, Aroon, CCI, Parabolic SAR, TRIX."""

from __future__ import annotations

import polars as pl

from cquant.indicator.registry import register
from cquant.indicator.utils import true_range, typical_price, wilder_smooth

CATEGORY = "trend"


# ---------------------------------------------------------------------------
# MACD
# ---------------------------------------------------------------------------

def _macd(
    df: pl.DataFrame,
    *,
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
    column: str = "close",
) -> pl.Series:
    """MACD Line = EMA(fast) - EMA(slow).

    Returns the MACD line only. For signal and histogram, use macd_signal / macd_hist.

    Args:
        df: DataFrame.
        fast_period: Fast EMA period.
        slow_period: Slow EMA period.
        signal_period: (unused here, kept for consistency).
        column: Source column.

    Returns:
        Series of MACD line values.
    """
    close = df[column]
    ema_fast = close.ewm_mean(span=fast_period, min_periods=fast_period)
    ema_slow = close.ewm_mean(span=slow_period, min_periods=slow_period)
    return (ema_fast - ema_slow).alias("macd")


def _macd_signal(
    df: pl.DataFrame,
    *,
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
    column: str = "close",
) -> pl.Series:
    """MACD Signal Line = EMA(MACD, signal_period).

    Args:
        df: DataFrame.
        fast_period: Fast EMA period.
        slow_period: Slow EMA period.
        signal_period: Signal line EMA period.
        column: Source column.

    Returns:
        Series of MACD signal values.
    """
    close = df[column]
    ema_fast = close.ewm_mean(span=fast_period, min_periods=fast_period)
    ema_slow = close.ewm_mean(span=slow_period, min_periods=slow_period)
    macd_line = ema_fast - ema_slow
    return macd_line.ewm_mean(span=signal_period, min_periods=signal_period).alias("macd_signal")


def _macd_hist(
    df: pl.DataFrame,
    *,
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
    column: str = "close",
) -> pl.Series:
    """MACD Histogram = MACD - Signal.

    Args:
        df: DataFrame.

    Returns:
        Series of MACD histogram values.
    """
    close = df[column]
    ema_fast = close.ewm_mean(span=fast_period, min_periods=fast_period)
    ema_slow = close.ewm_mean(span=slow_period, min_periods=slow_period)
    macd_line = ema_fast - ema_slow
    signal = macd_line.ewm_mean(span=signal_period, min_periods=signal_period)
    return (macd_line - signal).alias("macd_hist")


# ---------------------------------------------------------------------------
# ADX — Average Directional Index
# ---------------------------------------------------------------------------

def _adx(df: pl.DataFrame, *, period: int = 14) -> pl.Series:
    """Average Directional Index.

    ADX = WilderSmooth(100 * |+DI - -DI| / (+DI + -DI), period).

    Args:
        df: DataFrame with 'high', 'low', 'close'.
        period: Smoothing / lookback period.

    Returns:
        Series of ADX values.
    """
    high = df["high"]
    low = df["low"]
    close = df["close"]

    up_move = high - high.shift(1)
    down_move = low.shift(1) - low

    plus_dm = pl.when((up_move > down_move) & (up_move > 0)).then(up_move).otherwise(0.0)
    minus_dm = pl.when((down_move > up_move) & (down_move > 0)).then(down_move).otherwise(0.0)

    tr = true_range(df)

    atr = wilder_smooth(tr, period)
    plus_di = 100.0 * wilder_smooth(plus_dm, period) / atr
    minus_di = 100.0 * wilder_smooth(minus_dm, period) / atr

    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    adx = wilder_smooth(dx, period)
    return adx.alias("adx")


# ---------------------------------------------------------------------------
# Aroon
# ---------------------------------------------------------------------------

def _aroon_up(df: pl.DataFrame, *, period: int = 25) -> pl.Series:
    """Aroon Up = ((period - periods since highest high) / period) * 100.

    Args:
        df: DataFrame with 'high'.
        period: Lookback period.

    Returns:
        Series of Aroon Up values.
    """
    high = df["high"]
    return (
        high.rolling_map(
            function=lambda s: (period - list(reversed(list(s))).index(max(s))) / period * 100,
            window_size=period + 1,
            min_periods=period + 1,
        )
        .alias("aroon_up")
    )


def _aroon_down(df: pl.DataFrame, *, period: int = 25) -> pl.Series:
    """Aroon Down = ((period - periods since lowest low) / period) * 100.

    Args:
        df: DataFrame with 'low'.
        period: Lookback period.

    Returns:
        Series of Aroon Down values.
    """
    low = df["low"]
    return (
        low.rolling_map(
            function=lambda s: (period - list(reversed(list(s))).index(min(s))) / period * 100,
            window_size=period + 1,
            min_periods=period + 1,
        )
        .alias("aroon_down")
    )


# ---------------------------------------------------------------------------
# CCI — Commodity Channel Index
# ---------------------------------------------------------------------------

def _cci(df: pl.DataFrame, *, period: int = 20) -> pl.Series:
    """Commodity Channel Index.

    CCI = (TP - SMA(TP)) / (0.015 * MeanDeviation(TP)).

    Args:
        df: DataFrame with 'high', 'low', 'close'.
        period: Lookback period.

    Returns:
        Series of CCI values.
    """
    tp = typical_price(df)
    sma_tp = tp.rolling_mean(window_size=period)

    # Mean absolute deviation
    mad = tp.rolling_map(
        function=lambda s: sum(abs(x - sum(s) / len(s)) for x in s) / len(s),
        window_size=period,
        min_periods=period,
    )
    return ((tp - sma_tp) / (0.015 * mad)).alias("cci")


# ---------------------------------------------------------------------------
# Parabolic SAR
# ---------------------------------------------------------------------------

def _parabolic_sar(
    df: pl.DataFrame, *, af_start: float = 0.02, af_step: float = 0.02, af_max: float = 0.20
) -> pl.Series:
    """Parabolic Stop and Reverse (SAR).

    Args:
        df: DataFrame with 'high', 'low'.
        af_start: Initial acceleration factor.
        af_step: AF increment per new extreme.
        af_max: Maximum AF value.

    Returns:
        Series of SAR values.
    """
    high = df["high"].to_list()
    low = df["low"].to_list()
    n = len(high)

    sar_values = [None] * n
    if n < 2:
        return pl.Series("parabolic_sar", sar_values)

    # Initialize: assume uptrend
    is_long = True
    af = af_start
    ep = high[0]  # extreme point
    sar = low[0]

    sar_values[0] = sar

    for i in range(1, n):
        prev_sar = sar

        # Calculate new SAR
        sar = prev_sar + af * (ep - prev_sar)

        if is_long:
            # Ensure SAR is not above the prior two lows
            sar = min(sar, low[i - 1])
            if i >= 2:
                sar = min(sar, low[i - 2])

            if low[i] < sar:
                # Switch to short
                is_long = False
                sar = ep
                ep = low[i]
                af = af_start
            else:
                if high[i] > ep:
                    ep = high[i]
                    af = min(af + af_step, af_max)
        else:
            # Ensure SAR is not below the prior two highs
            sar = max(sar, high[i - 1])
            if i >= 2:
                sar = max(sar, high[i - 2])

            if high[i] > sar:
                # Switch to long
                is_long = True
                sar = ep
                ep = high[i]
                af = af_start
            else:
                if low[i] < ep:
                    ep = low[i]
                    af = min(af + af_step, af_max)

        sar_values[i] = sar

    return pl.Series("parabolic_sar", sar_values)


# ---------------------------------------------------------------------------
# TRIX — Triple Exponential Average Rate of Change
# ---------------------------------------------------------------------------

def _trix(df: pl.DataFrame, *, period: int = 15, column: str = "close") -> pl.Series:
    """TRIX — 1-period percentage change of triple EMA.

    TRIX = (EMA3 - EMA3.shift(1)) / EMA3.shift(1) * 100.

    Args:
        df: DataFrame.
        period: EMA period.
        column: Source column.

    Returns:
        Series of TRIX values.
    """
    s = df[column]
    ema1 = s.ewm_mean(span=period, min_periods=period)
    ema2 = ema1.ewm_mean(span=period, min_periods=period)
    ema3 = ema2.ewm_mean(span=period, min_periods=period)
    return ((ema3 - ema3.shift(1)) / ema3.shift(1) * 100).alias("trix")


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

register(
    name="macd",
    category=CATEGORY,
    description="MACD Line (fast EMA - slow EMA).",
    params=[
        ("fast_period", int, 12),
        ("slow_period", int, 26),
        ("signal_period", int, 9),
        ("column", str, "close"),
    ],
    fn=_macd,
)

register(
    name="macd_signal",
    category=CATEGORY,
    description="MACD Signal Line (EMA of MACD).",
    params=[
        ("fast_period", int, 12),
        ("slow_period", int, 26),
        ("signal_period", int, 9),
        ("column", str, "close"),
    ],
    fn=_macd_signal,
)

register(
    name="macd_hist",
    category=CATEGORY,
    description="MACD Histogram (MACD - Signal).",
    params=[
        ("fast_period", int, 12),
        ("slow_period", int, 26),
        ("signal_period", int, 9),
        ("column", str, "close"),
    ],
    fn=_macd_hist,
)

register(
    name="adx",
    category=CATEGORY,
    description="Average Directional Index.",
    params=[("period", int, 14)],
    fn=_adx,
)

register(
    name="aroon_up",
    category=CATEGORY,
    description="Aroon Up indicator.",
    params=[("period", int, 25)],
    fn=_aroon_up,
)

register(
    name="aroon_down",
    category=CATEGORY,
    description="Aroon Down indicator.",
    params=[("period", int, 25)],
    fn=_aroon_down,
)

register(
    name="cci",
    category=CATEGORY,
    description="Commodity Channel Index.",
    params=[("period", int, 20)],
    fn=_cci,
)

register(
    name="parabolic_sar",
    category=CATEGORY,
    description="Parabolic Stop and Reverse.",
    params=[
        ("af_start", float, 0.02),
        ("af_step", float, 0.02),
        ("af_max", float, 0.20),
    ],
    fn=_parabolic_sar,
)

register(
    name="trix",
    category=CATEGORY,
    description="TRIX — triple EMA rate of change.",
    params=[("period", int, 15), ("column", str, "close")],
    fn=_trix,
)
