"""cquant.knowledge_base.ingest.orchestrator — Loader selection and ingest pipeline."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from cquant.core.errors import IngestError
from cquant.knowledge_base.ingest.base import DocumentLoader
from cquant.knowledge_base.ingest.markdown_loader import MarkdownLoader
from cquant.knowledge_base.ingest.pdf_loader import PDFLoader
from cquant.knowledge_base.ingest.tabular_loader import TabularLoader
from cquant.knowledge_base.ingest.url_loader import URLLoader
from cquant.knowledge_base.schemas.document import IngestRequest, IngestResult

if TYPE_CHECKING:
    from cquant.knowledge_base.process.chunking import TextChunker
    from cquant.knowledge_base.process.embedder import EmbeddingProvider
    from cquant.knowledge_base.store.catalog import KBCatalog
    from cquant.knowledge_base.store.vector_base import VectorStore, VectorRow

logger = logging.getLogger(__name__)


class IngestOrchestrator:
    """Selects the right loader, runs the ingest pipeline, and persists results.

    Pipeline:
    1. Select loader by URI / mime_type
    2. Load document → LoadedDocument
    3. Check for duplicates (content_hash)
    4. Register in DuckDB catalog
    5. Chunk text
    6. Embed chunks (if embedder configured)
    7. Upsert into LanceDB
    8. Write pointer under by_type/
    """

    def __init__(
        self,
        catalog: "KBCatalog",
        vector_store: "VectorStore",
        chunker: "TextChunker",
        embedder: "EmbeddingProvider",
        loaders: list[DocumentLoader] | None = None,
    ) -> None:
        self._catalog = catalog
        self._vector = vector_store
        self._chunker = chunker
        self._embedder = embedder
        self._loaders: list[DocumentLoader] = loaders or [
            PDFLoader(), URLLoader(), MarkdownLoader(), TabularLoader()
        ]

    def ingest(self, request: IngestRequest) -> IngestResult:
        """Run the full ingest pipeline for one document."""
        run_id = str(uuid.uuid4())
        loader = self._select_loader(request.uri)

        try:
            doc = loader.load(request)
        except Exception as exc:
            logger.error("Ingest failed for %s: %s", request.uri, exc)
            self._catalog.register_ingest_run(
                run_id, loader.source_type, request.uri, "", "error", str(exc)
            )
            return IngestResult(doc_id="", version_id="", run_id=run_id,
                                status="error", error=str(exc))

        # Duplicate check
        if self._catalog.doc_exists(doc.meta.content_hash):
            logger.info("Document already exists (duplicate): %s", doc.doc_id)
            self._catalog.register_ingest_run(
                run_id, loader.source_type, request.uri, doc.meta.content_hash, "ok"
            )
            return IngestResult(doc_id=doc.doc_id, version_id="", run_id=run_id,
                                status="duplicate")

        # Register in catalog
        version_id = self._catalog.register_document(doc.meta)
        self._catalog.register_ingest_run(
            run_id, loader.source_type, request.uri, doc.meta.content_hash, "ok"
        )

        # Chunk + embed
        chunks = self._chunker.chunk(doc.doc_id, doc.text)
        chunk_count = len(chunks)
        if chunks:
            self._embed_and_store(chunks)

        return IngestResult(
            doc_id=doc.doc_id,
            version_id=version_id,
            run_id=run_id,
            status="ok",
            chunk_count=chunk_count,
        )

    def _select_loader(self, uri: str) -> DocumentLoader:
        for loader in self._loaders:
            if loader.can_load(uri):
                return loader
        raise IngestError(
            f"No loader found for URI: {uri!r}. "
            "Supported: .pdf, .md, .txt, .csv, .xlsx, http://, https://"
        )

    def _embed_and_store(self, chunks) -> None:  # type: ignore[no-untyped-def]
        from cquant.knowledge_base.store.vector_base import VectorRow
        texts = [c.text for c in chunks]
        try:
            embeddings = self._embedder.embed(texts)
        except Exception as exc:
            logger.warning("Embedding failed, skipping vector store: %s", exc)
            return

        rows = [
            VectorRow(
                vector_key=c.chunk_id,
                doc_id=c.doc_id,
                chunk_id=c.chunk_id,
                text=c.text,
                embedding=emb,
            )
            for c, emb in zip(chunks, embeddings)
        ]
        self._vector.upsert(rows)
