"""cquant.knowledge_base — Financial knowledge base with RAG support.

Usage::

    from cquant.knowledge_base import KnowledgeBaseService, IngestRequest, SearchQuery

    kb = KnowledgeBaseService.create()
    kb.ingest(IngestRequest(uri="research/report.pdf", source_name="Goldman Sachs"))
    results = kb.search(SearchQuery(text="AI stocks momentum"))
"""

from cquant.knowledge_base.service import KnowledgeBaseService
from cquant.knowledge_base.schemas.document import IngestRequest, IngestResult, LoadedDocument
from cquant.knowledge_base.schemas.search import SearchQuery, SearchResponse, SearchHit
from cquant.knowledge_base.process.embedder import EmbeddingProvider, NullEmbeddingProvider

__all__ = [
    "KnowledgeBaseService",
    "IngestRequest",
    "IngestResult",
    "LoadedDocument",
    "SearchQuery",
    "SearchResponse",
    "SearchHit",
    "EmbeddingProvider",
    "NullEmbeddingProvider",
]
