"""cquant.knowledge_base.search.hybrid — Hybrid search: keyword + semantic fusion.

Score fusion: hybrid_score = keyword_weight * keyword_score + semantic_weight * semantic_score

Default weights from plan v3: semantic 45%, keyword 35%, graph 20%.
For MVP the graph component is omitted (graph_weight absorbed by keyword).
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from cquant.knowledge_base.schemas.search import SearchHit, SearchQuery, SearchResponse
from cquant.knowledge_base.store.catalog import KBCatalog
from cquant.knowledge_base.store.vector_base import VectorQuery, VectorStore

if TYPE_CHECKING:
    from cquant.knowledge_base.process.embedder import EmbeddingProvider


class HybridSearch:
    """Fuse keyword (DuckDB) and semantic (LanceDB) results.

    When the embedding provider is NullEmbeddingProvider, falls back to
    keyword-only search transparently.
    """

    def __init__(
        self,
        catalog: KBCatalog,
        vector_store: VectorStore,
        embedder: "EmbeddingProvider",
    ) -> None:
        self._catalog = catalog
        self._vector = vector_store
        self._embedder = embedder

    def search(self, query: SearchQuery) -> SearchResponse:
        t0 = time.monotonic()

        keyword_hits = self._keyword_search(query)
        semantic_hits = self._semantic_search(query)
        merged = self._fuse(keyword_hits, semantic_hits, query)

        latency_ms = int((time.monotonic() - t0) * 1000)
        self._catalog.log_search(
            query_text=query.text,
            query_type=query.mode,
            result_count=len(merged),
            latency_ms=latency_ms,
            session_id=query.session_id,
            top_k=query.top_k,
        )
        return SearchResponse(query=query, hits=merged, total_found=len(merged), latency_ms=latency_ms)

    def _keyword_search(self, query: SearchQuery) -> list[SearchHit]:
        df = self._catalog.search_fulltext(query.text, top_k=query.top_k * 2)
        if df.is_empty():
            return []
        hits = []
        for row in df.iter_rows(named=True):
            hits.append(SearchHit(
                doc_id=row["doc_id"],
                score=1.0,   # All keyword hits get equal score before fusion
                title=row.get("title", ""),
                source_name=row.get("source_name", ""),
                logical_type=row.get("logical_type", ""),
                published_at=str(row.get("ingested_at", "")),
            ))
        return hits

    def _semantic_search(self, query: SearchQuery) -> list[SearchHit]:
        from cquant.knowledge_base.process.embedder import NullEmbeddingProvider
        if isinstance(self._embedder, NullEmbeddingProvider):
            return []   # No-op when embedder not configured

        try:
            embeddings = self._embedder.embed([query.text])
            vq = VectorQuery(embedding=embeddings[0], top_k=query.top_k * 2)
            vector_hits = self._vector.search(vq)
            return [
                SearchHit(
                    doc_id=h.doc_id,
                    chunk_id=h.chunk_id,
                    score=1.0 - h.score,   # LanceDB returns distance; convert to similarity
                    headline=h.text[:200],
                )
                for h in vector_hits
            ]
        except Exception:
            return []

    def _fuse(
        self,
        keyword: list[SearchHit],
        semantic: list[SearchHit],
        query: SearchQuery,
    ) -> list[SearchHit]:
        """Reciprocal Rank Fusion (RRF) weighted by mode."""
        scores: dict[str, float] = {}
        meta: dict[str, SearchHit] = {}

        # Keyword contribution
        for rank, hit in enumerate(keyword, start=1):
            key = hit.doc_id
            scores[key] = scores.get(key, 0.0) + query.keyword_weight / (60 + rank)
            meta.setdefault(key, hit)

        # Semantic contribution
        for rank, hit in enumerate(semantic, start=1):
            key = hit.doc_id
            scores[key] = scores.get(key, 0.0) + query.semantic_weight / (60 + rank)
            if key not in meta:
                meta[key] = hit
            elif hit.headline:
                meta[key].headline = hit.headline

        sorted_keys = sorted(scores, key=lambda k: scores[k], reverse=True)[:query.top_k]
        result = []
        for k in sorted_keys:
            h = meta[k]
            h.score = round(scores[k], 6)
            result.append(h)
        return result
