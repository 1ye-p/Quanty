"""Volume indicators — OBV, VPT, MFI, AD Line, CMF, Volume SMA, Volume Ratio."""

from __future__ import annotations

import polars as pl

from cquant.indicator.registry import register
from cquant.indicator.utils import money_flow, typical_price

CATEGORY = "volume"


# ---------------------------------------------------------------------------
# OBV — On Balance Volume
# ---------------------------------------------------------------------------

def _obv(df: pl.DataFrame) -> pl.Series:
    """On Balance Volume.

    OBV = OBV_prev + volume (if close > prev_close)
          OBV_prev - volume (if close < prev_close)
          OBV_prev (if close == prev_close).

    Args:
        df: DataFrame with 'close', 'volume'.

    Returns:
        Series of OBV values.
    """
    direction = pl.when(df["close"] > df["close"].shift(1)).then(1).when(
        df["close"] < df["close"].shift(1)
    ).then(-1).otherwise(0)
    signed_volume = direction * df["volume"]
    return signed_volume.cum_sum().alias("obv")


# ---------------------------------------------------------------------------
# VPT — Volume Price Trend
# ---------------------------------------------------------------------------

def _vpt(df: pl.DataFrame) -> pl.Series:
    """Volume Price Trend.

    VPT = VPT_prev + volume * (close - prev_close) / prev_close.

    Args:
        df: DataFrame with 'close', 'volume'.

    Returns:
        Series of VPT values.
    """
    pct_change = (df["close"] - df["close"].shift(1)) / df["close"].shift(1)
    return (df["volume"] * pct_change).cum_sum().alias("vpt")


# ---------------------------------------------------------------------------
# MFI — Money Flow Index
# ---------------------------------------------------------------------------

def _mfi(df: pl.DataFrame, *, period: int = 14) -> pl.Series:
    """Money Flow Index.

    Typical Price = (H + L + C) / 3.
    Raw MF = TP * Volume.
    Positive MF = sum of raw MF where TP > prev_TP over period.
    Negative MF = sum of raw MF where TP < prev_TP over period.
    MFR = Positive / Negative.
    MFI = 100 - 100 / (1 + MFR).

    Args:
        df: DataFrame with 'high', 'low', 'close', 'volume'.
        period: Lookback period.

    Returns:
        Series of MFI values (0-100).
    """
    tp = typical_price(df)
    raw_mf = tp * df["volume"]
    tp_diff = tp - tp.shift(1)

    pos_mf = pl.when(tp_diff > 0).then(raw_mf).otherwise(0.0)
    neg_mf = pl.when(tp_diff < 0).then(raw_mf).otherwise(0.0)

    pos_sum = pos_mf.rolling_sum(window_size=period)
    neg_sum = neg_mf.rolling_sum(window_size=period)

    mfr = pos_sum / neg_sum
    return (100.0 - 100.0 / (1.0 + mfr)).alias("mfi")


# ---------------------------------------------------------------------------
# AD Line — Accumulation/Distribution Line
# ---------------------------------------------------------------------------

def _ad_line(df: pl.DataFrame) -> pl.Series:
    """Accumulation/Distribution Line.

    CLV = ((close - low) - (high - close)) / (high - low).
    AD = cumulative(CLV * volume).

    Args:
        df: DataFrame with 'high', 'low', 'close', 'volume'.

    Returns:
        Series of AD Line values.
    """
    high = df["high"]
    low = df["low"]
    close = df["close"]
    hl_range = high - low

    clv = pl.when(hl_range != 0).then(
        ((close - low) - (high - close)) / hl_range
    ).otherwise(0.0)

    return (clv * df["volume"]).cum_sum().alias("ad_line")


# ---------------------------------------------------------------------------
# CMF — Chaikin Money Flow
# ---------------------------------------------------------------------------

def _cmf(df: pl.DataFrame, *, period: int = 20) -> pl.Series:
    """Chaikin Money Flow.

    CLV = ((close - low) - (high - close)) / (high - low).
    CMF = sum(CLV * volume, period) / sum(volume, period).

    Args:
        df: DataFrame with 'high', 'low', 'close', 'volume'.
        period: Lookback period.

    Returns:
        Series of CMF values (-1 to 1).
    """
    high = df["high"]
    low = df["low"]
    close = df["close"]
    hl_range = high - low

    clv = pl.when(hl_range != 0).then(
        ((close - low) - (high - close)) / hl_range
    ).otherwise(0.0)

    mf_volume = clv * df["volume"]
    return (
        mf_volume.rolling_sum(window_size=period)
        / df["volume"].rolling_sum(window_size=period)
    ).alias("cmf")


# ---------------------------------------------------------------------------
# Volume SMA
# ---------------------------------------------------------------------------

def _volume_sma(df: pl.DataFrame, *, period: int = 20) -> pl.Series:
    """Simple Moving Average of volume.

    Args:
        df: DataFrame with 'volume'.
        period: Lookback window.

    Returns:
        Series of volume SMA values.
    """
    return df["volume"].rolling_mean(window_size=period).alias("volume_sma")


# ---------------------------------------------------------------------------
# Volume Ratio
# ---------------------------------------------------------------------------

def _volume_ratio(df: pl.DataFrame, *, period: int = 20) -> pl.Series:
    """Volume Ratio = volume / SMA(volume, period).

    Values > 1 indicate above-average volume.

    Args:
        df: DataFrame with 'volume'.
        period: Lookback window for SMA.

    Returns:
        Series of volume ratio values.
    """
    sma = df["volume"].rolling_mean(window_size=period)
    return (df["volume"] / sma).alias("volume_ratio")


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

register(
    name="obv",
    category=CATEGORY,
    description="On Balance Volume.",
    params=[],
    fn=_obv,
)

register(
    name="vpt",
    category=CATEGORY,
    description="Volume Price Trend.",
    params=[],
    fn=_vpt,
)

register(
    name="mfi",
    category=CATEGORY,
    description="Money Flow Index.",
    params=[("period", int, 14)],
    fn=_mfi,
)

register(
    name="ad_line",
    category=CATEGORY,
    description="Accumulation/Distribution Line.",
    params=[],
    fn=_ad_line,
)

register(
    name="cmf",
    category=CATEGORY,
    description="Chaikin Money Flow.",
    params=[("period", int, 20)],
    fn=_cmf,
)

register(
    name="volume_sma",
    category=CATEGORY,
    description="Simple Moving Average of volume.",
    params=[("period", int, 20)],
    fn=_volume_sma,
)

register(
    name="volume_ratio",
    category=CATEGORY,
    description="Volume / SMA(volume) ratio.",
    params=[("period", int, 20)],
    fn=_volume_ratio,
)
