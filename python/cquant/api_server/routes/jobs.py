"""Job management routes — cancel and delete background jobs."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from cquant.api_server.deps import CatalogDep

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/jobs", tags=["jobs"])

# Tables to check for jobs, in priority order
_JOB_TABLES = [
    ("meta_ml_jobs", "job_id", "status"),
    ("gold_backtest_runs", "run_id", "status"),
    ("meta_factor_analytics", "job_id", "status"),
]


def _find_job(catalog, job_id: str) -> tuple[str, str, str] | None:
    """Find a job across all tables. Returns (table, id_col, status) or None."""
    for table, id_col, status_col in _JOB_TABLES:
        try:
            df = catalog.query(
                f"SELECT {id_col}, {status_col} FROM {table} WHERE {id_col} = ?",
                [job_id],
            )
            if not df.is_empty():
                row = df.to_dicts()[0]
                return table, id_col, row[status_col]
        except Exception:
            continue
    return None


@router.post("/{job_id}/cancel")
async def cancel_job(job_id: str, catalog: CatalogDep) -> dict:
    """Cancel a running or pending job."""
    result = _find_job(catalog, job_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    table, id_col, status = result
    if status not in ("pending", "running"):
        raise HTTPException(
            status_code=400,
            detail=f"Job '{job_id}' has status '{status}' and cannot be cancelled",
        )

    catalog.execute(
        f"UPDATE {table} SET status = 'cancelled' WHERE {id_col} = ?",
        [job_id],
    )
    return {"job_id": job_id, "status": "cancelled"}


@router.delete("/{job_id}")
async def delete_job(job_id: str, catalog: CatalogDep) -> dict:
    """Delete a completed or failed job."""
    result = _find_job(catalog, job_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    table, id_col, status = result
    if status in ("pending", "running"):
        raise HTTPException(
            status_code=400,
            detail=f"Job '{job_id}' is still {status}. Cancel it first.",
        )

    catalog.execute(
        f"DELETE FROM {table} WHERE {id_col} = ?",
        [job_id],
    )
    return {"job_id": job_id, "status": "deleted"}
