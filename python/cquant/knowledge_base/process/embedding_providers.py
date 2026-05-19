"""Concrete embedding providers for the knowledge base.

Supports OpenAI embedding APIs.
Configure via configs/defaults/knowledge_base.toml [embedding] section.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from cquant.knowledge_base.process.embedder import EmbeddingProvider

logger = logging.getLogger(__name__)


def _openai() -> Any:
    try:
        import openai
        return openai
    except ImportError as exc:
        raise ImportError(
            "openai is required for OpenAIEmbeddingProvider. "
            "Install with: pip install openai"
        ) from exc


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI embedding provider using text-embedding-3-small.

    Usage::

        provider = OpenAIEmbeddingProvider()
        vectors = provider.embed(["hello world", "quantitative finance"])
    """

    def __init__(
        self,
        model: str = "text-embedding-3-small",
        api_key: str | None = None,
    ) -> None:
        self._model = model
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        if not self._api_key:
            logger.warning("No OPENAI_API_KEY set; embed() will fail at runtime")
        self._client = None

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def dimension(self) -> int:
        dims = {
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "text-embedding-ada-002": 1536,
        }
        return dims.get(self._model, 1536)

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if self._client is None:
            openai = _openai()
            self._client = openai.OpenAI(api_key=self._api_key)
        resp = self._client.embeddings.create(input=texts, model=self._model)
        return [d.embedding for d in resp.data]
