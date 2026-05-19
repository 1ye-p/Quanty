"""cquant.knowledge_base.process.embedder — Embedding provider abstraction.

The embedding_provider capability is intentionally left as an interface.
Concrete implementations are registered as plugins at startup via configs/plugins/.
The NullEmbeddingProvider is the default — it returns zero vectors so that
the knowledge base is usable for full-text search without requiring a model.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class EmbeddingProvider(ABC):
    """Abstract embedding model interface."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Unique model identifier for lineage tracking."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Output vector dimension."""

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding per text. Batch-friendly."""


class NullEmbeddingProvider(EmbeddingProvider):
    """No-op provider — returns zero vectors.

    Used when no embedding model is configured.
    Semantic search will return empty results; keyword search still works.
    """

    def __init__(self, dimension: int = 768) -> None:
        self._dim = dimension

    @property
    def model_name(self) -> str:
        return "null"

    @property
    def dimension(self) -> int:
        return self._dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        logger.debug("NullEmbeddingProvider: returning zero vectors for %d texts", len(texts))
        return [[0.0] * self._dim for _ in texts]


def get_embedding_provider(name: str = "null", **kwargs) -> EmbeddingProvider:
    """Factory function to create embedding providers.

    Args:
        name: Provider name ('null', 'openai')
        **kwargs: Provider-specific arguments

    Returns:
        EmbeddingProvider instance
    """
    if name == "openai":
        from cquant.knowledge_base.process.embedding_providers import OpenAIEmbeddingProvider
        return OpenAIEmbeddingProvider(**kwargs)

    if name == "null":
        return NullEmbeddingProvider(**kwargs)

    raise ValueError(f"Unknown embedding provider: {name}. Available: ['null', 'openai']")
