"""Knowledge-base routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from cquant.api_server.deps import CatalogDep, KBServiceDep
from cquant.api_server.schemas.knowledge import (
    IngestRequestBody,
    IngestResponseBody,
    SearchHitBody,
    SearchRequestBody,
    SearchResponseBody,
)
from cquant.knowledge_base import IngestRequest, SearchQuery

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.post("/ingest", response_model=IngestResponseBody)
async def ingest_document(body: IngestRequestBody, kb: KBServiceDep) -> IngestResponseBody:
    """Ingest a document (PDF, URL, Markdown, or CSV) into the knowledge base."""
    result = kb.ingest(
        IngestRequest(
            uri=body.uri,
            logical_type=body.logical_type,
            source_name=body.source_name,
            title=body.title,
            language=body.language,
        )
    )
    return IngestResponseBody(
        doc_id=result.doc_id,
        status=result.status,
        chunk_count=result.chunk_count,
        run_id=result.run_id,
        error=result.error,
    )


@router.post("/search", response_model=SearchResponseBody)
async def search_knowledge(body: SearchRequestBody, kb: KBServiceDep) -> SearchResponseBody:
    """Hybrid search across the knowledge base."""
    response = kb.search(
        SearchQuery(
            text=body.text,
            top_k=body.top_k,
            mode=body.mode,
            logical_type=body.logical_type,
            source_name=body.source_name,
        )
    )
    hits = [
        SearchHitBody(
            doc_id=h.doc_id,
            title=h.title,
            source_name=h.source_name,
            logical_type=h.logical_type,
            score=h.score,
            headline=h.headline,
        )
        for h in response.hits
    ]
    return SearchResponseBody(hits=hits, total_found=response.total_found, latency_ms=response.latency_ms)


@router.get("/docs")
async def list_documents(
    kb: KBServiceDep,
    logical_type: str | None = None,
    limit: int = 100,
) -> dict:
    """List documents in the knowledge base."""
    df = kb.list_documents(logical_type=logical_type, limit=limit)
    return {"items": df.to_dicts(), "total": df.height}


@router.get("/docs/{doc_id}")
async def get_document(doc_id: str, kb: KBServiceDep) -> dict:
    """Get metadata for a specific document."""
    df = kb.get_document(doc_id)
    if df.is_empty():
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found")
    return df.to_dicts()[0]
