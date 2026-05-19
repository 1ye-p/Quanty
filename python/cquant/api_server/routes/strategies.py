"""Strategy configuration CRUD routes."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from cquant.api_server.deps import CatalogDep

router = APIRouter(prefix="/strategies", tags=["strategies"])


class StrategyCreateBody(BaseModel):
    strategy_id: str
    config_text: str
    config_format: str = "json"   # 'json' | 'toml'
    universe_id: str = ""


class StrategyUpdateBody(BaseModel):
    config_text: str
    config_format: str = "json"


def _parse_config(text: str, fmt: str) -> dict | None:
    if fmt == "json":
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None
    return None  # TOML parsing can be added later


@router.get("")
async def list_strategies(catalog: CatalogDep) -> dict:
    df = catalog.query(
        "SELECT strategy_id, config_format, config_text, universe_id, created_at, updated_at "
        "FROM meta_strategy_configs ORDER BY updated_at DESC"
    )
    return {"items": df.to_dicts(), "total": df.height}


@router.post("", status_code=201)
async def create_strategy(body: StrategyCreateBody, catalog: CatalogDep) -> dict:
    now = datetime.now(tz=timezone.utc).isoformat()
    parsed = _parse_config(body.config_text, body.config_format)

    # Reject invalid JSON before persisting
    if body.config_format == "json" and parsed is None:
        raise HTTPException(status_code=422, detail="config_text is not valid JSON")

    # Check if already exists
    existing = catalog.query(
        "SELECT strategy_id FROM meta_strategy_configs WHERE strategy_id = ?",
        [body.strategy_id],
    )
    if not existing.is_empty():
        raise HTTPException(status_code=409, detail=f"Strategy '{body.strategy_id}' already exists")

    catalog.execute(
        """INSERT INTO meta_strategy_configs
           (strategy_id, config_format, config_text, parsed_config, universe_id, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        [body.strategy_id, body.config_format, body.config_text,
         json.dumps(parsed) if parsed else None, body.universe_id, now, now],
    )
    return {"strategy_id": body.strategy_id, "status": "created"}


@router.get("/{strategy_id}")
async def get_strategy(strategy_id: str, catalog: CatalogDep) -> dict:
    df = catalog.query(
        "SELECT * FROM meta_strategy_configs WHERE strategy_id = ?",
        [strategy_id],
    )
    if df.is_empty():
        raise HTTPException(status_code=404, detail=f"Strategy '{strategy_id}' not found")
    return df.to_dicts()[0]


@router.put("/{strategy_id}")
async def update_strategy(strategy_id: str, body: StrategyUpdateBody, catalog: CatalogDep) -> dict:
    existing = catalog.query(
        "SELECT strategy_id FROM meta_strategy_configs WHERE strategy_id = ?",
        [strategy_id],
    )
    if existing.is_empty():
        raise HTTPException(status_code=404, detail=f"Strategy '{strategy_id}' not found")

    now = datetime.now(tz=timezone.utc).isoformat()
    parsed = _parse_config(body.config_text, body.config_format)
    if body.config_format == "json" and parsed is None:
        raise HTTPException(status_code=422, detail="config_text is not valid JSON")
    catalog.execute(
        """UPDATE meta_strategy_configs
           SET config_text = ?, config_format = ?, parsed_config = ?, updated_at = ?
           WHERE strategy_id = ?""",
        [body.config_text, body.config_format,
         json.dumps(parsed) if parsed else None, now, strategy_id],
    )
    return {"strategy_id": strategy_id, "status": "updated"}


@router.delete("/{strategy_id}")
async def delete_strategy(strategy_id: str, catalog: CatalogDep) -> dict:
    existing = catalog.query(
        "SELECT strategy_id FROM meta_strategy_configs WHERE strategy_id = ?",
        [strategy_id],
    )
    if existing.is_empty():
        raise HTTPException(status_code=404, detail=f"Strategy '{strategy_id}' not found")
    catalog.execute(
        "DELETE FROM meta_strategy_configs WHERE strategy_id = ?",
        [strategy_id],
    )
    return {"strategy_id": strategy_id, "status": "deleted"}
