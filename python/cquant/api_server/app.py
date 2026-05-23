"""cquant.api_server.app — FastAPI application factory.

Usage::

    # Run locally:
    uvicorn cquant.api_server.app:app --host 0.0.0.0 --port 8000 --reload

    # Or via Python:
    from cquant.api_server.app import create_app
    app = create_app()
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from cquant.api_server.routes import (
    advisor,
    backtests,
    datasets,
    factors,
    live,
    ml,
    news,
    strategies,
    health,
    knowledge,
    plugins,
    trading,
)

logger = logging.getLogger(__name__)

_VERSION = "0.1.0"
_TITLE = "cQuant Research API"
_DESCRIPTION = (
    "REST API for the cQuant quantitative research and backtesting platform. "
    "Provides access to market data, factor values, backtest results, "
    "the knowledge base, AI research advisor, and trading operations."
)


def create_app(
    *,
    cors_origins: list[str] | None = None,
    debug: bool = False,
) -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=_TITLE,
        description=_DESCRIPTION,
        version=_VERSION,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        debug=debug,
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    origins = cors_origins or ["http://localhost:3000", "http://localhost:5173"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Global exception handler ───────────────────────────────────────────────
    @app.exception_handler(Exception)
    async def _global_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception on %s %s", request.method, request.url)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "code": "internal_error"},
        )

    # ── Routers ────────────────────────────────────────────────────────────────
    from fastapi import Depends
    from cquant.api_server.deps import verify_api_key

    _auth = [Depends(verify_api_key)]

    prefix = "/api/v1"
    app.include_router(health.router)
    app.include_router(datasets.router, prefix=prefix, dependencies=_auth)
    app.include_router(factors.router, prefix=prefix, dependencies=_auth)
    app.include_router(backtests.router, prefix=prefix, dependencies=_auth)
    app.include_router(knowledge.router, prefix=prefix, dependencies=_auth)
    app.include_router(advisor.router, prefix=prefix, dependencies=_auth)
    app.include_router(plugins.router, prefix=prefix, dependencies=_auth)
    app.include_router(news.router, prefix=prefix, dependencies=_auth)
    app.include_router(strategies.router, prefix=prefix, dependencies=_auth)
    app.include_router(ml.router, prefix=prefix, dependencies=_auth)
    app.include_router(live.router, prefix=prefix, dependencies=_auth)
    app.include_router(trading.router, prefix=prefix, dependencies=_auth)

    logger.info("cQuant API v%s ready — docs at /api/docs", _VERSION)
    return app


# Module-level app instance for uvicorn
app: FastAPI = create_app()
