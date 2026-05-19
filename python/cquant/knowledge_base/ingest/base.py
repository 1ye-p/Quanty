"""cquant.knowledge_base.ingest.base — DocumentLoader ABC."""

from __future__ import annotations

from abc import ABC, abstractmethod

from cquant.knowledge_base.schemas.document import IngestRequest, LoadedDocument


class DocumentLoader(ABC):
    """Abstract base for all document loaders."""

    @property
    @abstractmethod
    def source_type(self) -> str:
        """Stable identifier: 'pdf' | 'url' | 'markdown' | 'tabular'."""

    @abstractmethod
    def can_load(self, uri: str, mime_type: str | None = None) -> bool:
        """Return True if this loader handles *uri*."""

    @abstractmethod
    def load(self, request: IngestRequest) -> LoadedDocument:
        """Load *request.uri* and return a LoadedDocument with extracted text."""
