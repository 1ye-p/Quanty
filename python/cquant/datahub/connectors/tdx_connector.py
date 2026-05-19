"""cquant.datahub.connectors.tdx_connector — TDX DuckDB data connector.

Reads A-share daily bars directly from a local tdx.db (通达信) DuckDB file.
No external API calls — fastest path to 20+ years of CN market data.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Iterable

import duckdb
import polars as pl

from cquant.core.enums import Frequency, Market
from cquant.core.errors import IngestError
from cquant.datahub.connectors.base import DataConnector, DataSpec, RawBatch

logger = logging.getLogger(__name__)


class TdxDuckDBConnector(DataConnector):
    """Connector for local TDX DuckDB files (CN A-share daily bars).

    Reads from ``raw_stocks_daily`` (raw prices) and ``v_qfq_daily`` (pre-adjusted
    prices with qfq_factor).  Symbol mapping: ``sh600036`` → ``SSE:600036``.

    Usage::

        connector = TdxDuckDBConnector("tdx.db")
        batches = list(connector.fetch(DataSpec(
            symbols=["SSE:600036", "SZSE:000001"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            frequency=Frequency.D1,
            market=Market.CN,
        )))
    """

    def __init__(self, db_path: str = "tdx.db") -> None:
        self._db_path = db_path

    @property
    def source_name(self) -> str:
        return "tdx"

    @property
    def supported_markets(self) -> list[Market]:
        return [Market.CN]

    @property
    def supported_frequencies(self) -> list[Frequency]:
        return [Frequency.D1]

    def fetch(self, spec: DataSpec) -> Iterable[RawBatch]:
        fetched_at = datetime.now(tz=timezone.utc).isoformat()
        tdx_symbols = [_to_tdx_symbol(s) for s in spec.symbols]

        # Chunk by symbol groups to avoid loading everything into memory
        chunk_size = 50
        for i in range(0, len(tdx_symbols), chunk_size):
            chunk = tdx_symbols[i : i + chunk_size]
            df = self._fetch_chunk(chunk, spec.start_date, spec.end_date)
            if not df.is_empty():
                yield RawBatch(
                    source=self.source_name,
                    dataset="daily_bar",
                    data=df,
                    fetched_at=fetched_at,
                    spec=spec,
                )

    def fetch_all(
        self,
        start_date: date,
        end_date: date,
        chunk_days: int = 365,
    ) -> Iterable[RawBatch]:
        """Fetch ALL symbols in chunks by date range (for full ingestion).

        Yields one RawBatch per date chunk, containing all symbols for that period.
        This avoids loading 21M+ rows into memory at once.
        """
        fetched_at = datetime.now(tz=timezone.utc).isoformat()
        current = start_date

        while current <= end_date:
            chunk_end = min(
                date(current.year + 1, 1, 1) if current.month == 1 and current.day == 1
                else date(current.year, 12, 31),
                end_date,
            )
            df = self._fetch_date_range(current, chunk_end)
            if not df.is_empty():
                yield RawBatch(
                    source=self.source_name,
                    dataset="daily_bar",
                    data=df,
                    fetched_at=fetched_at,
                    spec=None,
                )
                logger.info(
                    "TDX chunk %s to %s: %d rows",
                    current, chunk_end, len(df),
                )
            current = date(chunk_end.year + 1, 1, 1) if chunk_end.month == 12 and chunk_end.day == 31 else date(chunk_end.year, chunk_end.month + 1, 1)

    def _fetch_chunk(
        self, tdx_symbols: list[str], start: date, end: date
    ) -> pl.DataFrame:
        """Fetch daily data for a list of TDX symbols."""
        con = duckdb.connect(self._db_path, read_only=True)
        try:
            placeholders = ", ".join(f"'{s}'" for s in tdx_symbols)
            query = f"""
                SELECT
                    r.symbol,
                    r.date,
                    r.open,
                    r.high,
                    r.low,
                    r.close,
                    r.volume,
                    r.amount,
                    COALESCE(q.qfq_factor, 1.0) AS qfq_factor
                FROM raw_stocks_daily r
                LEFT JOIN v_qfq_daily q
                    ON r.symbol = q.symbol AND r.date = q.date
                WHERE r.symbol IN ({placeholders})
                  AND r.date >= '{start.isoformat()}'
                  AND r.date <= '{end.isoformat()}'
                ORDER BY r.symbol, r.date
            """
            df = con.execute(query).pl()
        finally:
            con.close()

        if df.is_empty():
            return df

        # Add asset_id column
        df = df.with_columns(
            pl.col("symbol").map_elements(_to_asset_id, return_dtype=pl.Utf8).alias("asset_id")
        ).drop("symbol")

        return df

    def _fetch_date_range(self, start: date, end: date) -> pl.DataFrame:
        """Fetch all symbols for a date range (chunked ingestion)."""
        con = duckdb.connect(self._db_path, read_only=True)
        try:
            query = f"""
                SELECT
                    r.symbol,
                    r.date,
                    r.open,
                    r.high,
                    r.low,
                    r.close,
                    r.volume,
                    r.amount,
                    COALESCE(q.qfq_factor, 1.0) AS qfq_factor
                FROM raw_stocks_daily r
                LEFT JOIN v_qfq_daily q
                    ON r.symbol = q.symbol AND r.date = q.date
                WHERE r.date >= '{start.isoformat()}'
                  AND r.date <= '{end.isoformat()}'
                ORDER BY r.symbol, r.date
            """
            df = con.execute(query).pl()
        finally:
            con.close()

        if df.is_empty():
            return df

        df = df.with_columns(
            pl.col("symbol").map_elements(_to_asset_id, return_dtype=pl.Utf8).alias("asset_id")
        ).drop("symbol")

        return df


def _to_tdx_symbol(asset_id: str) -> str:
    """Convert cQuant asset_id ('SSE:600036') to TDX symbol ('sh600036')."""
    if ":" not in asset_id:
        return asset_id.lower()
    exchange, symbol = asset_id.split(":", 1)
    prefix = {"SSE": "sh", "SZSE": "sz", "BSE": "bj"}.get(exchange, exchange.lower())
    return f"{prefix}{symbol}"


def _to_asset_id(tdx_symbol: str) -> str:
    """Convert TDX symbol ('sh600036') to cQuant asset_id ('SSE:600036')."""
    if tdx_symbol.startswith("sh"):
        return f"SSE:{tdx_symbol[2:]}"
    if tdx_symbol.startswith("sz"):
        return f"SZSE:{tdx_symbol[2:]}"
    if tdx_symbol.startswith("bj"):
        return f"BSE:{tdx_symbol[2:]}"
    return tdx_symbol
