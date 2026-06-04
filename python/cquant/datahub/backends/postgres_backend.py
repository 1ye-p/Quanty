"""PostgreSQL backend for QuantDB compatibility.

Reference: QuantAgent/agent/backtest/loaders/quantdb.py
Pattern: Short-lived psycopg v3 connections, no pool.
"""
from __future__ import annotations

import logging
from typing import Any

import polars as pl

logger = logging.getLogger(__name__)

_DEFAULT_CONNECT_TIMEOUT = 2
_DEFAULT_STATEMENT_TIMEOUT_MS = 10000


class PostgresBackend:
    """PostgreSQL database backend using psycopg v3."""

    def __init__(
        self,
        dsn: str,
        connect_timeout: int = _DEFAULT_CONNECT_TIMEOUT,
        statement_timeout_ms: int = _DEFAULT_STATEMENT_TIMEOUT_MS,
    ) -> None:
        self._dsn = dsn
        self._connect_timeout = connect_timeout
        self._statement_timeout_ms = statement_timeout_ms
        self._conn = None
        logger.info("PostgreSQL backend initialized")

    def _get_conn(self):
        """Get or create short-lived connection."""
        import psycopg
        if self._conn is not None and not self._conn.closed:
            # Reset stale transaction state from prior errors
            try:
                self._conn.execute("SELECT 1")
            except Exception:
                self._conn.rollback()
        if self._conn is None or self._conn.closed:
            self._conn = psycopg.connect(
                self._dsn,
                connect_timeout=self._connect_timeout,
                options=f"-c statement_timeout={self._statement_timeout_ms}",
            )
        return self._conn

    def query(self, sql: str, params: list[Any] | None = None) -> pl.DataFrame:
        sql = _convert_placeholders(sql)
        cur = self._get_conn().cursor()
        cur.execute(sql, params or [])
        if cur.description is None:
            return pl.DataFrame()
        cols = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        return pl.DataFrame(rows, schema=cols, orient="row") if rows else pl.DataFrame(schema=cols)

    def execute(self, sql: str, params: list[Any] | None = None) -> None:
        sql = _convert_placeholders(sql)
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(sql, params or [])
        conn.commit()

    def executemany(self, sql: str, rows: list[tuple]) -> None:
        sql = _convert_placeholders(sql)
        conn = self._get_conn()
        cur = conn.cursor()
        cur.executemany(sql, rows)
        conn.commit()

    def upsert(
        self,
        table: str,
        columns: list[str],
        rows: list[tuple],
        conflict_columns: list[str],
    ) -> None:
        cols = ", ".join(columns)
        placeholders = ", ".join(["%s"] * len(columns))
        conflict = ", ".join(conflict_columns)
        update_cols = [c for c in columns if c not in conflict_columns]
        if update_cols:
            update_set = ", ".join(f"{c} = EXCLUDED.{c}" for c in update_cols)
            sql = f"INSERT INTO {table} ({cols}) VALUES ({placeholders}) ON CONFLICT ({conflict}) DO UPDATE SET {update_set}"
        else:
            sql = f"INSERT INTO {table} ({cols}) VALUES ({placeholders}) ON CONFLICT ({conflict}) DO NOTHING"
        cur = self._get_conn().cursor()
        cur.executemany(sql, rows)

    def close(self) -> None:
        if self._conn and not self._conn.closed:
            self._conn.close()


def _convert_placeholders(sql: str) -> str:
    """Convert ? placeholders to %s for psycopg."""
    return sql.replace("?", "%s")
