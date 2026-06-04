"""DuckDB backend implementation."""
from __future__ import annotations

import logging
from typing import Any

import polars as pl

logger = logging.getLogger(__name__)


class DuckDBBackend:
    """DuckDB database backend."""

    def __init__(self, db_path: str = "data/catalog.duckdb", read_only: bool = False) -> None:
        import duckdb
        self._conn = duckdb.connect(db_path, read_only=read_only)
        logger.info("DuckDB backend connected: %s (read_only=%s)", db_path, read_only)

    def query(self, sql: str, params: list[Any] | None = None) -> pl.DataFrame:
        rel = self._conn.execute(sql, params or [])
        return rel.pl()

    def execute(self, sql: str, params: list[Any] | None = None) -> None:
        self._conn.execute(sql, params or [])

    def executemany(self, sql: str, rows: list[tuple]) -> None:
        self._conn.executemany(sql, rows)

    def upsert(
        self,
        table: str,
        columns: list[str],
        rows: list[tuple],
        conflict_columns: list[str],
    ) -> None:
        cols = ", ".join(columns)
        placeholders = ", ".join(["?"] * len(columns))
        sql = f"INSERT OR REPLACE INTO {table} ({cols}) VALUES ({placeholders})"
        self._conn.executemany(sql, rows)

    def close(self) -> None:
        self._conn.close()
