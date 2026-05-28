"""告警规则 CRUD + 历史查询 API."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from cquant.api_server.deps import CatalogDep
from cquant.api_server.alert_checker import _ensure_tables, RULE_TYPES, run_all_checks

router = APIRouter(prefix="/alerts", tags=["alerts"])


class AlertRuleBody(BaseModel):
    rule_type: str
    params: dict
    enabled: bool = True


@router.get("/rules")
async def list_alert_rules(catalog: CatalogDep) -> dict:
    _ensure_tables(catalog)
    df = catalog.query(
        "SELECT rule_id, rule_type, params_json, enabled, created_at "
        "FROM meta_alert_rules ORDER BY created_at DESC"
    )
    items = []
    for r in df.to_dicts():
        items.append({**r, "params": json.loads(r["params_json"]),
                      "rule_type_label": RULE_TYPES.get(r["rule_type"], r["rule_type"])})
    return {"items": items, "rule_types": [
        {"type": k, "label": v} for k, v in RULE_TYPES.items()
    ]}


@router.post("/rules", status_code=201)
async def create_alert_rule(body: AlertRuleBody, catalog: CatalogDep) -> dict:
    if body.rule_type not in RULE_TYPES:
        raise HTTPException(status_code=400, detail=f"Unknown rule_type: {body.rule_type}")
    _ensure_tables(catalog)
    rule_id = f"ar_{uuid.uuid4().hex[:10]}"
    catalog.execute(
        "INSERT INTO meta_alert_rules (rule_id, rule_type, params_json, enabled) VALUES (?, ?, ?, ?)",
        [rule_id, body.rule_type, json.dumps(body.params), body.enabled],
    )
    return {"rule_id": rule_id, "status": "created"}


@router.delete("/rules/{rule_id}")
async def delete_alert_rule(rule_id: str, catalog: CatalogDep) -> dict:
    _ensure_tables(catalog)
    catalog.execute("DELETE FROM meta_alert_rules WHERE rule_id = ?", [rule_id])
    return {"rule_id": rule_id, "status": "deleted"}


@router.get("/history")
async def list_alert_history(catalog: CatalogDep, unread_only: bool = False, limit: int = 50) -> dict:
    _ensure_tables(catalog)
    where = "WHERE read = FALSE" if unread_only else "WHERE 1=1"
    df = catalog.query(
        f"SELECT alert_id, rule_id, rule_type, message, triggered_at, read "
        f"FROM meta_alert_history {where} ORDER BY triggered_at DESC LIMIT ?",
        [limit],
    )
    unread_count_df = catalog.query(
        "SELECT COUNT(*) as n FROM meta_alert_history WHERE read = FALSE"
    )
    unread_count = int(unread_count_df["n"][0]) if not unread_count_df.is_empty() else 0
    return {
        "items": df.to_dicts() if not df.is_empty() else [],
        "unread_count": unread_count,
    }


@router.post("/history/read-all")
async def mark_all_read(catalog: CatalogDep) -> dict:
    _ensure_tables(catalog)
    catalog.execute("UPDATE meta_alert_history SET read = TRUE WHERE read = FALSE")
    return {"status": "ok"}


@router.post("/check")
async def trigger_check(catalog: CatalogDep) -> dict:
    """手动触发一次所有规则检查。"""
    triggered = run_all_checks(catalog)
    return {"triggered": triggered}
