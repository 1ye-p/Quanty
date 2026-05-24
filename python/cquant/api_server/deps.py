"""cquant.api_server.deps — FastAPI dependency injection.

All shared resources (Catalog, KnowledgeBaseService, AdvisorOrchestrator) are
created once at startup and injected via FastAPI's Depends() mechanism.
"""

from __future__ import annotations

import hmac
import logging
import os
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

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

_logger = logging.getLogger(__name__)
_bearer_scheme = HTTPBearer(auto_error=False)
_auth_warned = False


def _is_trading_endpoint(request: Request) -> bool:
    return request.url.path.startswith("/api/v1/trading/")


def verify_api_key(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> None:
    """Verify Bearer token against CQUANT_API_KEY env var.

    Auth behavior when CQUANT_API_KEY is not set:
    - /trading/* endpoints: REJECT with 503 (safety-critical)
    - Other endpoints: PASS in dev mode with warning log
    """
    global _auth_warned
    api_key = os.environ.get("CQUANT_API_KEY", "")
    if not api_key:
        if _is_trading_endpoint(request):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Trading endpoints require CQUANT_API_KEY to be configured.",
            )
        if not _auth_warned:
            _logger.warning(
                "CQUANT_API_KEY is not set — API authentication is DISABLED. "
                "Set this environment variable before deploying to production."
            )
            _auth_warned = True
        return
    if credentials is None or not hmac.compare_digest(credentials.credentials, api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key. Use Authorization: Bearer <key>",
            headers={"WWW-Authenticate": "Bearer"},
        )
