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
    """解析策略配置文本，支持 JSON 和 TOML。"""
    text = text.strip()
    if fmt == "json":
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None
    if fmt == "toml":
        try:
            import tomllib
            return tomllib.loads(text)
        except Exception:
            return None
    # 自动检测格式
    if text.startswith('{') or text.startswith('[{'):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
    try:
        import tomllib
        return tomllib.loads(text)
    except Exception:
        return None


def _ensure_version_table(catalog) -> None:
    """幂等创建策略版本表。"""
    catalog.execute("""
        CREATE TABLE IF NOT EXISTS meta_strategy_versions (
            version_id    VARCHAR NOT NULL,
            strategy_id   VARCHAR NOT NULL,
            config_text   VARCHAR NOT NULL,
            config_format VARCHAR DEFAULT 'json',
            summary       VARCHAR DEFAULT '',
            created_at    TIMESTAMP NOT NULL,
            PRIMARY KEY (version_id)
        )
    """)


def _generate_summary(parsed: dict | None, config_format: str) -> str:
    """从解析后的配置生成单行展示摘要。"""
    if not parsed:
        return f"[{config_format}]"
    parts = []
    st = parsed.get("strategy_type", "")
    if st:
        parts.append(st)
    top_n = parsed.get("top_n")
    if top_n is not None:
        parts.append(f"top_n={top_n}")
    sort_factor = parsed.get("sort_factor") or next(iter(parsed.get("factors") or []), None)
    if sort_factor:
        parts.append(f"factor={sort_factor}")
    risk_policies = parsed.get("risk_policies", [])
    if risk_policies:
        parts.append(f"风控={','.join(risk_policies[:2])}")
    return " · ".join(parts) if parts else config_format


MAX_VERSIONS = 50


@router.get("")
async def list_strategies(catalog: CatalogDep) -> dict:
    df = catalog.query(
        "SELECT strategy_id, config_format, config_text, universe_id, created_at, updated_at "
        "FROM meta_strategy_configs ORDER BY updated_at DESC"
    )
    return {"items": df.to_dicts(), "total": df.height}


@router.post("", status_code=201)
async def create_strategy(body: StrategyCreateBody, catalog: CatalogDep) -> dict:
    """创建新策略配置，strategy_id 须唯一；已存在时返回 409。"""
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
    """更新策略配置，并自动保存版本快照（最多保留 5 个历史版本）。"""
    existing = catalog.query(
        "SELECT strategy_id, config_text, config_format FROM meta_strategy_configs WHERE strategy_id = ?",
        [strategy_id],
    )
    if existing.is_empty():
        raise HTTPException(status_code=404, detail=f"Strategy '{strategy_id}' not found")

    now = datetime.now(tz=timezone.utc).isoformat()
    parsed = _parse_config(body.config_text, body.config_format)
    if body.config_format == "json" and parsed is None:
        raise HTTPException(status_code=422, detail="config_text is not valid JSON")

    # 保存版本快照（保存当前的旧配置，不是新配置）
    _ensure_version_table(catalog)
    existing_row = existing.to_dicts()[0]
    version_id = f"v_{uuid.uuid4().hex[:10]}"
    old_parsed = _parse_config(existing_row["config_text"], existing_row["config_format"])
    summary = _generate_summary(old_parsed, existing_row["config_format"])
    catalog.execute(
        "INSERT INTO meta_strategy_versions (version_id, strategy_id, config_text, config_format, summary, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [version_id, strategy_id, existing_row["config_text"], existing_row["config_format"], summary, now],
    )

    # 滚动删除超出 MAX_VERSIONS 的旧版本
    old_versions = catalog.query(
        "SELECT version_id FROM meta_strategy_versions WHERE strategy_id = ? "
        "ORDER BY created_at DESC OFFSET ? LIMIT 100",
        [strategy_id, MAX_VERSIONS],
    )
    if not old_versions.is_empty():
        for row in old_versions.to_dicts():
            catalog.execute(
                "DELETE FROM meta_strategy_versions WHERE version_id = ?",
                [row["version_id"]],
            )

    # 更新主记录
    catalog.execute(
        """UPDATE meta_strategy_configs
           SET config_text = ?, config_format = ?, parsed_config = ?, updated_at = ?
           WHERE strategy_id = ?""",
        [body.config_text, body.config_format,
         json.dumps(parsed) if parsed else None, now, strategy_id],
    )
    return {"strategy_id": strategy_id, "status": "updated", "version_id": version_id, "summary": summary}


@router.get("/{strategy_id}/versions")
async def list_strategy_versions(strategy_id: str, catalog: CatalogDep) -> dict:
    """列出策略的历史版本（最近 MAX_VERSIONS 个）。"""
    _ensure_version_table(catalog)
    df = catalog.query(
        "SELECT version_id, strategy_id, config_text, config_format, summary, created_at "
        "FROM meta_strategy_versions WHERE strategy_id = ? "
        "ORDER BY created_at DESC LIMIT ?",
        [strategy_id, MAX_VERSIONS],
    )
    return {"items": df.to_dicts() if not df.is_empty() else [], "strategy_id": strategy_id}


@router.post("/{strategy_id}/rollback/{version_id}")
async def rollback_strategy(strategy_id: str, version_id: str, catalog: CatalogDep) -> dict:
    """回滚策略到指定历史版本（回滚本身也会创建新版本记录）。"""
    _ensure_version_table(catalog)
    version_df = catalog.query(
        "SELECT config_text, config_format FROM meta_strategy_versions "
        "WHERE version_id = ? AND strategy_id = ?",
        [version_id, strategy_id],
    )
    if version_df.is_empty():
        raise HTTPException(status_code=404, detail=f"Version '{version_id}' not found for strategy '{strategy_id}'")

    row = version_df.to_dicts()[0]
    body = StrategyUpdateBody(config_text=row["config_text"], config_format=row["config_format"])
    return await update_strategy(strategy_id, body, catalog)


