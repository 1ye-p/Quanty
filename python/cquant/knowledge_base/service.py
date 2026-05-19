"""cquant.knowledge_base.service — KnowledgeBaseService facade.

Single entry point for api_server and ai_advisor.
Composes: IngestOrchestrator + HybridSearch + KBCatalog.

Usage::

    from cquant.knowledge_base.service import KnowledgeBaseService

    kb = KnowledgeBaseService.create()                # uses defaults
    result = kb.ingest(IngestRequest(uri="report.pdf", logical_type="research"))
    response = kb.search(SearchQuery(text="茅台 动量因子", top_k=5))
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import polars as pl

from cquant.datahub.catalog import Catalog
from cquant.knowledge_base.ingest.orchestrator import IngestOrchestrator
from cquant.knowledge_base.process.chunking import TextChunker
from cquant.knowledge_base.process.embedder import EmbeddingProvider, NullEmbeddingProvider
from cquant.knowledge_base.schemas.document import IngestRequest, IngestResult
from cquant.knowledge_base.schemas.search import SearchQuery, SearchResponse
from cquant.knowledge_base.search.hybrid import HybridSearch
from cquant.knowledge_base.store.catalog import KBCatalog
from cquant.knowledge_base.store.vector_lance import LanceVectorStore

logger = logging.getLogger(__name__)


class KnowledgeBaseService:
    """Facade composing all knowledge base subsystems."""

    def __init__(
        self,
        catalog: KBCatalog,
        orchestrator: IngestOrchestrator,
        search: HybridSearch,
    ) -> None:
        self._catalog = catalog
        self._orchestrator = orchestrator
        self._search = search

    @classmethod
    def create(
        cls,
        db_path: str | Path = "data/catalog.duckdb",
        kb_root: str | Path = "knowledge",
        vector_path: str | Path = "knowledge/vector/lancedb",
        embedder: EmbeddingProvider | None = None,
        chunk_size: int = 512,
        chunk_overlap: int = 64,
    ) -> "KnowledgeBaseService":
        """Build a KnowledgeBaseService with sensible defaults."""
        raw_catalog = Catalog(db_path=db_path)
        raw_catalog.initialize()
        kb_catalog = KBCatalog(raw_catalog)

        vector_store = LanceVectorStore(db_path=vector_path)
        _embedder = embedder or NullEmbeddingProvider()
        chunker = TextChunker(chunk_size=chunk_size, overlap=chunk_overlap)

        orchestrator = IngestOrchestrator(
            catalog=kb_catalog,
            vector_store=vector_store,
            chunker=chunker,
            embedder=_embedder,
        )
        hybrid_search = HybridSearch(
            catalog=kb_catalog,
            vector_store=vector_store,
            embedder=_embedder,
        )
        return cls(catalog=kb_catalog, orchestrator=orchestrator, search=hybrid_search)

    # ── Ingest ─────────────────────────────────────────────────────────────────

    def ingest(self, request: IngestRequest) -> IngestResult:
        """Ingest one document into the knowledge base."""
        return self._orchestrator.ingest(request)

    def ingest_file(
        self,
        path: str | Path,
        logical_type: str = "research",
        **kwargs: Any,
    ) -> IngestResult:
        """Convenience wrapper for local file ingestion."""
        return self.ingest(IngestRequest(
            uri=str(path),
            logical_type=logical_type,  # type: ignore[arg-type]
            **kwargs,
        ))

    # ── Search ─────────────────────────────────────────────────────────────────

    def search(self, query: SearchQuery) -> SearchResponse:
        """Hybrid search across the knowledge base."""
        return self._search.search(query)

    def search_text(self, text: str, top_k: int = 10, **kwargs: Any) -> SearchResponse:
        """Convenience wrapper for text-only queries."""
        return self.search(SearchQuery(text=text, top_k=top_k, **kwargs))

    # ── Catalog queries ────────────────────────────────────────────────────────

    def get_document(self, doc_id: str) -> pl.DataFrame:
        return self._catalog.get_document(doc_id)

    def list_documents(
        self, logical_type: str | None = None, limit: int = 100
    ) -> pl.DataFrame:
        return self._catalog.list_documents(logical_type=logical_type, limit=limit)
