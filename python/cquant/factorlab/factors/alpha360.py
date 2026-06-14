"""Alpha360 factor set: 60-day normalized OHLCV, 360 features total.

Feature naming: {field}_{day}_norm
- close_0_norm ~ close_59_norm: 60-day close price change rate
- open_0_norm ~ open_59_norm: 60-day open price deviation from close
- high_0_norm ~ high_59_norm: 60-day high price deviation from close
- low_0_norm ~ low_59_norm: 60-day low price deviation from close
- vwap_0_norm ~ vwap_59_norm: 60-day VWAP deviation from close
- volume_0_norm ~ volume_59_norm: 60-day volume change vs 5-day MA
"""
from __future__ import annotations

import polars as pl

WINDOW = 60
FIELDS = ["close", "open", "high", "low", "vwap", "volume"]


class Alpha360:
    """Alpha360 factor set: 60-day normalized OHLCV, 360 features total."""

    @property
    def name(self) -> str:
        return "Alpha360"

    @property
    def description(self) -> str:
        return "60-day逐日归一化OHLCV，共360个特征"

    def compute(self, frame: pl.DataFrame) -> pl.DataFrame:
        """Compute Alpha360 factors.

        Args:
            frame: Must contain close, open, high, low, vwap, volume columns.
        Returns:
            DataFrame with 360 new feature columns appended.
        """
        result = frame.clone()

        close = frame["close"]
        open_ = frame["open"]
        high = frame["high"]
        low = frame["low"]
        vwap = frame["vwap"]
        volume = frame["volume"]

        # 5-day moving average volume for volume normalization
        vol_ma5 = volume.rolling_mean(window_size=5)

        for d in range(WINDOW):
            close_shift_d = close.shift(d)
            close_shift_d1 = close.shift(d + 1)

            result = result.with_columns(
                (close_shift_d / close_shift_d1 - 1).alias(f"close_{d}_norm"),
                (open_.shift(d) / close_shift_d - 1).alias(f"open_{d}_norm"),
                (high.shift(d) / close_shift_d - 1).alias(f"high_{d}_norm"),
                (low.shift(d) / close_shift_d - 1).alias(f"low_{d}_norm"),
                (vwap.shift(d) / close_shift_d - 1).alias(f"vwap_{d}_norm"),
                (volume.shift(d) / vol_ma5.shift(d) - 1).alias(f"volume_{d}_norm"),
            )

        return result

    def get_feature_names(self) -> list[str]:
        """Return all 360 feature column names."""
        names = []
        for d in range(WINDOW):
            for field in FIELDS:
                names.append(f"{field}_{d}_norm")
        return names
