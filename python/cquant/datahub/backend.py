"""Catalog backend protocol — database-agnostic interface."""
from __future__ import annotations

from typing import Any, Protocol

import polars as pl


class CatalogBackend(Protocol):
    """Database backend interface for Catalog."""

    def query(self, sql: str, params: list[Any] | None = None) -> pl.DataFrame:
        """Execute SELECT query, return Polars DataFrame."""
        ...

    def execute(self, sql: str, params: list[Any] | None = None) -> None:
        """Execute non-SELECT statement (DDL, INSERT, UPDATE, DELETE)."""
        ...

    def executemany(self, sql: str, rows: list[tuple]) -> None:
        """Execute statement for multiple rows."""
        ...

    def upsert(
        self,
        table: str,
        columns: list[str],
        rows: list[tuple],
        conflict_columns: list[str],
    ) -> None:
        """Insert or update rows on conflict."""
        ...

    def close(self) -> None:
        """Close connection."""
        ...
