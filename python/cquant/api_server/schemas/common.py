"""Shared API schemas."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ErrorResponse(BaseModel):
    detail: str
    code: str = "error"


class JobStatus(BaseModel):
    job_id: str
    status: str          # 'pending' | 'running' | 'completed' | 'failed'
    message: str = ""
    result_uri: str = ""


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int = 1
    page_size: int = 20
