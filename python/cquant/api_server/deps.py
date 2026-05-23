"""cquant.api_server.deps — FastAPI dependency injection.

All shared resources (Catalog, KnowledgeBaseService, AdvisorOrchestrator) are
created once at startup and injected via FastAPI's Depends() mechanism.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from cquant.core.config import settings
from cquant.datahub.catalog import Catalog
from cquant.knowledge_base import KnowledgeBaseService


@lru_cache(maxsize=1)
def _get_catalog() -> Catalog:
    cat = Catalog(db_path=settings.db_path)
    cat.initialize()
    return cat


@lru_cache(maxsize=1)
def _get_kb_service() -> KnowledgeBaseService:
    return KnowledgeBaseService.create(
        db_path=settings.db_path,
        kb_root=settings.storage.knowledge_root,
        vector_path=f"{settings.storage.knowledge_root}/vector/lancedb",
    )


def get_catalog() -> Catalog:
    return _get_catalog()


def get_kb_service() -> KnowledgeBaseService:
    return _get_kb_service()


CatalogDep = Annotated[Catalog, Depends(get_catalog)]
KBServiceDep = Annotated[KnowledgeBaseService, Depends(get_kb_service)]

import os

from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_bearer_scheme = HTTPBearer(auto_error=False)


def verify_api_key(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> None:
    """Verify Bearer token against CQUANT_API_KEY env var.

    Auth is disabled (dev mode) when CQUANT_API_KEY is not set.
    """
    api_key = os.environ.get("CQUANT_API_KEY", "")
    if not api_key:
        return  # dev mode — no auth required
    if credentials is None or credentials.credentials != api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key. Use Authorization: Bearer <key>",
            headers={"WWW-Authenticate": "Bearer"},
        )
