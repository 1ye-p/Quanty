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


class AlertRuleUpdateBody(BaseModel):
    params: dict | None = None
    enabled: bool | None = None


@router.put("/rules/{rule_id}")
async def update_alert_rule(rule_id: str, body: AlertRuleUpdateBody, catalog: CatalogDep) -> dict:
    _ensure_tables(catalog)
    existing = catalog.query(
        "SELECT rule_id, params_json, enabled FROM meta_alert_rules WHERE rule_id = ?",
        [rule_id],
    )
    if existing.is_empty():
        raise HTTPException(status_code=404, detail=f"Rule '{rule_id}' not found")

    updates = []
    params = []
    if body.params is not None:
        updates.append("params_json = ?")
        params.append(json.dumps(body.params))
    if body.enabled is not None:
        updates.append("enabled = ?")
        params.append(body.enabled)

    if updates:
        params.append(rule_id)
        catalog.execute(
            f"UPDATE meta_alert_rules SET {', '.join(updates)} WHERE rule_id = ?",
            params,
        )
    return {"rule_id": rule_id, "status": "updated"}


@router.get("/history")
async def list_alert_history(catalog: CatalogDep, unread_only: bool = False, limit: int = 50) -> dict:
    _ensure_tables(catalog)
    where = "WHERE read = FALSE" if unread_only else "WHERE 1=1"
    df = catalog.query(
        f"SELECT alert_id, rule_id, rule_type, severity, message, triggered_at, read "
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


class NewsSentimentCheckBody(BaseModel):
    threshold: float = -0.5
    change_threshold: float = -0.3
    scope: str = "portfolio"
    critical_events: list[str] | None = None


@router.post("/check-news-sentiment")
async def check_news_sentiment_endpoint(
    body: NewsSentimentCheckBody | None = None,
    catalog: CatalogDep = None,
) -> dict:
    """手动触发组合新闻情感检查。

    Accepts optional parameters to override the default thresholds.
    If no body is provided, uses defaults (threshold=-0.5, change_threshold=-0.3,
    scope="portfolio").
    """
    from cquant.api_server.alert_checker import (
        _ensure_tables,
        _get_portfolio_asset_ids,
        check_news_sentiment,
    )

    _ensure_tables(catalog)

    if body is None:
        body = NewsSentimentCheckBody()

    # Find or create a temporary rule for this manual check
    params = {
        "threshold": body.threshold,
        "change_threshold": body.change_threshold,
        "scope": body.scope,
    }
    if body.critical_events is not None:
        params["critical_events"] = body.critical_events

    # Use a dedicated manual rule_id so alerts are traceable
    rule_id = "manual_news_sentiment"
    triggered = check_news_sentiment(catalog, rule_id, params)

    # Collect the asset IDs that were checked for reporting
    asset_ids = _get_portfolio_asset_ids(catalog) if body.scope == "portfolio" else set()

    return {
        "triggered": triggered,
        "scope": body.scope,
        "assets_checked": sorted(asset_ids),
        "params": params,
    }


# ── Notification Channels ──────────────────────────────────────────────────────

_channel_tables_ensured = False


def _ensure_channel_tables(catalog) -> None:
    global _channel_tables_ensured
    if _channel_tables_ensured:
        return
    try:
        catalog.execute("""
            CREATE TABLE IF NOT EXISTS meta_notification_channels (
                channel_id   VARCHAR PRIMARY KEY,
                channel_type VARCHAR NOT NULL,
                name         VARCHAR NOT NULL,
                config_json  VARCHAR NOT NULL,
                enabled      BOOLEAN DEFAULT TRUE,
                created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        _channel_tables_ensured = True
    except Exception as exc:
        import logging
        logging.getLogger(__name__).debug("_ensure_channel_tables: %s", exc)


class ChannelBody(BaseModel):
    channel_type: str
    name: str
    config: dict
    enabled: bool = True


@router.get("/channels")
async def list_channels(catalog: CatalogDep) -> dict:
    _ensure_channel_tables(catalog)
    df = catalog.query(
        "SELECT channel_id, channel_type, name, config_json, enabled, created_at "
        "FROM meta_notification_channels ORDER BY created_at DESC"
    )
    _SENSITIVE_KEYS = {"password", "token", "secret", "sign_key", "webhook_url"}
    items = []
    for r in df.to_dicts():
        config = json.loads(r["config_json"])
        masked = {k: ("***" if k in _SENSITIVE_KEYS and v else v) for k, v in config.items()}
        items.append({**r, "config": masked})
    return {"items": items}


@router.post("/channels", status_code=201)
async def create_channel(body: ChannelBody, catalog: CatalogDep) -> dict:
    _ensure_channel_tables(catalog)
    channel_id = f"ch_{uuid.uuid4().hex[:10]}"
    catalog.execute(
        "INSERT INTO meta_notification_channels (channel_id, channel_type, name, config_json, enabled) "
        "VALUES (?, ?, ?, ?, ?)",
        [channel_id, body.channel_type, body.name, json.dumps(body.config), body.enabled],
    )
    return {"channel_id": channel_id, "status": "created"}


@router.delete("/channels/{channel_id}")
async def delete_channel(channel_id: str, catalog: CatalogDep) -> dict:
    _ensure_channel_tables(catalog)
    catalog.execute("DELETE FROM meta_notification_channels WHERE channel_id = ?", [channel_id])
    return {"channel_id": channel_id, "status": "deleted"}
