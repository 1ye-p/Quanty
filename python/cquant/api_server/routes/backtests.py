"""Backtest run routes."""

from __future__ import annotations

import asyncio
import json
import logging
import pathlib
import uuid
from datetime import date

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from cquant.api_server.deps import CatalogDep

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/backtests", tags=["backtests"])

# 任务注册表（in-memory，进程级别）
_JOB_REGISTRY: dict[str, dict] = {}


class BacktestCreateBody(BaseModel):
    strategy_id: str
    dataset_version: str
    start_date: str  # ISO date
    end_date: str  # ISO date
    top_n: int = 10
    sort_factor: str = "ret_20d"
    feature_set_version: str = ""


def _run_backtest(catalog, spec):
    """Run backtest in thread pool (CPU-bound)."""
    from cquant.backtest_vector.run import BacktestRunner

    runner = BacktestRunner(catalog)
    return runner.run(spec)


def _load_metrics(path: pathlib.Path) -> dict:
    """Load metrics JSON from an artifacts file (blocking I/O, run via to_thread)."""
    with open(path) as f:
        return json.load(f)


@router.post("", status_code=201)
async def create_backtest(
    body: BacktestCreateBody,
    background_tasks: BackgroundTasks,
    catalog: CatalogDep,
) -> dict:
    """触发回测，立即返回 job_id（后台异步执行）。"""
    # Look up strategy config to get top_n / sort_factor if not overridden
    strat_df = catalog.query(
        "SELECT parsed_config FROM meta_strategy_configs WHERE strategy_id = ?",
        [body.strategy_id],
    )
    if strat_df.is_empty():
        raise HTTPException(status_code=404, detail=f"Strategy '{body.strategy_id}' not found")

    parsed = json.loads(strat_df["parsed_config"].item()) if strat_df["parsed_config"].item() else {}

    # Use strategy config values as defaults, allow overrides from request body
    top_n = body.top_n if body.top_n != 10 else parsed.get("top_n", 10)
    sort_factor = body.sort_factor if body.sort_factor != "ret_20d" else (
        parsed.get("factors", ["ret_20d"])[0] if parsed.get("factors") else "ret_20d"
    )

    from cquant.backtest_vector.run import BacktestRunSpec

    try:
        start = date.fromisoformat(body.start_date)
        end = date.fromisoformat(body.end_date)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Invalid date format: {e}")

    # Auto-detect feature_set_version if not provided
    feature_set_version = body.feature_set_version
    if not feature_set_version:
        fsv_df = catalog.query(
            "SELECT feature_set_version FROM gold_factor_values "
            "GROUP BY feature_set_version ORDER BY MAX(trade_date) DESC LIMIT 1"
        )
        if not fsv_df.is_empty():
            feature_set_version = fsv_df["feature_set_version"].item()

    spec = BacktestRunSpec(
        dataset_version=body.dataset_version,
        strategy_id=body.strategy_id,
        start_date=start,
        end_date=end,
        feature_set_version=feature_set_version,
        top_n=top_n,
        sort_factor=sort_factor,
        tags=parsed.get("risk_limits", {}),
    )

    job_id = str(uuid.uuid4())
    _JOB_REGISTRY[job_id] = {"status": "running", "run_id": None, "error": None}

    def _run_job() -> None:
        try:
            run_id = _run_backtest(catalog, spec)
            _JOB_REGISTRY[job_id].update({"status": "completed", "run_id": run_id})
        except Exception as exc:
            logger.exception("Backtest job %s failed", job_id)
            _JOB_REGISTRY[job_id].update({"status": "failed", "error": str(exc)})

    background_tasks.add_task(_run_job)
    return {"job_id": job_id, "strategy_id": body.strategy_id, "status": "running"}


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str) -> dict:
    """查询回测任务运行状态。

    Returns {job_id, status: running|completed|failed, run_id: str|None, error: str|None}
    """
    job = _JOB_REGISTRY.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return {"job_id": job_id, **job}


