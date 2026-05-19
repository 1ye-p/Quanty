"""Unit tests for ml_lab.labels — forward return and triple barrier label construction."""

from __future__ import annotations

import polars as pl
import pytest

from cquant.ml_lab.labels import forward_return_labels, triple_barrier_labels


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def rising_prices() -> pl.DataFrame:
    """Prices that steadily rise for a single asset."""
    return pl.DataFrame({
        "asset_id": ["A"] * 10,
        "trade_date": list(range(10)),
        "close": [100.0 + i * 2.0 for i in range(10)],
    })


@pytest.fixture
def falling_prices() -> pl.DataFrame:
    """Prices that steadily fall for a single asset."""
    return pl.DataFrame({
        "asset_id": ["A"] * 10,
        "trade_date": list(range(10)),
        "close": [100.0 - i * 2.0 for i in range(10)],
    })


@pytest.fixture
def flat_prices() -> pl.DataFrame:
    """Flat prices for a single asset."""
    return pl.DataFrame({
        "asset_id": ["A"] * 10,
        "trade_date": list(range(10)),
        "close": [100.0] * 10,
    })


@pytest.fixture
def multi_asset_prices() -> pl.DataFrame:
    """Two assets with simple price patterns."""
    return pl.DataFrame({
        "asset_id": ["A", "A", "A", "A", "A", "B", "B", "B", "B", "B"],
        "trade_date": [1, 2, 3, 4, 5, 1, 2, 3, 4, 5],
        "close": [100.0, 110.0, 121.0, 133.1, 146.41, 50.0, 45.0, 40.5, 36.45, 32.805],
    })


# ── forward_return_labels tests ──────────────────────────────────────────────


class TestForwardReturnLabels:
    def test_columns(self, rising_prices: pl.DataFrame) -> None:
        """Output has correct columns."""
        result = forward_return_labels(rising_prices, periods=5)
        assert set(result.columns) == {"asset_id", "trade_date", "ret_5d"}

    def test_rising_asset_positive_return(self, rising_prices: pl.DataFrame) -> None:
        """Rising prices produce positive return labels."""
        result = forward_return_labels(rising_prices, periods=3)
        # Row 0: close=100, future_close=106 → 106/100-1 = 0.06
        val = result.filter(pl.col("trade_date") == 0).select("ret_3d").item()
        assert val > 0

    def test_falling_asset_negative_return(self, falling_prices: pl.DataFrame) -> None:
        """Falling prices produce negative return labels."""
        result = forward_return_labels(falling_prices, periods=3)
        val = result.filter(pl.col("trade_date") == 0).select("ret_3d").item()
        assert val < 0

    def test_flat_asset_zero_return(self, flat_prices: pl.DataFrame) -> None:
        """Flat prices produce zero return labels."""
        result = forward_return_labels(flat_prices, periods=3)
        val = result.filter(pl.col("trade_date") == 0).select("ret_3d").item()
        assert val == pytest.approx(0.0)

    def test_last_periods_are_null(self, rising_prices: pl.DataFrame) -> None:
        """Last N rows per asset have null labels."""
        result = forward_return_labels(rising_prices, periods=3)
        # trade_date 7, 8, 9 → null (last 3 of 10)
        nulls = result.filter(pl.col("trade_date") >= 7).select("ret_3d")
        assert nulls.null_count().item() == 3

    def test_custom_column_names(self, multi_asset_prices: pl.DataFrame) -> None:
        """Custom output_col works."""
        result = forward_return_labels(multi_asset_prices, periods=2, output_col="fwd_2d")
        assert "fwd_2d" in result.columns
        assert "ret_2d" not in result.columns

    def test_multi_asset_isolation(self, multi_asset_prices: pl.DataFrame) -> None:
        """Labels are computed per-asset, not across assets."""
        result = forward_return_labels(multi_asset_prices, periods=2)
        # Asset B trade_date 1: future_close (trade_date 3) = 40.5, 40.5/50-1 = -0.19
        b_val = result.filter((pl.col("asset_id") == "B") & (pl.col("trade_date") == 1)).select("ret_2d").item()
        assert b_val == pytest.approx(-0.19)


# ── triple_barrier_labels tests ──────────────────────────────────────────────


class TestTripleBarrierLabels:
    def test_columns(self, rising_prices: pl.DataFrame) -> None:
        """Output has correct columns."""
        result = triple_barrier_labels(rising_prices)
        assert set(result.columns) == {"asset_id", "trade_date", "tb_label"}

    def test_label_values(self, rising_prices: pl.DataFrame) -> None:
        """Labels are 1.0, -1.0, or 0.0."""
        result = triple_barrier_labels(rising_prices)
        valid = result.drop_nulls("tb_label")
        unique_vals = set(valid["tb_label"].to_list())
        assert unique_vals.issubset({1.0, -1.0, 0.0})

    def test_rising_hits_upper(self) -> None:
        """Monotonically rising prices hit upper barrier."""
        prices = pl.DataFrame({
            "asset_id": ["A"] * 20,
            "trade_date": list(range(20)),
            "close": [100.0 + i * 1.0 for i in range(20)],
        })
        result = triple_barrier_labels(prices, upper_pct=0.03, lower_pct=-0.03, max_periods=10)
        val = result.filter(pl.col("trade_date") == 0).select("tb_label").item()
        assert val == 1.0

    def test_falling_hits_lower(self) -> None:
        """Monotonically falling prices hit lower barrier."""
        prices = pl.DataFrame({
            "asset_id": ["A"] * 20,
            "trade_date": list(range(20)),
            "close": [100.0 - i * 1.0 for i in range(20)],
        })
        result = triple_barrier_labels(prices, upper_pct=0.03, lower_pct=-0.03, max_periods=10)
        val = result.filter(pl.col("trade_date") == 0).select("tb_label").item()
        assert val == -1.0

    def test_flat_hits_neither(self) -> None:
        """Flat prices within barriers yield 0.0."""
        prices = pl.DataFrame({
            "asset_id": ["A"] * 20,
            "trade_date": list(range(20)),
            "close": [100.0 + (0.1 if i % 2 == 0 else -0.1) for i in range(20)],
        })
        result = triple_barrier_labels(prices, upper_pct=0.05, lower_pct=-0.05, max_periods=5)
        val = result.filter(pl.col("trade_date") == 0).select("tb_label").item()
        assert val == 0.0

    def test_last_rows_are_null(self, rising_prices: pl.DataFrame) -> None:
        """Rows without enough future data have null labels."""
        result = triple_barrier_labels(rising_prices, max_periods=5)
        nulls = result.tail(5).select("tb_label").null_count().item()
        assert nulls == 5
