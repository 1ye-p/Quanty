"""Tests for Alpha360 factor set (360 features)."""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import polars as pl
import pytest

from cquant.factorlab.factors.alpha360 import Alpha360, WINDOW, FIELDS


def _make_frame(n: int = 100) -> pl.DataFrame:
    """Create a synthetic DataFrame with OHLCV + vwap columns."""
    rng = np.random.default_rng(42)
    dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(n)]
    p = 100.0
    rows = []
    for d in dates:
        p *= 1 + rng.normal(0.001, 0.01)
        rows.append({
            "asset_id": "A",
            "trade_date": d,
            "open": p * 0.99,
            "high": p * 1.02,
            "low": p * 0.97,
            "close": p,
            "volume": 1e6 * (1 + rng.normal(0, 0.1)),
            "vwap": p * (1 + rng.normal(0, 0.005)),
        })
    return pl.DataFrame(rows)


class TestAlpha360:
    def setup_method(self) -> None:
        self.alpha360 = Alpha360()
        self.frame = _make_frame(100)
        self.result = self.alpha360.compute(self.frame)

    def test_output_has_360_feature_columns(self) -> None:
        """Result should have exactly 360 new feature columns."""
        original_cols = set(self.frame.columns)
        result_cols = set(self.result.columns)
        new_cols = result_cols - original_cols
        assert len(new_cols) == 360, f"Expected 360 new columns, got {len(new_cols)}"

    def test_row_count_matches_input(self) -> None:
        """Row count should be unchanged."""
        assert len(self.result) == len(self.frame)

    def test_feature_names_correct(self) -> None:
        """Feature names should follow the {field}_{day}_norm pattern."""
        expected = self.alpha360.get_feature_names()
        assert len(expected) == 360

        for d in range(WINDOW):
            for field in FIELDS:
                col_name = f"{field}_{d}_norm"
                assert col_name in expected, f"Missing feature: {col_name}"
                assert col_name in self.result.columns, f"Missing column in result: {col_name}"

    def test_feature_names_order(self) -> None:
        """Feature names should be in order: close_0, open_0, ..., volume_0, close_1, ..."""
        names = self.alpha360.get_feature_names()
        assert names[0] == "close_0_norm"
        assert names[1] == "open_0_norm"
        assert names[5] == "volume_0_norm"
        assert names[6] == "close_1_norm"

    def test_close_norm_is_return(self) -> None:
        """close_{d}_norm should be close[d] / close[d+1] - 1 (return)."""
        # For d=0, close_0_norm = close / close.shift(1) - 1
        expected = (self.frame["close"] / self.frame["close"].shift(1) - 1)
        result = self.result["close_0_norm"]
        # Compare non-null values
        mask = expected.is_not_null()
        assert all(
            abs(a - b) < 1e-10
            for a, b in zip(expected.filter(mask).to_list(), result.filter(mask).to_list())
        )

    def test_open_norm_is_deviation(self) -> None:
        """open_{d}_norm should be open[d] / close[d] - 1 (deviation)."""
        expected = (self.frame["open"] / self.frame["close"] - 1)
        result = self.result["open_0_norm"]
        mask = expected.is_not_null()
        assert all(
            abs(a - b) < 1e-10
            for a, b in zip(expected.filter(mask).to_list(), result.filter(mask).to_list())
        )

    def test_volume_norm_uses_ma5(self) -> None:
        """volume_{d}_norm should be volume[d] / vol_ma5[d] - 1."""
        vol_ma5 = self.frame["volume"].rolling_mean(window_size=5)
        expected = (self.frame["volume"] / vol_ma5 - 1)
        result = self.result["volume_0_norm"]
        mask = expected.is_not_null()
        assert all(
            abs(a - b) < 1e-10
            for a, b in zip(expected.filter(mask).to_list(), result.filter(mask).to_list())
        )

    def test_first_61_rows_null_for_close_norm(self) -> None:
        """close_{d}_norm needs d+1 rows of history, so first 61 rows should be null for d=59."""
        # For d=59, we need shift(60), so first 60 rows are null for close_59_norm
        col = self.result["close_59_norm"]
        assert col.head(60).null_count() == 60
        assert col.drop_nulls().len() > 0

    def test_original_columns_preserved(self) -> None:
        """Original columns should still be present."""
        for col in self.frame.columns:
            assert col in self.result.columns

    def test_name_property(self) -> None:
        """Name property should return 'Alpha360'."""
        assert self.alpha360.name == "Alpha360"
