"""Unit tests for ml_lab.preprocessing — cross-sectional normalization and cleaning."""

from __future__ import annotations

import polars as pl
import pytest

from cquant.ml_lab.preprocessing import (
    cross_sectional_zscore,
    fill_nulls_cross_section,
    winsorize,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def factor_frame() -> pl.DataFrame:
    """Two assets, two dates, two factor columns with known values."""
    return pl.DataFrame({
        "asset_id": ["A", "B", "A", "B"],
        "trade_date": [1, 1, 2, 2],
        "factor1": [10.0, 20.0, 30.0, 40.0],
        "factor2": [1.0, 3.0, 5.0, 7.0],
    })


@pytest.fixture
def outlier_frame() -> pl.DataFrame:
    """Frame with an extreme outlier for winsorize testing.

    20 normal values + 1 extreme outlier (100.0) per date so the
    0.95 quantile falls well below 100.
    """
    n = 20
    assets = [f"A{i}" for i in range(n)] + ["OUTLIER"]
    vals = [float(i) for i in range(1, n + 1)] + [100.0]
    return pl.DataFrame({
        "asset_id": assets * 2,
        "trade_date": [1] * (n + 1) + [2] * (n + 1),
        "factor1": vals * 2,
    })


@pytest.fixture
def null_frame() -> pl.DataFrame:
    """Frame with null values for fill testing."""
    return pl.DataFrame({
        "asset_id": ["A", "B", "C", "A", "B", "C"],
        "trade_date": [1, 1, 1, 2, 2, 2],
        "factor1": [10.0, None, 30.0, None, 50.0, 60.0],
    })


# ── cross_sectional_zscore tests ─────────────────────────────────────────────


class TestCrossSectionalZscore:
    def test_columns_preserved(self, factor_frame: pl.DataFrame) -> None:
        """Output keeps all original columns."""
        result = cross_sectional_zscore(factor_frame, columns=["factor1", "factor2"])
        assert set(result.columns) == set(factor_frame.columns)

    def test_zero_mean(self, factor_frame: pl.DataFrame) -> None:
        """Z-scored values have mean ≈ 0 per date."""
        result = cross_sectional_zscore(factor_frame, columns=["factor1"])
        for date_val in [1, 2]:
            date_vals = result.filter(pl.col("trade_date") == date_val)["factor1"]
            assert date_vals.mean() == pytest.approx(0.0, abs=1e-9)

    def test_unit_variance(self, factor_frame: pl.DataFrame) -> None:
        """Z-scored values have std ≈ 1 per date."""
        result = cross_sectional_zscore(factor_frame, columns=["factor1"])
        for date_val in [1, 2]:
            date_vals = result.filter(pl.col("trade_date") == date_val)["factor1"]
            # Population std with 2 values: std = half the range
            assert date_vals.std() == pytest.approx(1.0, abs=1e-9)

    def test_multiple_columns(self, factor_frame: pl.DataFrame) -> None:
        """Both factor columns are z-scored independently."""
        result = cross_sectional_zscore(factor_frame, columns=["factor1", "factor2"])
        for date_val in [1, 2]:
            for col in ["factor1", "factor2"]:
                date_vals = result.filter(pl.col("trade_date") == date_val)[col]
                assert date_vals.mean() == pytest.approx(0.0, abs=1e-9)


# ── winsorize tests ──────────────────────────────────────────────────────────


class TestWinsorize:
    def test_clips_extremes(self, outlier_frame: pl.DataFrame) -> None:
        """Outlier (100.0) gets clipped to upper quantile bound."""
        result = winsorize(outlier_frame, columns=["factor1"], lower=0.05, upper=0.95)
        # Date 1: values [1, 2, 3, 100] — 100 should be clipped
        date1_vals = result.filter(pl.col("trade_date") == 1)["factor1"]
        assert date1_vals.max() < 100.0

    def test_no_clip_without_outliers(self) -> None:
        """Uniform data is not clipped."""
        frame = pl.DataFrame({
            "asset_id": ["A", "B", "C"],
            "trade_date": [1, 1, 1],
            "factor1": [1.0, 2.0, 3.0],
        })
        result = winsorize(frame, columns=["factor1"], lower=0.01, upper=0.99)
        assert result["factor1"].to_list() == [1.0, 2.0, 3.0]

    def test_preserves_columns(self, outlier_frame: pl.DataFrame) -> None:
        """Output keeps all original columns."""
        result = winsorize(outlier_frame, columns=["factor1"])
        assert set(result.columns) == set(outlier_frame.columns)


# ── fill_nulls_cross_section tests ───────────────────────────────────────────


class TestFillNullsCrossSection:
    def test_fill_median(self, null_frame: pl.DataFrame) -> None:
        """Nulls filled with cross-sectional median per date."""
        result = fill_nulls_cross_section(null_frame, columns=["factor1"], method="median")
        # Date 1: [10, None, 30] → median = 20
        val_a = result.filter((pl.col("trade_date") == 1) & (pl.col("asset_id") == "A"))["factor1"].item()
        val_b = result.filter((pl.col("trade_date") == 1) & (pl.col("asset_id") == "B"))["factor1"].item()
        val_c = result.filter((pl.col("trade_date") == 1) & (pl.col("asset_id") == "C"))["factor1"].item()
        assert val_b == pytest.approx(20.0)
        assert val_a == 10.0  # unchanged
        assert val_c == 30.0  # unchanged

    def test_fill_zero(self, null_frame: pl.DataFrame) -> None:
        """Nulls filled with 0."""
        result = fill_nulls_cross_section(null_frame, columns=["factor1"], method="zero")
        assert result["factor1"].null_count() == 0
        # Original null at date 1 asset B should be 0
        val = result.filter((pl.col("trade_date") == 1) & (pl.col("asset_id") == "B"))["factor1"].item()
        assert val == 0.0

    def test_no_nulls_left(self, null_frame: pl.DataFrame) -> None:
        """All nulls are filled regardless of method."""
        for method in ["median", "mean", "zero"]:
            result = fill_nulls_cross_section(null_frame, columns=["factor1"], method=method)
            assert result["factor1"].null_count() == 0

    def test_preserves_columns(self, null_frame: pl.DataFrame) -> None:
        """Output keeps all original columns."""
        result = fill_nulls_cross_section(null_frame, columns=["factor1"])
        assert set(result.columns) == set(null_frame.columns)
