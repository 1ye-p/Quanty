"""Job management routes — cancel and delete background jobs."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from cquant.api_server.deps import CatalogDep

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("/{job_id}/cancel")
async def cancel_job(job_id: str, catalog: CatalogDep) -> dict:
    """Cancel a running or pending job."""
    # Check if job exists
    df = catalog.query(
        "SELECT job_id, status FROM meta_factor_analytics WHERE job_id = ?",
        [job_id],
    )
    if df.is_empty():
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    job = df.to_dicts()[0]
    if job["status"] not in ("pending", "running"):
        raise HTTPException(
            status_code=400,
            detail=f"Job '{job_id}' has status '{job['status']}' and cannot be cancelled",
        )

    catalog.execute(
        "UPDATE meta_factor_analytics SET status = 'cancelled' WHERE job_id = ?",
        [job_id],
    )
    return {"job_id": job_id, "status": "cancelled"}


@router.delete("/{job_id}")
async def delete_job(job_id: str, catalog: CatalogDep) -> dict:
    """Delete a completed or failed job."""
    df = catalog.query(
        "SELECT job_id, status FROM meta_factor_analytics WHERE job_id = ?",
        [job_id],
    )
    if df.is_empty():
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    job = df.to_dicts()[0]
    if job["status"] in ("pending", "running"):
        raise HTTPException(
            status_code=400,
            detail=f"Job '{job_id}' is still {job['status']}. Cancel it first.",
        )

    catalog.execute(
        "DELETE FROM meta_factor_analytics WHERE job_id = ?",
        [job_id],
    )
    return {"job_id": job_id, "status": "deleted"}
