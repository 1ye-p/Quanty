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


class WalkForwardConfig(BaseModel):
    """Walk-forward rolling configuration for ML training and backtesting."""
    n_splits: int = 3
    gap_days: int = 5
    window_type: str = "expanding"  # "expanding" | "sliding"
    step_days: int | None = None
    purge_window: int = 0


class UniverseCreateBody(BaseModel):
    """自定义股票池创建请求。"""
    name: str
    asset_ids: list[str] = []
    filter_type: str = "all"  # "all" | "exchange" | "custom"
    filter_value: str = ""
