"""cquant.api_server.middleware — HTTP observability middleware.

Provides:

* ``StructuredLoggingMiddleware`` — emits one structured log record per HTTP
  request with method, path, status, and latency, and increments the
  ``http_requests_total`` Prometheus counter.
* ``configure_structured_logging`` — installs a JSON formatter on the
  ``cquant.api`` logger so the records above (and any other logger output
  routed through it) render as machine-parseable JSON. Falls back to the
  default human-readable format when ``CQUANT_LOG_JSON != "1"``.

The JSON formatter is a thin ``logging.Formatter`` subclass — it avoids an
external dependency (e.g. structlog) while still producing key=value JSON
suitable for ingestion by Loki / Elastic / CloudWatch.

Logging is best-effort: if ``prometheus_client`` is unavailable, the metrics
counter is a silent no-op so request handling never breaks.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("cquant.api")


# ---------------------------------------------------------------------------
# Optional Prometheus integration (graceful degradation)
# ---------------------------------------------------------------------------
try:
    from prometheus_client import Counter as _Counter

    http_requests_total = _Counter(
        "http_requests_total",
        "Total HTTP requests handled by the API server.",
        ["method", "path", "status"],
    )
except Exception:  # pragma: no cover — prometheus_client is normally present
    class _NoopCounter:
        def labels(self, *args: Any, **kwargs: Any) -> "_NoopCounter":
            return self

        def inc(self, amount: float = 1.0) -> None:  # noqa: ARG002
            pass

    http_requests_total = _NoopCounter()


class _JsonFormatter(logging.Formatter):
    """Emit each log record as a single JSON line.

    Standard LogRecord attributes and any ``extra`` payload are flattened into
    the JSON object. An ``event`` key mirrors ``record.message`` so callers can
    pass a short human label and rely on ``extra`` for structured fields,
    mirroring the structlog convention.
    """

    # LogRecord __dict__ keys that are infrastructure, not payload.
    _RESERVED = frozenset(
        {
            "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
            "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
            "created", "msecs", "relativeCreated", "thread", "threadName",
            "processName", "process", "getMessage", "taskName", "message",
        }
    )

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S.%fZ"),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key in self._RESERVED or key.startswith("_"):
                continue
            payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_structured_logging(level: int | str = logging.INFO) -> None:
    """Install the JSON formatter on the ``cquant.api`` logger.

    Idempotent: re-running replaces the handler cleanly rather than stacking
    duplicates. Set ``CQUANT_LOG_JSON=1`` to opt into JSON; otherwise a plain
    formatter is used for local readability.
    """
    import os

    root = logging.getLogger("cquant.api")
    root.setLevel(level)

    # Remove any handler we previously installed.
    root.handlers = [h for h in root.handlers if not getattr(h, "_cquant_structured", False)]

    handler = logging.StreamHandler()
    handler._cquant_structured = True  # type: ignore[attr-defined]
    if os.getenv("CQUANT_LOG_JSON", "1") == "1":
        handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root.addHandler(handler)
    root.propagate = False


class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    """Log every HTTP request as structured JSON and bump the request counter.

    The log record carries ``method`` / ``path`` / ``status`` / ``duration_ms``
    via ``extra`` so downstream formatters can surface them as first-class
    fields. Errors raised downstream are still logged (status defaults to 500)
    and re-raised so FastAPI's exception handlers run normally.
    """

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        start = time.perf_counter()
        status_code = 500
        response: Response | None = None
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            path = request.url.path
            method = request.method
            logger.info(
                "request",
                extra={
                    "method": method,
                    "path": path,
                    "status": status_code,
                    "duration_ms": duration_ms,
                },
            )
            try:
                http_requests_total.labels(method=method, path=path, status=str(status_code)).inc()
            except Exception:  # pragma: no cover — never let metrics break requests
                pass
