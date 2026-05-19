"""Tests for BronzeWriter — raw data Parquet persistence + metadata recording."""

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import polars as pl
import pytest

from cquant.datahub.bronze_writer import BronzeWriter


@pytest.fixture
def catalog():
    c = MagicMock()
    return c


@pytest.fixture
def data():
    return pl.DataFrame(
        {
            "date": ["2025-01-01", "2025-01-02", "2025-01-03"],
            "close": [10.0, 10.5, 10.3],
            "volume": [1000, 1500, 1200],
        }
    )


def test_write_creates_parquet(catalog, data, tmp_path):
    """After write(), the Parquet file must exist on disk."""
    lake_root = str(tmp_path / "lake")
    writer = BronzeWriter(catalog, lake_root=lake_root)

    ingestion_id = writer.write(
        source="tdx",
        dataset="daily_bar",
        data=data,
        symbol="600000.SH",
        fetch_start=date(2025, 1, 1),
        fetch_end=date(2025, 1, 3),
    )

    parquet_path = (
        Path(lake_root) / "bronze" / "tdx" / "daily_bar" / f"{ingestion_id}.parquet"
    )
    assert parquet_path.exists(), f"Parquet file not found: {parquet_path}"

    # Verify contents round-trip
    restored = pl.read_parquet(parquet_path)
    assert restored.shape == data.shape


def test_write_records_metadata(catalog, data, tmp_path):
    """write() must INSERT a row into bronze_ingestions via catalog."""
    lake_root = str(tmp_path / "lake")
    writer = BronzeWriter(catalog, lake_root=lake_root)

    ingestion_id = writer.write(
        source="tushare",
        dataset="fundamentals",
        data=data,
        symbol=None,
        fetch_start=date(2025, 1, 1),
        fetch_end=date(2025, 6, 30),
    )

    # Verify catalog.execute was called with INSERT
    catalog.execute.assert_called_once()
    sql = catalog.execute.call_args[0][0]
    params = catalog.execute.call_args[0][1] if len(catalog.execute.call_args[0]) > 1 else []

    assert "INSERT INTO bronze_ingestions" in sql
    assert ingestion_id in params
    assert "tushare" in params
    assert "fundamentals" in params
    assert 3 in params  # row_count


def test_content_hash_is_deterministic(catalog, tmp_path):
    """Same data produces same content_hash, even across different ingestion_ids."""
    data = pl.DataFrame({"x": [1, 2, 3], "y": [4.0, 5.0, 6.0]})
    lake_root = str(tmp_path / "lake")
    writer = BronzeWriter(catalog, lake_root=lake_root)

    id1 = writer.write(source="src", dataset="ds", data=data)
    id2 = writer.write(source="src", dataset="ds", data=data)

    assert id1 != id2, "ingestion_ids must be unique"

    # Extract hashes from the two INSERT calls
    calls = catalog.execute.call_args_list
    assert len(calls) == 2

    def _extract_hash(call_args):
        params = call_args[0][1]
        # params order: ingestion_id, source, dataset, symbol, fetch_start, fetch_end,
        #               row_count, storage_uri, content_hash, schema_version, fetched_at, status, error_msg
        return params[8]

    hash1 = _extract_hash(calls[0])
    hash2 = _extract_hash(calls[1])
    assert hash1 == hash2, f"Content hash should be deterministic: {hash1} != {hash2}"
    assert len(hash1) == 64  # SHA-256 hex digest
