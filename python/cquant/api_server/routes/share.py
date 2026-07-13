"""Share link routes — create and retrieve shareable content links."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from cquant.api_server.deps import CatalogDep

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/share", tags=["share"])

_SHARE_DDL = """
CREATE TABLE IF NOT EXISTS shares (
    share_id      VARCHAR PRIMARY KEY,
    content_type  VARCHAR NOT NULL,
    content_id    VARCHAR NOT NULL,
    created_by    VARCHAR,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at    TIMESTAMP
)
"""

def _ensure_share_table(catalog) -> None:
    """Create the shares table if it doesn't exist (idempotent via IF NOT EXISTS)."""
    catalog.execute(_SHARE_DDL)


class ShareRequest(BaseModel):
    """Request body for creating a share link."""
    content_type: Literal["backtest", "strategy", "factor", "report"] = Field(
        ..., description="Type of content to share"
    )
    content_id: str = Field(..., min_length=1, description="ID of the content to share")
    created_by: str = Field(default="", description="Optional creator identifier")


class ShareResponse(BaseModel):
    """Response for share creation."""
    share_id: str
    url: str


class ShareContent(BaseModel):
    """Share content details."""
    share_id: str
    content_type: str
    content_id: str
    created_by: str | None = None
    created_at: str | None = None
    expires_at: str | None = None


@router.post("", response_model=ShareResponse, status_code=201)
async def create_share(body: ShareRequest, catalog: CatalogDep) -> dict:
    """Create a new share link for content.

    Returns a short share_id and URL that can be used to retrieve the shared content.
    """
    _ensure_share_table(catalog)

    share_id = uuid4().hex[:12]
    now = datetime.now(tz=timezone.utc).isoformat()

    try:
        catalog.execute(
            "INSERT INTO shares (share_id, content_type, content_id, created_by, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            [share_id, body.content_type, body.content_id, body.created_by or None, now],
        )
    except Exception as exc:
        logger.exception("Failed to create share link")
        raise HTTPException(status_code=500, detail="Failed to create share link")

    return {"share_id": share_id, "url": f"/share/{share_id}"}


@router.get("/{share_id}", response_model=ShareContent)
async def get_share(share_id: str, catalog: CatalogDep) -> dict:
    """Retrieve share content by share_id.

    Returns the shared content metadata including content_type and content_id.
    Raises 404 if share_id is not found or has expired.
    """
    _ensure_share_table(catalog)

    try:
        df = catalog.query(
            "SELECT share_id, content_type, content_id, created_by, created_at, expires_at "
            "FROM shares WHERE share_id = ?",
            [share_id],
        )
    except Exception as exc:
        logger.exception("Failed to query share %s", share_id)
        raise HTTPException(status_code=500, detail="Failed to retrieve share")

    if df.is_empty():
        raise HTTPException(status_code=404, detail="Share not found")

    row = df.to_dicts()[0]

    # Check expiration
    if row.get("expires_at"):
        try:
            expires_at = datetime.fromisoformat(str(row["expires_at"]))
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if datetime.now(tz=timezone.utc) > expires_at:
                raise HTTPException(status_code=404, detail="Share link has expired")
        except HTTPException:
            raise
        except Exception as exc:
            logger.warning("Failed to parse expires_at=%s for share %s: %s", row.get("expires_at"), share_id, exc)

    # Convert datetime objects to strings for JSON serialization
    result = {}
    for key, value in row.items():
        if isinstance(value, datetime):
            result[key] = value.isoformat()
        else:
            result[key] = value

    return result
