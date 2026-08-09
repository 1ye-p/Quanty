"""cquant.datahub.catalog — DuckDB-backed dataset catalog.

Manages dataset registration, version lineage, and SQL query access
over the Bronze / Silver / Gold layers.
"""

from __future__ import annotations

import hashlib
import logging
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterator

import polars as pl

from cquant.core.errors import CatalogError

if TYPE_CHECKING:
    from cquant.datahub.backend import CatalogBackend

logger = logging.getLogger(__name__)

_DDL_FILES = [
    "sql/duckdb/bronze.sql",
    "sql/duckdb/silver.sql",
    "sql/duckdb/news.sql",
    "sql/duckdb/analysis.sql",
    "sql/duckdb/gold.sql",
    "sql/duckdb/knowledge.sql",
    "sql/duckdb/meta.sql",
]


@contextmanager
def _observe_duckdb(operation: str) -> Iterator[None]:
    """Observe a DuckDB operation's latency into the Prometheus histogram.

    Best-effort: if ``prometheus_client`` or the metrics module is unavailable,
    or the histogram is disabled, this is a transparent no-op. Lives here in
    ``catalog.py`` (rather than the metrics route) to avoid importing the API
    layer from the data layer.
    """
    start = time.perf_counter()
    try:
        yield
    finally:
        try:
            from cquant.api_server.routes.metrics import (
                duckdb_query_duration_seconds,
            )

            if duckdb_query_duration_seconds is not None:
                duckdb_query_duration_seconds.labels(operation=operation).observe(
                    time.perf_counter() - start
                )
        except Exception:  # pragma: no cover — metrics are best-effort
            pass


