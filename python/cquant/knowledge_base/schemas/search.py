"""cquant.knowledge_base.schemas.search — Search query and result models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class SearchQuery:
    """A unified search request across keyword, semantic, and graph modes."""

    text: str
    mode: Literal["hybrid", "semantic", "keyword", "graph"] = "hybrid"
    top_k: int = 10
    # Filters
    logical_type: str | None = None          # 'research' | 'strategy' | 'notes' | 'data'
    source_name: str | None = None
    language: str | None = None
    published_after: str | None = None       # ISO date string
    published_before: str | None = None
    tickers: list[str] = field(default_factory=list)
    industries: list[str] = field(default_factory=list)
    # Search weights (sum should be 1.0)
    semantic_weight: float = 0.45
    keyword_weight: float = 0.35
    graph_weight: float = 0.20
    session_id: str = ""


@dataclass
class SearchHit:
    """A single search result."""

    doc_id: str
    chunk_id: str = ""
    score: float = 0.0
    title: str = ""
    source_name: str = ""
    logical_type: str = ""
    headline: str = ""                   # First ~200 chars of chunk text
    published_at: str = ""
    matched_entities: list[str] = field(default_factory=list)


@dataclass
class SearchResponse:
    """Results of a search query."""

    query: SearchQuery
    hits: list[SearchHit]
    total_found: int = 0
    latency_ms: int = 0
