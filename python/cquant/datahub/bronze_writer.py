"""cquant.datahub.bronze_writer — Persist raw data to Parquet and record metadata.

Bronze layer stores raw ingested data as Parquet files on the filesystem and
tracks provenance metadata in the ``bronze_ingestions`` DuckDB table.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

import polars as pl

from cquant.datahub.catalog import Catalog


class BronzeWriter:
    """Write raw DataFrames to the bronze lake layer.

    Parameters
    ----------
    catalog : Catalog
        DuckDB catalog used for metadata queries.
    lake_root : str
        Root directory for the data lake.  Parquet files land under
        ``{lake_root}/bronze/{source}/{dataset}/{ingestion_id}.parquet``.
    """

    def __init__(self, catalog: Catalog, lake_root: str = "data/lake") -> None:
        self._catalog = catalog
        self._lake_root = Path(lake_root)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def write(
        self,
        source: str,
        dataset: str,
        data: pl.DataFrame,
        symbol: str | None = None,
        fetch_start: date | None = None,
        fetch_end: date | None = None,
    ) -> str:
        """Write *data* to a Parquet file and record metadata.

        Returns the ``ingestion_id`` (UUID string).
        """
        ingestion_id = str(uuid.uuid4())

        # 1. Build output path
        parquet_dir = self._lake_root / "bronze" / source / dataset
        parquet_dir.mkdir(parents=True, exist_ok=True)
        parquet_path = parquet_dir / f"{ingestion_id}.parquet"

        # 2. Write Parquet
        data.write_parquet(parquet_path)

        # 3. Compute SHA-256 of the written Parquet bytes
        content_hash = hashlib.sha256(parquet_path.read_bytes()).hexdigest()

        # 4. Persist metadata
        row_count = data.shape[0]
        fetched_at = datetime.now(tz=timezone.utc).isoformat()
        storage_uri = str(parquet_path)

        self._catalog.execute(
            """
            INSERT INTO bronze_ingestions
                (ingestion_id, source, dataset, symbol, fetch_start_date,
                 fetch_end_date, row_count, storage_uri, content_hash,
                 schema_version, fetched_at, status, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '1.0', ?, 'ok', NULL)
            """,
            [
                ingestion_id,
                source,
                dataset,
                symbol,
                fetch_start,
                fetch_end,
                row_count,
                storage_uri,
                content_hash,
                fetched_at,
            ],
        )

        return ingestion_id