class Catalog:
    """Database-agnostic catalog for the cQuant data lake.

    Usage::

        catalog = Catalog("data/catalog.duckdb")
        catalog.initialize()          # Run DDL on first use
        catalog.query("SELECT COUNT(*) FROM silver_prices_1d")
    """

    def __init__(
        self,
        db_path: str | Path = "data/catalog.duckdb",
        repo_root: str | Path | None = None,
        backend: CatalogBackend | None = None,
        read_only: bool = False,
    ) -> None:
        self._repo_root = Path(repo_root) if repo_root else Path.cwd()
        if backend is not None:
            self._backend: CatalogBackend = backend
            self._db_path = Path(db_path)
        else:
            self._db_path = Path(db_path)
            if not read_only:
                self._db_path.parent.mkdir(parents=True, exist_ok=True)
            from cquant.datahub.backends.duckdb_backend import DuckDBBackend

            self._backend = DuckDBBackend(str(self._db_path), read_only=read_only)

    def _get_conn(self):
        """Compatibility shim — returns the raw backend connection if available."""
        return getattr(self._backend, "_conn", None)

    def initialize(self) -> None:
        """Execute all DDL scripts to create tables if they do not exist."""
        for ddl_file in _DDL_FILES:
            path = self._repo_root / ddl_file
            if not path.exists():
                logger.warning("DDL file not found, skipping: %s", path)
                continue
            sql = path.read_text(encoding="utf-8")
            for stmt in _split_statements(sql):
                try:
                    self._backend.execute(stmt)
                except Exception as exc:
                    raise CatalogError(f"DDL failed in {ddl_file}: {exc}\n\n{stmt}") from exc
        logger.info("Catalog initialized at %s", self._db_path)

    def query(self, sql: str, params: list[Any] | None = None) -> pl.DataFrame:
        """Execute *sql* and return the result as a Polars DataFrame."""
        with _observe_duckdb("query"):
            try:
                return self._backend.query(sql, params)
            except CatalogError:
                raise
            except Exception as exc:
                raise CatalogError(f"Query failed: {exc}\n\nSQL: {sql}") from exc

    def execute(self, sql: str, params: list[Any] | None = None) -> None:
        """Execute a non-SELECT statement (INSERT, UPDATE, DELETE)."""
        with _observe_duckdb("execute"):
            try:
                self._backend.execute(sql, params)
            except CatalogError:
                raise
            except Exception as exc:
                raise CatalogError(f"Execute failed: {exc}\n\nSQL: {sql}") from exc

    def executemany(self, sql: str, rows: list[tuple]) -> None:
        """Execute statement for multiple rows."""
        with _observe_duckdb("executemany"):
            try:
                self._backend.executemany(sql, rows)
            except CatalogError:
                raise
            except Exception as exc:
                raise CatalogError(f"Executemany failed: {exc}\n\nSQL: {sql}") from exc

    def upsert(
        self,
        table: str,
        columns: list[str],
        rows: list[tuple],
        conflict_columns: list[str],
    ) -> None:
        """Insert or update rows on conflict."""
        try:
            self._backend.upsert(table, columns, rows, conflict_columns)
        except CatalogError:
            raise
        except Exception as exc:
            raise CatalogError(f"Upsert failed: {exc}\n\nTable: {table}") from exc

    def register_dataset(
        self,
        dataset_name: str,
        frequency: str,
        start_date: str,
        end_date: str,
        asset_count: int,
        row_count: int,
        storage_uri: str,
        source: str,
        data_for_hash: bytes | None = None,
    ) -> str:
        """Register a new dataset version and return the version_id."""
        version_id = str(uuid.uuid4())
        content_hash = hashlib.sha256(data_for_hash).hexdigest() if data_for_hash else ""
        now = datetime.now(tz=timezone.utc).isoformat()

        # Mark previous current version as non-current
        self.execute(
            """
            UPDATE silver_dataset_versions
            SET is_current = FALSE
            WHERE dataset_name = ? AND is_current = TRUE
            """,
            [dataset_name],
        )

        self.execute(
            """
            INSERT INTO silver_dataset_versions
                (version_id, dataset_name, frequency, start_date, end_date,
                 asset_count, row_count, storage_uri, content_hash, source, created_at, is_current)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, TRUE)
            """,
            [
                version_id, dataset_name, frequency, start_date, end_date,
                asset_count, row_count, storage_uri, content_hash, source, now,
            ],
        )
        return version_id

    def get_data_quality_summary(
        self, table: str = "silver_prices_1d"
    ) -> dict:
        """返回价格数据的质量诊断摘要。

        Parameters
        ----------
        table:
            要检查的表名，默认 ``"silver_prices_1d"``。

        Returns
        -------
        包含以下键的字典：

        - ``total_rows``: 总行数
        - ``asset_count``: 资产数量
        - ``date_range``: ``{"start": date, "end": date}``
        - ``zero_close_count``: close <= 0 的异常行数
        - ``suspended_count``: 停牌行数
        """
        try:
            stats = self.query(f"""
                SELECT
                    COUNT(*) AS total_rows,
                    COUNT(DISTINCT asset_id) AS asset_count,
                    MIN(trade_date) AS start_date,
                    MAX(trade_date) AS end_date,
                    SUM(CASE WHEN close <= 0 THEN 1 ELSE 0 END) AS zero_close_count,
                    SUM(CASE WHEN is_suspended THEN 1 ELSE 0 END) AS suspended_count
                FROM {table}
            """)
        except Exception:
            return {
                "total_rows": 0,
                "asset_count": 0,
                "date_range": {"start": None, "end": None},
                "zero_close_count": 0,
                "suspended_count": 0,
            }

        if stats.is_empty():
            return {
                "total_rows": 0,
                "asset_count": 0,
                "date_range": {"start": None, "end": None},
                "zero_close_count": 0,
                "suspended_count": 0,
            }

        row = stats.row(0, named=True)
        return {
            "total_rows": int(row["total_rows"] or 0),
            "asset_count": int(row["asset_count"] or 0),
            "date_range": {
                "start": row["start_date"],
                "end": row["end_date"],
            },
            "zero_close_count": int(row["zero_close_count"] or 0),
            "suspended_count": int(row["suspended_count"] or 0),
        }

    # ------------------------------------------------------------------
    # Factor descriptions
    # ------------------------------------------------------------------

    _CREATE_FACTOR_DESCRIPTIONS = """\
CREATE TABLE IF NOT EXISTS meta_factor_descriptions (
    factor_name         VARCHAR PRIMARY KEY,
    description         TEXT,
    category            VARCHAR,
    formula             TEXT,
    data_source         VARCHAR,
    lookback_days       INTEGER,
    notes               TEXT,
    created_at          TIMESTAMPTZ NOT NULL,
    updated_at          TIMESTAMPTZ NOT NULL
);"""

    def write_meta_factor_descriptions(self, df: pl.DataFrame) -> int:
        """Upsert factor descriptions into ``meta_factor_descriptions``.

        Creates the table on first call.  Expects *df* to contain at least a
        ``factor_name`` column.  Missing optional columns are filled with
        ``None`` / current timestamp.

        Returns the number of rows written.
        """
        if df.is_empty():
            return 0

        self.execute(self._CREATE_FACTOR_DESCRIPTIONS)

        now = datetime.now(tz=timezone.utc).isoformat()
        df = df.with_columns(
            pl.col("created_at").fill_null(pl.lit(now)) if "created_at" in df.columns else pl.lit(now).alias("created_at"),
            pl.col("updated_at").fill_null(pl.lit(now)) if "updated_at" in df.columns else pl.lit(now).alias("updated_at"),
        )

        columns = df.columns
        rows = [tuple(row) for row in df.iter_rows()]
        conflict_cols = ["factor_name"]
        self.upsert("meta_factor_descriptions", columns, rows, conflict_cols)
        return len(rows)

    def read_meta_factor_descriptions(
        self, factor_names: list[str] | None = None
    ) -> pl.DataFrame:
        """Read factor descriptions.

        If *factor_names* is provided, returns only matching rows.  Otherwise
        returns all rows.
        """
        if factor_names:
            placeholders = ", ".join(["?"] * len(factor_names))
            return self.query(
                f"SELECT * FROM meta_factor_descriptions WHERE factor_name IN ({placeholders})",
                factor_names,
            )
        return self.query("SELECT * FROM meta_factor_descriptions")

    # ------------------------------------------------------------------
    # Model registry
    # ------------------------------------------------------------------

    _CREATE_MODEL_REGISTRY = """\
CREATE TABLE IF NOT EXISTS meta_model_registry (
    model_name          VARCHAR PRIMARY KEY,
    model_type          VARCHAR NOT NULL,
    framework           VARCHAR,
    version             VARCHAR,
    params_json         JSON,
    metrics_json        JSON,
    artifact_path       VARCHAR,
    status              VARCHAR DEFAULT 'registered',
    description         TEXT,
    created_at          TIMESTAMPTZ NOT NULL,
    updated_at          TIMESTAMPTZ NOT NULL
);"""

    def write_meta_model_registry(self, df: pl.DataFrame) -> int:
        """Upsert model entries into ``meta_model_registry``.

        Creates the table on first call.  Expects *df* to contain at least
        ``model_name`` and ``model_type`` columns.

        Returns the number of rows written.
        """
        if df.is_empty():
            return 0

        self.execute(self._CREATE_MODEL_REGISTRY)

        now = datetime.now(tz=timezone.utc).isoformat()
        df = df.with_columns(
            pl.col("created_at").fill_null(pl.lit(now)) if "created_at" in df.columns else pl.lit(now).alias("created_at"),
            pl.col("updated_at").fill_null(pl.lit(now)) if "updated_at" in df.columns else pl.lit(now).alias("updated_at"),
        )

        columns = df.columns
        rows = [tuple(row) for row in df.iter_rows()]
        conflict_cols = ["model_name"]
        self.upsert("meta_model_registry", columns, rows, conflict_cols)
        return len(rows)

    def read_meta_model_registry(self) -> pl.DataFrame:
        """Read all entries from the model registry."""
        return self.query("SELECT * FROM meta_model_registry")

    def close(self) -> None:
        self._backend.close()

    def __enter__(self) -> "Catalog":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()


def _split_statements(sql: str) -> list[str]:
    """Split a SQL string into individual statements.

    Strips single-line (--) comments and dot-commands (.read) before splitting
    on semicolons, so that comment text never ends up in an executed statement.
    """
    import re
    # Remove single-line comments (-- ...) and dot-commands (.foo)
    no_comments = re.sub(r"(--[^\n]*)", "", sql)
    no_comments = re.sub(r"^\s*\.[^\n]*$", "", no_comments, flags=re.MULTILINE)

    statements = []
    for raw in no_comments.split(";"):
        stmt = raw.strip()
        if stmt:
            statements.append(stmt + ";")
    return statements


def create_catalog() -> Catalog:
    """Create catalog from environment configuration."""
    import os

    backend_type = os.environ.get("CQUANT_DB_BACKEND", "duckdb")
    if backend_type == "postgresql":
        dsn = os.environ["CQUANT_PG_DSN"]
        from cquant.datahub.backends.postgres_backend import PostgresBackend

        return Catalog(backend=PostgresBackend(dsn))
    else:
        db_path = os.environ.get("CQUANT_DB_PATH", "data/catalog.duckdb")
        return Catalog(db_path=db_path)
