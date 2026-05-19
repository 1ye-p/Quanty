"""cquant.datahub.connectors.csv_parquet_connector — Local file connector.

Reads CSV or Parquet files from the local filesystem for offline research
and fixture data injection.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import polars as pl

from cquant.core.enums import Frequency, Market
from cquant.core.errors import IngestError
from cquant.datahub.connectors.base import DataConnector, DataSpec, RawBatch

logger = logging.getLogger(__name__)


class CSVParquetConnector(DataConnector):
    """Reads CSV and Parquet files from the local filesystem.

    The file path is expected to be provided in spec.extra['file_path'].
    Alternatively, a directory can be provided and all matching files within
    will be read.
    """

    @property
    def source_name(self) -> str:
        return "csv_parquet"

    @property
    def supported_markets(self) -> list[Market]:
        return list(Market)

    @property
    def supported_frequencies(self) -> list[Frequency]:
        return list(Frequency)

    def fetch(self, spec: DataSpec) -> Iterable[RawBatch]:
        file_path = spec.extra.get("file_path")
        if not file_path:
            raise IngestError("CSVParquetConnector requires spec.extra['file_path']")

        path = Path(file_path)
        fetched_at = datetime.now(tz=timezone.utc).isoformat()

        if path.is_dir():
            files = list(path.glob("*.parquet")) + list(path.glob("*.csv"))
        elif path.exists():
            files = [path]
        else:
            raise IngestError(f"File or directory not found: {path}")

        for f in sorted(files):
            try:
                if f.suffix == ".parquet":
                    df = pl.read_parquet(f)
                else:
                    df = pl.read_csv(f, try_parse_dates=True)

                yield RawBatch(
                    source=self.source_name,
                    dataset=spec.extra.get("dataset", "local_file"),
                    data=df,
                    fetched_at=fetched_at,
                    spec=spec,
                )
            except Exception as exc:
                logger.error("Failed to read %s: %s", f, exc)
                raise IngestError(f"Failed to read {f}: {exc}") from exc
