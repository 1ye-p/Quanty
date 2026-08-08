"""cquant.api_server.deps — FastAPI dependency injection.

All shared resources (Catalog, KnowledgeBaseService, AdvisorOrchestrator) are
created once at startup and injected via FastAPI's Depends() mechanism.

This module also owns the global job concurrency primitives: a bounded
``JOB_SEMAPHORE`` that gates heavy background jobs (backtest / factors / ML /
scoring / datasets / pipeline) and a ``JobQueueStats`` counter that tracks how
many jobs are waiting and running for frontend display.
"""

from __future__ import annotations

import asyncio
import hmac
import logging
import os
from functools import lru_cache
from typing import Annotated, Any, Callable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from cquant.core.config import settings
from cquant.datahub.catalog import Catalog
from cquant.knowledge_base import KnowledgeBaseService


# ---------------------------------------------------------------------------
# Global job concurrency control
# ---------------------------------------------------------------------------
#
# Heavy background jobs (backtest, factor analytics, ML training, scoring,
# data ingest, full pipeline) are CPU/IO bound and can saturate the host if
# submitted unbounded. ``JOB_SEMAPHORE`` caps how many run concurrently; the
# cap is configurable via ``CQUANT_MAX_CONCURRENT_JOBS`` (default 2).
#
# Jobs are submitted through ``run_job_async`` (an async coroutine), so FastAPI
# runs them on the event loop where ``async with JOB_SEMAPHORE`` actually
# blocks, then dispatches the (synchronous) job body to a worker thread via
# ``asyncio.to_thread`` to avoid blocking the loop while the job runs.

#: Maximum number of heavy jobs that may execute concurrently.
JOB_SEMAPHORE = asyncio.Semaphore(int(os.getenv("CQUANT_MAX_CONCURRENT_JOBS", "2")))


class JobQueueStats:
    """Process-wide counters for the heavy job queue.

    All mutators are *not* async-safe by themselves — they are guarded by
    ``JOB_SEMAPHORE`` / ``_queue_counter_lock`` at the call sites in
    ``run_job_async``. Reads (``snapshot``) are atomic enough for observability.
    """

    __slots__ = ("waiting", "running", "total_submitted", "total_completed", "_next_position")

    def __init__(self) -> None:
        self.waiting: int = 0
        self.running: int = 0
        self.total_submitted: int = 0
        self.total_completed: int = 0
        self._next_position: int = 1

    def reserve(self) -> int:
        """Called when a job enters the queue. Returns its queue position."""
        self.waiting += 1
        self.total_submitted += 1
        position = self._next_position
        self._next_position += 1
        return position

    def acquire(self) -> None:
        """Called when a job leaves the queue and starts running."""
        self.waiting = max(0, self.waiting - 1)
        self.running += 1

    def release(self) -> None:
        """Called when a job finishes (success or failure)."""
        self.running = max(0, self.running - 1)
        self.total_completed += 1

    def snapshot(self) -> dict[str, Any]:
        """Return a JSON-serializable view of current queue state."""
        cap = int(os.getenv("CQUANT_MAX_CONCURRENT_JOBS", "2"))
        return {
            "max_concurrent": cap,
            "waiting": self.waiting,
            "running": self.running,
            "total_submitted": self.total_submitted,
            "total_completed": self.total_completed,
        }


#: Global queue counter shared by all routes.
job_queue_stats = JobQueueStats()


async def run_job_async(_run_job: Callable[..., Any], /, *args: Any, **kwargs: Any) -> Any:
    """Run a heavy (synchronous) job under the global semaphore.

    The job callable runs in a worker thread (``asyncio.to_thread``) so the
    event loop stays responsive while it blocks. ``job_queue_stats`` is updated
    across the queue→run→done transitions for frontend display.

    Parameters
    ----------
    _run_job:
        The synchronous job function. Positional-only so arbitrary keyword
        arguments can be forwarded without collision.
    *args, **kwargs:
        Forwarded verbatim to ``_run_job``.
    """
    job_queue_stats.reserve()
    try:
        async with JOB_SEMAPHORE:
            job_queue_stats.acquire()
            try:
                return await asyncio.to_thread(_run_job, *args, **kwargs)
            finally:
                job_queue_stats.release()
    except BaseException:
        # If reserve()/acquire() itself never happened (e.g. cancelled before
        # entering the semaphore), the finally above still balances acquire.
        # Here we only reach if something went wrong outside the try body;
        # ensure waiting counter does not leak on cancellation.
        raise


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
