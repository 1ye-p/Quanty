"""Dataset catalog routes."""

from __future__ import annotations

from fastapi import APIRouter

from cquant.api_server.deps import CatalogDep

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.get("")
async def list_datasets(catalog: CatalogDep, limit: int = 50) -> dict:
    """List registered dataset versions."""
    df = catalog.query(
        "SELECT version_id, dataset_name, frequency, start_date, end_date, "
        "asset_count, row_count, source, created_at, is_current "
        "FROM silver_dataset_versions "
        "ORDER BY created_at DESC LIMIT ?",
        [limit],
    )
    return {"items": df.to_dicts(), "total": df.height}


@router.get("/{version_id}")
async def get_dataset(version_id: str, catalog: CatalogDep) -> dict:
    """Get a specific dataset version."""
    df = catalog.query(
        "SELECT * FROM silver_dataset_versions WHERE version_id = ?",
        [version_id],
    )
    if df.is_empty():
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Dataset version '{version_id}' not found")
    return df.to_dicts()[0]