@router.delete("/{strategy_id}")
async def delete_strategy(strategy_id: str, catalog: CatalogDep) -> dict:
    """删除策略配置。已关联的回测历史不受影响。"""
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


# ── Optimization report (human review required before applying) ────────────────

def _maybe_json(raw: str | dict | None) -> dict | None:
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(str(raw))
    except (TypeError, ValueError):
        return None


@router.get("/{strategy_id}/optimization-report")
async def get_optimization_report(strategy_id: str, catalog: CatalogDep) -> dict:
    """读取策略最新一次自动寻优报告（来自每周调度 StrategyOptimizationJob）。"""
    # Ensure table exists (created by optimizer job, but may not have run yet)
    catalog.execute(
        "CREATE TABLE IF NOT EXISTS gold_optimization_reports ("
        "strategy_id VARCHAR, generated_at TIMESTAMPTZ, status VARCHAR, reason VARCHAR, "
        "health_json JSON, best_params_json JSON, baseline_metrics_json JSON, "
        "candidate_metrics_json JSON, overfit_check_json JSON)"
    )
    df = catalog.query(
        "SELECT strategy_id, generated_at, status, reason, health_json, "
        "best_params_json, baseline_metrics_json, candidate_metrics_json, overfit_check_json "
        "FROM gold_optimization_reports WHERE strategy_id = ? "
        "ORDER BY generated_at DESC LIMIT 1",
        [strategy_id],
    )
    if df.is_empty():
        raise HTTPException(
            status_code=404,
            detail=f"No optimization report found for strategy '{strategy_id}'",
        )
    row = df.to_dicts()[0]
    return {
        "strategy_id": row["strategy_id"],
        "generated_at": str(row["generated_at"]),
        "status": row["status"],
        "reason": row["reason"],
        "health": _maybe_json(row["health_json"]),
        "best_params": _maybe_json(row["best_params_json"]),
        "baseline_metrics": _maybe_json(row["baseline_metrics_json"]),
        "candidate_metrics": _maybe_json(row["candidate_metrics_json"]),
        "overfit_check": _maybe_json(row["overfit_check_json"]),
    }


class ApplyOptimizationBody(BaseModel):
    best_params: dict
    confirm: bool = False
    baseline_run_id: str | None = None


@router.post("/{strategy_id}/apply-optimization")
async def apply_optimization(
    strategy_id: str, body: ApplyOptimizationBody, catalog: CatalogDep
) -> dict:
    """人工确认应用寻优新参数（安全红线：必须显式 confirm=true）。

    流程：
      1. 校验 confirm 标志 + 策略存在 + 最新报告处于 needs_review。
      2. 合并 best_params 进策略配置 → 走版本管理（旧版本快照可回滚）。
      3. 更新 baseline_run_id（显式传入或回退到报告/现有值）。
      4. 标记报告 status="applied"。
    """
    if not body.confirm:
        raise HTTPException(
            status_code=400,
            detail="Human confirmation required: set confirm=true to apply",
        )

    existing = catalog.query(
        "SELECT config_text, config_format FROM meta_strategy_configs "
        "WHERE strategy_id = ?",
        [strategy_id],
    )
    if existing.is_empty():
        raise HTTPException(status_code=404, detail=f"Strategy '{strategy_id}' not found")

    # 只允许应用最新且待审核的报告
    report_df = catalog.query(
        "SELECT status FROM gold_optimization_reports WHERE strategy_id = ? "
        "ORDER BY generated_at DESC LIMIT 1",
        [strategy_id],
    )
    if report_df.is_empty():
        raise HTTPException(
            status_code=404,
            detail=f"No optimization report found for strategy '{strategy_id}'",
        )
    latest_status = report_df["status"][0]
    if latest_status not in ("needs_review", "applied"):
        raise HTTPException(
            status_code=409,
            detail=f"Latest report status is '{latest_status}', not 'needs_review'",
        )

    # 合并参数到现有配置（保留未涉及的字段）
    row = existing.to_dicts()[0]
    parsed = _parse_config(row["config_text"], row["config_format"]) or {}
    parsed.update(body.best_params)
    new_config_text = json.dumps(parsed, ensure_ascii=False, indent=2)

    # 复用版本管理：PUT /strategies/{id} 会快照旧配置并可回滚
    update_body = StrategyUpdateBody(
        config_text=new_config_text, config_format="json"
    )
    update_result = await update_strategy(strategy_id, update_body, catalog)

    # 更新 baseline_run_id
    from cquant.scheduler.strategy_health import set_baseline_run_id

    baseline_run_id = body.baseline_run_id
    if baseline_run_id is None:
        current = parsed.get("baseline_run_id")
        if current:
            baseline_run_id = current
    if baseline_run_id:
        set_baseline_run_id(catalog, strategy_id, baseline_run_id)

    # 标记报告已应用
    catalog.execute(
        "UPDATE gold_optimization_reports SET status = 'applied' "
        "WHERE strategy_id = ? AND status = 'needs_review'",
        [strategy_id],
    )

    return {
        "strategy_id": strategy_id,
        "status": "applied",
        "version_id": update_result.get("version_id"),
        "applied_params": body.best_params,
        "baseline_run_id": baseline_run_id,
    }
