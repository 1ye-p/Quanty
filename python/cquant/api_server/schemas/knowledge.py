"""Knowledge-base API schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class IngestRequestBody(BaseModel):
    uri: str
    logical_type: Literal["research", "strategy", "notes", "data"] = "research"
    source_name: str = ""
    title: str = ""
    language: str = "zh-CN"


class IngestResponseBody(BaseModel):
    doc_id: str
    status: str              # 'ok' | 'duplicate' | 'error'
    chunk_count: int = 0
    run_id: str = ""
    error: str = ""


class SearchRequestBody(BaseModel):
    text: str
    top_k: int = 10
    mode: Literal["hybrid", "semantic", "keyword"] = "hybrid"
    logical_type: str | None = None
    source_name: str | None = None


class SearchHitBody(BaseModel):
    doc_id: str
    title: str = ""
    source_name: str = ""
    logical_type: str = ""
    score: float = 0.0
    headline: str = ""


class SearchResponseBody(BaseModel):
    hits: list[SearchHitBody]
    total_found: int
    latency_ms: int


class QARequestBody(BaseModel):
    question: str = Field(..., min_length=1, description="The question to answer using the knowledge base")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of context snippets to retrieve")
    model: Literal["claude", "openai"] = Field(default="claude", description="LLM provider to use")


class QASourceBody(BaseModel):
    doc_id: str
    snippet: str = ""
    score: float = 0.0


class QAResponseBody(BaseModel):
    answer: str
    sources: list[QASourceBody]
    model: str
