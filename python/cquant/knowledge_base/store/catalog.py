"""cquant.knowledge_base.store.catalog — DuckDB kb_* metadata adapter."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import polars as pl

from cquant.datahub.catalog import Catalog
from cquant.knowledge_base.schemas.document import DocumentMeta, IngestResult


class KBCatalog:
    """Read/write interface for the kb_* DuckDB tables.

    Wraps the shared Catalog instance so that knowledge_base operations
    use the same DuckDB connection as the rest of the data lake.
    """

    def __init__(self, catalog: Catalog) -> None:
        self._cat = catalog

    def ensure_tables(self) -> None:
        """Initialize kb_* DDL (idempotent)."""
        self._cat.initialize()

    def doc_exists(self, content_hash: str) -> bool:
        """Return True if a document with this content_hash is already stored."""
        df = self._cat.query(
            "SELECT COUNT(*) AS n FROM kb_documents WHERE content_hash = ?",
            [content_hash],
        )
        return int(df["n"].item()) > 0

    def register_document(self, meta: DocumentMeta) -> str:
        """Insert a new document row. Returns version_id."""
        version_id = str(uuid.uuid4())
        now = datetime.now(tz=timezone.utc).isoformat()

        self._cat.execute(
            """
            INSERT INTO kb_documents
                (doc_id, logical_type, source_type, title, source_name, canonical_url,
                 language, content_hash, raw_path, current_version_id, status,
                 ingested_at, published_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
            """,
            [
                meta.doc_id, meta.logical_type, meta.source_type,
                meta.title, meta.source_name, meta.canonical_url or "",
                meta.language, meta.content_hash, "",
                version_id, now,
                meta.published_at.isoformat() if meta.published_at else None,
            ],
        )

        self._cat.execute(
            """
            INSERT INTO kb_document_versions
                (version_id, doc_id, extracted_text_path, parser_name, is_current, created_at)
            VALUES (?, ?, '', 'text_extractor', TRUE, ?)
            """,
            [version_id, meta.doc_id, now],
        )
        return version_id

    def register_ingest_run(
        self,
        run_id: str,
        loader_type: str,
        input_uri: str,
        input_hash: str,
        status: str,
        error_text: str = "",
    ) -> None:
        now = datetime.now(tz=timezone.utc).isoformat()
        self._cat.execute(
            """
            INSERT INTO kb_ingest_runs
                (run_id, loader_type, input_uri, input_hash, status, error_text,
                 started_at, finished_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [run_id, loader_type, input_uri, input_hash, status, error_text, now, now],
        )

    def search_fulltext(self, query: str, top_k: int = 10) -> pl.DataFrame:
        """Simple LIKE-based full-text search over kb_documents (MVP fallback)."""
        pattern = f"%{query}%"
        return self._cat.query(
            """
            SELECT doc_id, title, source_name, logical_type, language, ingested_at
            FROM kb_documents
            WHERE status = 'active'
              AND (title LIKE ? OR source_name LIKE ?)
            ORDER BY ingested_at DESC
            LIMIT ?
            """,
            [pattern, pattern, top_k],
        )

    def get_document(self, doc_id: str) -> pl.DataFrame:
        return self._cat.query(
            "SELECT * FROM kb_documents WHERE doc_id = ?",
            [doc_id],
        )

    def list_documents(
        self,
        logical_type: str | None = None,
        limit: int = 100,
    ) -> pl.DataFrame:
        if logical_type:
            return self._cat.query(
                "SELECT doc_id, title, source_name, logical_type, ingested_at "
                "FROM kb_documents WHERE status = 'active' AND logical_type = ? "
                "ORDER BY ingested_at DESC LIMIT ?",
                [logical_type, limit],
            )
        return self._cat.query(
            "SELECT doc_id, title, source_name, logical_type, ingested_at "
            "FROM kb_documents WHERE status = 'active' "
            "ORDER BY ingested_at DESC LIMIT ?",
            [limit],
        )

    def log_search(
        self,
        query_text: str,
        query_type: str,
        result_count: int,
        latency_ms: int,
        session_id: str = "",
        filters_json: Any = None,
        top_k: int = 10,
    ) -> None:
        import json as _json
        self._cat.execute(
            """
            INSERT INTO kb_search_history
                (query_id, session_id, query_text, query_type, filters_json,
                 top_k, latency_ms, result_count, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                str(uuid.uuid4()), session_id, query_text, query_type,
                _json.dumps(filters_json or {}), top_k, latency_ms,
                result_count, datetime.now(tz=timezone.utc).isoformat(),
            ],
        )
