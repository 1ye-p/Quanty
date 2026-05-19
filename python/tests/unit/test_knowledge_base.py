"""Unit tests for knowledge_base module.

Tests embedding providers, text chunker, catalog, and hybrid search.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from cquant.knowledge_base.process.embedder import EmbeddingProvider, NullEmbeddingProvider, get_embedding_provider
from cquant.knowledge_base.process.chunking import TextChunker
from cquant.knowledge_base.schemas.search import SearchHit, SearchQuery, SearchResponse
from cquant.knowledge_base.store.catalog import KBCatalog


# ── Embedding Provider Tests ──────────────────────────────────────────────────

class TestEmbeddingProviders:
    def test_null_provider_returns_zero_vectors(self):
        provider = NullEmbeddingProvider(dimension=768)
        result = provider.embed(["hello", "world"])
        assert len(result) == 2
        assert len(result[0]) == 768
        assert all(v == 0.0 for v in result[0])

    def test_null_provider_model_name(self):
        provider = NullEmbeddingProvider()
        assert provider.model_name == "null"

    def test_null_provider_default_dimension(self):
        provider = NullEmbeddingProvider()
        assert provider.dimension == 768

    @patch("cquant.knowledge_base.process.embedding_providers._openai")
    def test_openai_provider_embed(self, mock_openai_fn):
        from cquant.knowledge_base.process.embedding_providers import OpenAIEmbeddingProvider

        mock_openai = MagicMock()
        mock_openai_fn.return_value = mock_openai
        mock_client = MagicMock()
        mock_openai.OpenAI.return_value = mock_client
        mock_client.embeddings.create.return_value = MagicMock(
            data=[MagicMock(embedding=[0.1] * 1536)]
        )

        provider = OpenAIEmbeddingProvider(api_key="fake-key")
        result = provider.embed(["test text"])

        assert len(result) == 1
        assert len(result[0]) == 1536
        assert result[0][0] == 0.1
        mock_client.embeddings.create.assert_called_once()

    def test_openai_provider_dimension(self):
        from cquant.knowledge_base.process.embedding_providers import OpenAIEmbeddingProvider

        provider = OpenAIEmbeddingProvider(api_key="fake-key")
        assert provider.dimension == 1536
        assert provider.model_name == "text-embedding-3-small"

    def test_openai_provider_empty_texts(self):
        from cquant.knowledge_base.process.embedding_providers import OpenAIEmbeddingProvider

        provider = OpenAIEmbeddingProvider(api_key="fake-key")
        result = provider.embed([])
        assert result == []


# ── Factory Tests ─────────────────────────────────────────────────────────────

class TestGetEmbeddingProvider:
    def test_null_provider(self):
        provider = get_embedding_provider("null")
        assert isinstance(provider, NullEmbeddingProvider)

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown embedding provider"):
            get_embedding_provider("nonexistent")

    def test_openai_provider(self):
        provider = get_embedding_provider("openai", api_key="fake-key")
        from cquant.knowledge_base.process.embedding_providers import OpenAIEmbeddingProvider
        assert isinstance(provider, OpenAIEmbeddingProvider)


# ── TextChunker Tests ─────────────────────────────────────────────────────────

class TestTextChunker:
    def test_chunk_short_text(self):
        chunker = TextChunker(chunk_size=1000, overlap=100)
        text = "This is a short document."
        chunks = chunker.chunk("doc1", text)
        assert len(chunks) == 1
        assert chunks[0].text == text

    def test_chunk_long_text(self):
        chunker = TextChunker(chunk_size=100, overlap=20)
        text = "word " * 100  # 500 chars
        chunks = chunker.chunk("doc1", text)
        assert len(chunks) > 1

    def test_chunk_multiple_sentences(self):
        chunker = TextChunker(chunk_size=50, overlap=10)
        text = "Sentence one. " * 20  # Multiple sentences
        chunks = chunker.chunk("doc1", text)
        assert len(chunks) > 1

    def test_chunk_preserves_doc_id(self):
        chunker = TextChunker(chunk_size=50, overlap=10)
        text = "a" * 200
        chunks = chunker.chunk("my-doc", text)
        for chunk in chunks:
            assert chunk.doc_id == "my-doc"

    def test_chunk_has_indices(self):
        chunker = TextChunker(chunk_size=50, overlap=10)
        text = "a" * 200
        chunks = chunker.chunk("doc1", text)
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i


# ── KBCatalog Tests ───────────────────────────────────────────────────────────

class TestKBCatalog:
    def test_search_fulltext_uses_like(self):
        mock_catalog = MagicMock()
        mock_catalog.query.return_value = MagicMock(is_empty=lambda: True)

        kb_catalog = KBCatalog(mock_catalog)
        kb_catalog.search_fulltext("test query", top_k=5)

        call_args = mock_catalog.query.call_args
        query_str = call_args[0][0]
        params = call_args[0][1]

        assert "LIKE" in query_str
        assert "%test query%" in params

    def test_doc_exists_returns_true(self):
        mock_catalog = MagicMock()
        mock_df = MagicMock()
        mock_df.__getitem__ = lambda self, key: MagicMock(item=lambda: 1)
        mock_catalog.query.return_value = mock_df
        kb_catalog = KBCatalog(mock_catalog)
        assert kb_catalog.doc_exists("abc123") is True

    def test_doc_exists_returns_false(self):
        mock_catalog = MagicMock()
        mock_df = MagicMock()
        mock_df.__getitem__ = lambda self, key: MagicMock(item=lambda: 0)
        mock_catalog.query.return_value = mock_df
        kb_catalog = KBCatalog(mock_catalog)
        assert kb_catalog.doc_exists("abc123") is False


# ── HybridSearch Tests ────────────────────────────────────────────────────────

class TestHybridSearch:
    def test_fusion_merges_results(self):
        from cquant.knowledge_base.search.hybrid import HybridSearch

        keyword_hits = [
            SearchHit(doc_id="doc1", chunk_id="c1", score=1.0),
            SearchHit(doc_id="doc2", chunk_id="c2", score=1.0),
        ]
        semantic_hits = [
            SearchHit(doc_id="doc2", chunk_id="c2", score=0.9),
            SearchHit(doc_id="doc3", chunk_id="c3", score=0.8),
        ]

        query = SearchQuery(
            text="test",
            top_k=10,
            keyword_weight=0.5,
            semantic_weight=0.5,
        )

        search = HybridSearch.__new__(HybridSearch)
        merged = search._fuse(keyword_hits, semantic_hits, query)

        # doc2 should rank highest (appears in both)
        assert merged[0].doc_id == "doc2"
        assert len(merged) == 3
