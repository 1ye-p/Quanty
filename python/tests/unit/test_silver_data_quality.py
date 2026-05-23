"""Tests for SilverNormalizer data quality filters."""
from __future__ import annotations

from datetime import date, datetime

import polars as pl
import pytest

from cquant.datahub.connectors.base import RawBatch
from cquant.datahub.pipelines.silver import SilverNormalizer


def _make_batch(rows: list[dict], source: str = "csv_parquet") -> RawBatch:
    """Helper to create a RawBatch from row dicts."""
    return RawBatch(
        source=source,
        dataset="daily_bar",
        data=pl.DataFrame(rows),
        fetched_at=datetime.utcnow().isoformat() + "Z",
    )


class TestDataQualityFilters:
    """Test SilverNormalizer._clean_data_quality() behavior."""

    def test_zero_close_price_is_removed(self) -> None:
        """Rows with close price = 0 should be filtered out."""
        normalizer = SilverNormalizer()
        batch = _make_batch([
            {
                "asset_id": "SSE:600036",
                "trade_date": date(2025, 1, 2),
                "open": 10.0,
                "high": 11.0,
                "low": 9.0,
                "close": 0.0,
                "volume": 1_000_000,
                "amount": 10_000_000,
                "adj_factor": 1.0,
                "is_suspended": False,
                "source": "test",
            },
            {
                "asset_id": "SSE:600036",
                "trade_date": date(2025, 1, 3),
                "open": 10.0,
                "high": 11.0,
                "low": 9.0,
                "close": 10.5,
                "volume": 1_000_000,
                "amount": 10_500_000,
                "adj_factor": 1.0,
                "is_suspended": False,
                "source": "test",
            },
        ])
        result = normalizer.normalize(batch)
        assert len(result) == 1
        assert result["close"][0] == pytest.approx(10.5)

    def test_negative_close_price_is_removed(self) -> None:
        """Rows with close price < 0 should be filtered out."""
        normalizer = SilverNormalizer()
        batch = _make_batch([
            {
                "asset_id": "SSE:600036",
                "trade_date": date(2025, 1, 2),
                "open": 10.0,
                "high": 11.0,
                "low": 9.0,
                "close": -5.0,
                "volume": 1_000_000,
                "amount": 10_000_000,
                "adj_factor": 1.0,
                "is_suspended": False,
                "source": "test",
            },
        ])
        result = normalizer.normalize(batch)
        assert len(result) == 0

    def test_negative_volume_is_clipped_to_zero(self) -> None:
        """Rows with negative volume should have it clipped to 0, row retained."""
        normalizer = SilverNormalizer()
        batch = _make_batch([
            {
                "asset_id": "SSE:600036",
                "trade_date": date(2025, 1, 2),
                "open": 10.0,
                "high": 11.0,
                "low": 9.0,
                "close": 10.5,
                "volume": -100,
                "amount": 10_500_000,
                "adj_factor": 1.0,
                "is_suspended": False,
                "source": "test",
            },
        ])
        result = normalizer.normalize(batch)
        assert len(result) == 1
        assert result["volume"][0] == 0.0

    def test_valid_data_passes_through_unchanged(self) -> None:
        """Valid rows should pass through data quality filter unchanged."""
        normalizer = SilverNormalizer()
        batch = _make_batch([
            {
                "asset_id": "SSE:600036",
                "trade_date": date(2025, 1, 2),
                "open": 10.0,
                "high": 11.0,
                "low": 9.0,
                "close": 10.5,
                "volume": 1_000_000,
                "amount": 10_500_000,
                "adj_factor": 1.0,
                "is_suspended": False,
                "source": "test",
            },
        ])
        result = normalizer.normalize(batch)
        assert len(result) == 1
        assert result["close"][0] == pytest.approx(10.5)
        assert result["volume"][0] == pytest.approx(1_000_000)

    def test_mixed_valid_invalid_rows(self) -> None:
        """Mix of valid and invalid rows should filter appropriately."""
        normalizer = SilverNormalizer()
        batch = _make_batch([
            # Valid
            {
                "asset_id": "SSE:600036",
                "trade_date": date(2025, 1, 1),
                "open": 10.0,
                "high": 11.0,
                "low": 9.0,
                "close": 10.5,
                "volume": 1_000_000,
                "amount": 10_500_000,
                "adj_factor": 1.0,
                "is_suspended": False,
                "source": "test",
            },
            # Zero close
            {
                "asset_id": "SSE:600036",
                "trade_date": date(2025, 1, 2),
                "open": 10.0,
                "high": 11.0,
                "low": 9.0,
                "close": 0.0,
                "volume": 1_000_000,
                "amount": 0,
                "adj_factor": 1.0,
                "is_suspended": False,
                "source": "test",
            },
            # Valid with negative volume
            {
                "asset_id": "SSE:600036",
                "trade_date": date(2025, 1, 3),
                "open": 10.0,
                "high": 11.0,
                "low": 9.0,
                "close": 10.2,
                "volume": -50,
                "amount": 10_200_000,
                "adj_factor": 1.0,
                "is_suspended": False,
                "source": "test",
            },
            # Negative close
            {
                "asset_id": "SSE:600036",
                "trade_date": date(2025, 1, 4),
                "open": 10.0,
                "high": 11.0,
                "low": 9.0,
                "close": -2.5,
                "volume": 1_000_000,
                "amount": 0,
                "adj_factor": 1.0,
                "is_suspended": False,
                "source": "test",
            },
            # Valid
            {
                "asset_id": "SSE:600036",
                "trade_date": date(2025, 1, 5),
                "open": 10.0,
                "high": 11.0,
                "low": 9.0,
                "close": 10.8,
                "volume": 2_000_000,
                "amount": 21_600_000,
                "adj_factor": 1.0,
                "is_suspended": False,
                "source": "test",
            },
        ])
        result = normalizer.normalize(batch)
        # Should have 3 rows: 1st, 3rd (clipped), and 5th
        assert len(result) == 3
        # Check the rows
        dates = result["trade_date"].to_list()
        assert dates == [date(2025, 1, 1), date(2025, 1, 3), date(2025, 1, 5)]
        # Check that volume was clipped
        assert result["volume"][1] == 0.0

    def test_multiple_assets_filtered_independently(self) -> None:
        """Data quality filter should work across multiple assets."""
        normalizer = SilverNormalizer()
        batch = _make_batch([
            # Valid for SSE:600036
            {
                "asset_id": "SSE:600036",
                "trade_date": date(2025, 1, 1),
                "open": 10.0,
                "high": 11.0,
                "low": 9.0,
                "close": 10.5,
                "volume": 1_000_000,
                "amount": 10_500_000,
                "adj_factor": 1.0,
                "is_suspended": False,
                "source": "test",
            },
            # Invalid close for SZSE:000001
            {
                "asset_id": "SZSE:000001",
                "trade_date": date(2025, 1, 1),
                "open": 20.0,
                "high": 21.0,
                "low": 19.0,
                "close": 0.0,
                "volume": 2_000_000,
                "amount": 0,
                "adj_factor": 1.0,
                "is_suspended": False,
                "source": "test",
            },
            # Valid for SZSE:000001
            {
                "asset_id": "SZSE:000001",
                "trade_date": date(2025, 1, 2),
                "open": 20.0,
                "high": 21.0,
                "low": 19.0,
                "close": 20.5,
                "volume": 2_000_000,
                "amount": 41_000_000,
                "adj_factor": 1.0,
                "is_suspended": False,
                "source": "test",
            },
        ])
        result = normalizer.normalize(batch)
        # Should have 2 rows (invalid middle row removed)
        assert len(result) == 2
        # Check that we kept the valid rows
        expected_assets = ["SSE:600036", "SZSE:000001"]
        assert result["asset_id"].to_list() == expected_assets

    def test_very_small_positive_close_is_kept(self) -> None:
        """Even tiny positive close prices should pass (only > 0 required)."""
        normalizer = SilverNormalizer()
        batch = _make_batch([
            {
                "asset_id": "SSE:600036",
                "trade_date": date(2025, 1, 1),
                "open": 0.001,
                "high": 0.002,
                "low": 0.0005,
                "close": 0.0001,  # Very small but positive
                "volume": 1_000_000,
                "amount": 100,
                "adj_factor": 1.0,
                "is_suspended": False,
                "source": "test",
            },
        ])
        result = normalizer.normalize(batch)
        assert len(result) == 1
        assert result["close"][0] == pytest.approx(0.0001)

    def test_missing_close_column_handled_gracefully(self) -> None:
        """If close column is missing, should not crash."""
        normalizer = SilverNormalizer()
        # Create batch without close column initially
        batch = _make_batch([
            {
                "asset_id": "SSE:600036",
                "trade_date": date(2025, 1, 1),
                "open": 10.0,
                "high": 11.0,
                "low": 9.0,
                # No close column
                "volume": 1_000_000,
                "amount": 10_500_000,
                "adj_factor": 1.0,
                "is_suspended": False,
                "source": "test",
            },
        ])
        # Should not crash; _ensure_required_columns adds missing close as None
        result = normalizer.normalize(batch)
        assert "close" in result.columns

    def test_missing_volume_column_handled_gracefully(self) -> None:
        """If volume column is missing, should not crash."""
        normalizer = SilverNormalizer()
        # Create batch without volume column initially
        batch = _make_batch([
            {
                "asset_id": "SSE:600036",
                "trade_date": date(2025, 1, 1),
                "open": 10.0,
                "high": 11.0,
                "low": 9.0,
                "close": 10.5,
                # No volume column
                "amount": 10_500_000,
                "adj_factor": 1.0,
                "is_suspended": False,
                "source": "test",
            },
        ])
        # Should not crash; _ensure_required_columns adds missing volume as None
        result = normalizer.normalize(batch)
        assert "volume" in result.columns

    def test_filter_applied_after_source_normalization(self) -> None:
        """Data quality filter should apply to data from any source."""
        normalizer = SilverNormalizer()
        # Using akshare source format
        batch = RawBatch(
            source="akshare",
            dataset="daily_bar",
            data=pl.DataFrame([
                {
                    "日期": "2025-01-01",
                    "开盘": 10.0,
                    "最高": 11.0,
                    "最低": 9.0,
                    "收盘": 0.0,  # Invalid
                    "成交量": 1_000_000,
                    "成交额": 0,
                    "symbol": "600036",
                },
            ]),
            fetched_at=datetime.utcnow().isoformat() + "Z",
        )
        result = normalizer.normalize(batch)
        # Should be filtered out
        assert len(result) == 0

    def test_zero_volume_is_okay(self) -> None:
        """Zero volume itself is okay (clipping won't change it), but negative isn't."""
        normalizer = SilverNormalizer()
        batch = _make_batch([
            {
                "asset_id": "SSE:600036",
                "trade_date": date(2025, 1, 1),
                "open": 10.0,
                "high": 11.0,
                "low": 9.0,
                "close": 10.5,
                "volume": 0.0,  # Zero volume is fine
                "amount": 0,
                "adj_factor": 1.0,
                "is_suspended": False,
                "source": "test",
            },
        ])
        result = normalizer.normalize(batch)
        assert len(result) == 1
        assert result["volume"][0] == 0.0
