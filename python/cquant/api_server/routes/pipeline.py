"""Pipeline routes — run and monitor the automated ML pipeline."""

from __future__ import annotations

import logging
import threading
from typing import Any

from fastapi import APIRouter, BackgroundTasks

from cquant.api_server.deps import CatalogDep, run_job_async

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/pipeline", tags=["pipeline"])

# Module-level state for tracking pipeline runs
_pipeline_lock = threading.Lock()
_current_run: dict[str, Any] | None = None
_is_running: bool = False


def _run_pipeline_bg(catalog: Any) -> None:
    """Background task that runs the full pipeline."""
    global _current_run, _is_running
    with _pipeline_lock:
        _is_running = True

    try:
        from cquant.pipeline.config import PipelineConfig
        from cquant.pipeline.orchestrator import PipelineOrchestrator

        config = PipelineConfig()
        orchestrator = PipelineOrchestrator(catalog, config)
        result = orchestrator.run_full_pipeline()

        with _pipeline_lock:
            _current_run = result
            _is_running = False

        logger.info(
            "Pipeline completed: run_id=%s, status=%s",
            result.get("run_id"), result.get("status"),
        )
    except Exception as exc:
        logger.error("Pipeline failed: %s", exc)
        with _pipeline_lock:
            _current_run = {"status": "error", "error": str(exc)}
            _is_running = False


@router.post("/run")
async def run_pipeline(catalog: CatalogDep, background_tasks: BackgroundTasks) -> dict:
    """Run the full ML pipeline manually.

    Kicks off the pipeline in the background and returns immediately
    with a run ID.  Use ``GET /pipeline/status`` to poll progress.
    """
    global _is_running

    with _pipeline_lock:
        if _is_running:
            return {
                "status": "already_running",
                "detail": "A pipeline run is already in progress. Check /pipeline/status.",
            }
        _is_running = True

    background_tasks.add_task(run_job_async, _run_pipeline_bg, catalog)
    return {"status": "started", "detail": "Pipeline started in background."}


@router.get("/status")
async def get_pipeline_status() -> dict:
    """Get the current or most recent pipeline run status."""
    with _pipeline_lock:
        if _is_running:
            return {
                "status": "running",
                "detail": "Pipeline is currently executing.",
            }
        if _current_run is not None:
            return {
                "status": _current_run.get("status", "unknown"),
                "run_id": _current_run.get("run_id"),
                "started_at": _current_run.get("started_at"),
                "finished_at": _current_run.get("finished_at"),
                "duration_seconds": _current_run.get("duration_seconds"),
                "stages": _current_run.get("stages"),
            }
        return {
            "status": "idle",
            "detail": "No pipeline run has been executed yet.",
        }
