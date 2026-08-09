"""cquant.api_server.routes.metrics — Prometheus metrics + /metrics endpoint.

Exposes the metrics registry on ``GET /metrics`` for scraping by a Prometheus
server. The HTTP request counter is owned by ``middleware.py`` (it has to be
imported by the middleware before any request runs); this module owns the
backtest / queue / DuckDB metrics and re-exports the HTTP counter for
completeness.

Metric catalogue
----------------
* ``http_requests_total`` (Counter, method/path/status) — owned in middleware
* ``backtest_duration_seconds`` (Histogram, job_type) — observed in
  ``run_job_async`` for every heavy job
* ``backtest_job_duration_seconds`` (Histogram, job_type/status) — same data
  keyed by outcome, so dashboards can split success vs failure latency
* ``backtest_jobs_active`` (Gauge) — currently running heavy jobs, mirrored
  from ``JobQueueStats.running``; refreshed on every ``/metrics`` scrape
* ``backtest_jobs_waiting`` (Gauge) — queued-but-not-started jobs
* ``duckdb_query_duration_seconds`` (Histogram) — DuckDB read latency,
  observed from ``CatalogBackend`` instrumentation

The endpoint is intentionally *not* behind the global API-key auth dependency
so a scrape job can poll it without a token (set ``/metrics`` allow-listing at
the reverse proxy in production).
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter
from fastapi.responses import Response

logger = logging.getLogger(__name__)
router = APIRouter(tags=["metrics"])


# ---------------------------------------------------------------------------
# Metric registry
# ---------------------------------------------------------------------------
#
# All prometheus objects are created lazily behind a try/except so this module
# imports cleanly even if prometheus_client is missing — the /metrics endpoint
# then returns a 503 explaining the gap instead of crashing on import.
try:
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        Gauge,
        Histogram,
        generate_latest,
    )
    from prometheus_client import Counter as _Counter

    # Re-export the HTTP counter so callers can import everything from here.
    from cquant.api_server.middleware import http_requests_total  # noqa: F401

    backtest_duration_seconds = Histogram(
        "backtest_duration_seconds",
        "Wall-clock duration of heavy background jobs (backtest/factors/ML/...).",
        ["job_type"],
        buckets=(0.5, 1, 2.5, 5, 10, 30, 60, 120, 300, 600, 1200, 3600),
    )
    backtest_job_duration_seconds = Histogram(
        "backtest_job_duration_seconds",
        "Heavy background job duration keyed by outcome (success/failure).",
        ["job_type", "status"],
        buckets=(0.5, 1, 2.5, 5, 10, 30, 60, 120, 300, 600, 1200, 3600),
    )
    backtest_jobs_active = Gauge(
        "backtest_jobs_active",
        "Number of heavy background jobs currently running.",
    )
    backtest_jobs_waiting = Gauge(
        "backtest_jobs_waiting",
        "Number of heavy background jobs queued but not yet started.",
    )
    duckdb_query_duration_seconds = Histogram(
        "duckdb_query_duration_seconds",
        "DuckDB SELECT query latency as observed through the data layer.",
        ["operation"],  # operation: query / execute / executemany
        buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
    )

    _PROMETHEUS_AVAILABLE = True
except Exception as exc:  # pragma: no cover — prometheus_client is normally present
    logger.warning("prometheus_client unavailable, /metrics disabled: %s", exc)
    _PROMETHEUS_AVAILABLE = False
    http_requests_total = None  # type: ignore[assignment]
    backtest_duration_seconds = None  # type: ignore[assignment]
    backtest_job_duration_seconds = None  # type: ignore[assignment]
    backtest_jobs_active = None  # type: ignore[assignment]
    backtest_jobs_waiting = None  # type: ignore[assignment]
    duckdb_query_duration_seconds = None  # type: ignore[assignment]


def _sync_queue_gauges() -> None:
    """Mirror ``JobQueueStats`` running/waiting counts into Prometheus gauges.

    Called on every scrape so the gauges reflect queue depth without needing
    a background polling task. Import is local to avoid a circular import
    (deps.py <-> metrics would otherwise tangle).
    """
    if not _PROMETHEUS_AVAILABLE:
        return
    try:
        from cquant.api_server.deps import job_queue_stats

        snapshot: dict[str, Any] = job_queue_stats.snapshot()
        backtest_jobs_active.set(int(snapshot.get("running", 0)))  # type: ignore[union-attr]
        backtest_jobs_waiting.set(int(snapshot.get("waiting", 0)))  # type: ignore[union-attr]
    except Exception as exc:  # pragma: no cover — never break a scrape
        logger.debug("Failed to sync job queue gauges: %s", exc)


@router.get("/metrics")
async def metrics() -> Response:
    """Prometheus exposition endpoint.

    Returns the default registry in the Prometheus text exposition format.
    Returns 503 if ``prometheus_client`` is not installed so a misconfigured
    scrape fails loudly rather than emitting an empty body.
    """
    if not _PROMETHEUS_AVAILABLE:
        return Response(
            content="prometheus_client not installed\n",
            media_type="text/plain",
            status_code=503,
        )
    _sync_queue_gauges()
    body = generate_latest()  # type: ignore[misc]
    return Response(content=body, media_type=CONTENT_TYPE_LATEST)
