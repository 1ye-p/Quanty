"""Knowledge-base routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from cquant.api_server.deps import CatalogDep, KBServiceDep
from cquant.api_server.schemas.knowledge import (
    IngestRequestBody,
    IngestResponseBody,
    QAResponseBody,
    QARequestBody,
    QASourceBody,
    SearchHitBody,
    SearchRequestBody,
    SearchResponseBody,
)
from cquant.knowledge_base import IngestRequest, SearchQuery

logger = logging.getLogger(__name__)

_QA_SYSTEM_PROMPT = (
    "You are a quantitative research assistant. "
    "Answer the user's question based on the provided context. "
    "Cite sources when possible. If the context does not contain enough information "
    "to answer the question, say so honestly."
)

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


@router.post("/qa", response_model=QAResponseBody)
async def knowledge_qa(body: QARequestBody, kb: KBServiceDep) -> QAResponseBody:
    """RAG Q&A: retrieve relevant snippets from the knowledge base, then answer with an LLM."""
    # Step 1: Retrieve relevant context from knowledge base
    response = kb.search(
        SearchQuery(text=body.question, top_k=body.top_k, mode="hybrid")
    )

    if not response.hits:
        return QAResponseBody(
            answer="No relevant documents found in the knowledge base for your question.",
            sources=[],
            model=body.model,
        )

    # Step 2: Build context from retrieved snippets
    context_parts: list[str] = []
    sources: list[QASourceBody] = []
    for i, hit in enumerate(response.hits, 1):
        snippet = hit.headline or ""
        context_parts.append(f"[{i}] (doc: {hit.doc_id}, score: {hit.score:.2f}) {snippet}")
        sources.append(QASourceBody(doc_id=hit.doc_id, snippet=snippet, score=hit.score))

    context_block = "\n\n".join(context_parts)

    # Step 3: Call LLM
    from cquant.ai_advisor.providers.base import Message
    from cquant.ai_advisor.providers.claude import ClaudeProvider
    from cquant.ai_advisor.providers.openai_provider import OpenAIProvider

    provider = ClaudeProvider() if body.model == "claude" else OpenAIProvider()

    messages = [Message(role="user", content=f"Context:\n{context_block}\n\nQuestion: {body.question}")]
    try:
        result = await provider.generate(messages, system=_QA_SYSTEM_PROMPT, max_tokens=2048)
    except Exception as exc:
        logger.exception("LLM call failed for QA")
        raise HTTPException(status_code=502, detail=f"LLM provider error: {exc}")

    if result.stop_reason == "unavailable":
        logger.warning("LLM unavailable for QA: %s", result.content)
        raise HTTPException(
            status_code=503,
            detail=f"LLM provider '{body.model}' is not available: {result.content}",
        )

    return QAResponseBody(answer=result.content, sources=sources, model=result.model)


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
