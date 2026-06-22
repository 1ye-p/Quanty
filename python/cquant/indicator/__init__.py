"""cquant.indicator — Technical indicator calculation library (Polars-based).

Provides 30+ technical indicators organized by category:
- ohlcv: returns, log_returns, vwap
- moving_average: sma, ema, wma, dema, tema, kama
- trend: macd, adx, aroon, cci, parabolic_sar, trix
- oscillator: rsi, kdj, stochastic, williams_r, roc, momentum, ultimate_oscillator
- volatility: bollinger_bands, atr, keltner_channels, stddev, variance
- volume: obv, vpt, mfi, ad_line, cmf, volume_sma, volume_ratio

Usage::

    from cquant.indicator import list_indicators, compute
    from cquant.indicator.registry import get_indicator

    # List all indicators
    indicators = list_indicators()

    # Compute a single indicator
    spec = get_indicator("rsi")
    rsi_series = spec.fn(df, period=14)

    # Compute multiple indicators at once
    result = compute(df, [
        {"name": "sma", "params": {"period": 20}},
        {"name": "rsi", "params": {"period": 14}},
    ])
"""

# Import submodules to trigger indicator registration
from cquant.indicator import (  # noqa: F401
    ohlcv,
    moving_average,
    trend,
    oscillator,
    volatility,
    volume,
)

from cquant.indicator.base import IndicatorSpec, validate_ohlcv  # noqa: F401
from cquant.indicator.registry import (  # noqa: F401
    compute,
    get_indicator,
    list_indicators,
)

__all__ = [
    "IndicatorSpec",
    "validate_ohlcv",
    "compute",
    "get_indicator",
    "list_indicators",
]
