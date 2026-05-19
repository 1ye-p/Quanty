"""Knowledge-base API schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


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