@router.get("")
async def list_backtests(catalog: CatalogDep, limit: int = 50) -> dict:
    """List backtest runs."""
    df = catalog.query(
        "SELECT run_id, engine, strategy_id, dataset_version, started_at, "
        "completed_at, status FROM gold_backtest_runs ORDER BY started_at DESC LIMIT ?",
        [limit],
    )
    return {"items": df.to_dicts(), "total": df.height}


@router.get("/{run_id}")
async def get_backtest(run_id: str, catalog: CatalogDep) -> dict:
    """Get a specific backtest run with metrics."""
    df = catalog.query(
        "SELECT * FROM gold_backtest_runs WHERE run_id = ?", [run_id]
    )
    if df.is_empty():
        raise HTTPException(status_code=404, detail=f"Backtest run '{run_id}' not found")

    result = df.to_dicts()[0]

    # Load metrics from artifacts file (offload to thread to avoid blocking event loop)
    metrics_path = pathlib.Path("data/backtest_artifacts") / f"{run_id}.json"
    if metrics_path.exists():
        try:
            result["metrics"] = await asyncio.to_thread(_load_metrics, metrics_path)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load metrics for run %s: %s", run_id, e)
            result["metrics"] = {}
    else:
        result["metrics"] = {}

    return result


@router.post("/{run_id}/analyze")
async def trigger_analysis(
    run_id: str,
    background_tasks: BackgroundTasks,
    catalog: CatalogDep,
) -> dict:
    """触发指定回测的过拟合分析（后台异步执行）。

    分析结果写入 gold_bt_analysis_runs。
    通过 GET /backtests/{run_id}/analysis 查看结果。
    """
    # 验证回测存在且已完成
    df = catalog.query(
        "SELECT run_id, status FROM gold_backtest_runs WHERE run_id = ?", [run_id]
    )
    if df.is_empty():
        raise HTTPException(status_code=404, detail=f"Backtest run '{run_id}' not found")
    if df["status"][0] != "completed":
        raise HTTPException(status_code=422, detail="Only completed backtests can be analyzed")

    job_id = str(uuid.uuid4())
    _JOB_REGISTRY[job_id] = {"status": "running", "run_id": None, "error": None}

    def _run_analysis() -> None:
        try:
            from cquant.bt_analyzer.run import AnalysisRunner, AnalysisRunSpec
            runner = AnalysisRunner(catalog)
            analysis_id = runner.run(AnalysisRunSpec(backtest_run_id=run_id))
            _JOB_REGISTRY[job_id].update({"status": "completed", "run_id": analysis_id})
        except Exception as exc:
            logger.exception("Analysis job %s failed", job_id)
            _JOB_REGISTRY[job_id].update({"status": "failed", "error": str(exc)})

    background_tasks.add_task(_run_analysis)
    return {"job_id": job_id, "run_id": run_id, "status": "running"}


@router.get("/{run_id}/analysis")
async def get_backtest_analysis(run_id: str, catalog: CatalogDep) -> dict:
    """Get post-backtest analysis report for a run."""
    df = catalog.query(
        "SELECT * FROM gold_bt_analysis_runs WHERE backtest_run_id = ? "
        "ORDER BY created_at DESC LIMIT 1",
        [run_id],
    )
    if df.is_empty():
        raise HTTPException(status_code=404, detail=f"No analysis found for run '{run_id}'")
    return df.to_dicts()[0]


@router.get("/{run_id}/risk")
async def get_backtest_risk(run_id: str, catalog: CatalogDep, limit: int = 20) -> dict:
    """Get risk snapshots for a backtest run."""
    df = catalog.query(
        "SELECT * FROM gold_risk_snapshots WHERE run_id = ? "
        "ORDER BY snapshot_ts DESC LIMIT ?",
        [run_id, limit],
    )
    return {"items": df.to_dicts(), "total": df.height}


