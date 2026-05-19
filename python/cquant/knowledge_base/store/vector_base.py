"""cquant.knowledge_base.store.vector_base — VectorStore ABC."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class VectorRow:
    """One chunk to upsert into the vector store."""

    vector_key: str      # Unique ID (typically doc_id + chunk_index)
    doc_id: str
    chunk_id: str
    text: str
    embedding: list[float]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class VectorHit:
    """One result from a similarity search."""

    vector_key: str
    doc_id: str
    chunk_id: str
    score: float
    text: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class VectorQuery:
    """A similarity search request."""

    embedding: list[float]
    top_k: int = 10
    filter_doc_ids: list[str] = field(default_factory=list)


class VectorStore(ABC):
    """Abstract base for vector stores (LanceDB, ChromaDB, etc.)."""

    @property
    @abstractmethod
    def backend(self) -> str:
        """e.g. 'lancedb' | 'chroma'"""

    @abstractmethod
    def upsert(self, rows: list[VectorRow]) -> None:
        """Insert or update chunks in the store."""

    @abstractmethod
    def search(self, query: VectorQuery) -> list[VectorHit]:
        """Return top-k nearest neighbours."""

    @abstractmethod
    def delete_document(self, doc_id: str) -> None:
        """Remove all chunks belonging to *doc_id*."""

    def similar_to_document(self, doc_id: str, top_k: int = 10) -> list[VectorHit]:
        """Return documents most similar to *doc_id* (via centroid search)."""
        raise NotImplementedError