@router.get("/{run_id}/tearsheet")
async def get_tearsheet(run_id: str, catalog: CatalogDep) -> dict:
    """Portfolio returns time series for tearsheet rendering."""
    run_df = catalog.query(
        "SELECT run_id, engine, strategy_id, status FROM gold_backtest_runs WHERE run_id = ? LIMIT 1",
        [run_id],
    )
    if run_df.is_empty():
        raise HTTPException(status_code=404, detail=f"Backtest run '{run_id}' not found")

    analysis_df = catalog.query(
        "SELECT overall_overfit_score, psr, dsr, summary "
        "FROM gold_bt_analysis_runs WHERE backtest_run_id = ? ORDER BY created_at DESC LIMIT 1",
        [run_id],
    )
    analysis = analysis_df.to_dicts()[0] if not analysis_df.is_empty() else {}

    risk_df = catalog.query(
        "SELECT snapshot_ts, drawdown, gross_leverage, var_95 "
        "FROM gold_risk_snapshots WHERE run_id = ? ORDER BY snapshot_ts",
        [run_id],
    )

    snapshots_df = catalog.query(
        "SELECT trade_date, nav, cash, positions_count "
        "FROM gold_portfolio_snapshots WHERE run_id = ? ORDER BY trade_date",
        [run_id],
    )

    return {
        "run": run_df.to_dicts()[0],
        "analysis": analysis,
        "risk_series": risk_df.to_dicts(),
        "snapshots": snapshots_df.to_dicts() if not snapshots_df.is_empty() else [],
        "note": "portfolio_returns are not yet persisted; use risk_series for PnL approximation",
    }


@router.get("/{run_id}/validation-windows")
async def get_validation_windows(run_id: str, catalog: CatalogDep) -> dict:
    """Walk-forward and CPCV validation windows for overfitting analysis."""
    analysis_df = catalog.query(
        "SELECT analysis_run_id FROM gold_bt_analysis_runs WHERE backtest_run_id = ? "
        "ORDER BY created_at DESC LIMIT 1",
        [run_id],
    )
    if analysis_df.is_empty():
        raise HTTPException(status_code=404, detail=f"No analysis found for run '{run_id}'")

    analysis_run_id = analysis_df["analysis_run_id"].item()
    wf_df = catalog.query(
        "SELECT * FROM gold_bt_validation_windows WHERE analysis_run_id = ? AND method = 'walk_forward'",
        [analysis_run_id],
    )
    cpcv_df = catalog.query(
        "SELECT * FROM gold_bt_validation_windows WHERE analysis_run_id = ? AND method = 'cpcv'",
        [analysis_run_id],
    )
    return {"walk_forward": wf_df.to_dicts(), "cpcv": cpcv_df.to_dicts()}


@router.get("/{run_id}/multiple-testing")
async def get_multiple_testing(run_id: str, catalog: CatalogDep) -> dict:
    """Multiple hypothesis testing corrections."""
    analysis_df = catalog.query(
        "SELECT analysis_run_id FROM gold_bt_analysis_runs WHERE backtest_run_id = ? "
        "ORDER BY created_at DESC LIMIT 1",
        [run_id],
    )
    if analysis_df.is_empty():
        raise HTTPException(status_code=404, detail=f"No analysis found for run '{run_id}'")

    analysis_run_id = analysis_df["analysis_run_id"].item()
    mt_df = catalog.query(
        "SELECT method, n_trials, alpha, results_json, accepted "
        "FROM gold_bt_multiple_testing WHERE analysis_run_id = ?",
        [analysis_run_id],
    )
    return {m["method"]: m for m in mt_df.to_dicts()}


@router.get("/{run_id}/fills")
async def get_backtest_fills(run_id: str, catalog: CatalogDep, limit: int = 200) -> dict:
    """Get fill records for a backtest run."""
    df = catalog.query(
        "SELECT trade_date, asset_id, side, qty, price, notional, "
        "commission, stamp_duty, slippage, total_cost "
        "FROM gold_fills WHERE run_id = ? ORDER BY trade_date LIMIT ?",
        [run_id, limit],
    )
    return {"items": df.to_dicts(), "total": df.height}
