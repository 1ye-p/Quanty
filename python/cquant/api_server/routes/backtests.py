"""Backtest run routes."""

from __future__ import annotations

import asyncio
import json
import logging
import pathlib
import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from cquant.api_server.deps import CatalogDep

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/backtests", tags=["backtests"])

# ── Job persistence (DuckDB-backed) ──────────────────────────────────────────

_JOB_DDL = """
CREATE TABLE IF NOT EXISTS _api_jobs (
    job_id     VARCHAR PRIMARY KEY,
    job_type   VARCHAR NOT NULL DEFAULT 'backtest',
    status     VARCHAR NOT NULL DEFAULT 'running',
    run_id     VARCHAR,
    error      VARCHAR,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
)
"""


def _ensure_job_table(catalog) -> None:
    """Create the _api_jobs table if it doesn't exist."""
    try:
        catalog.execute(_JOB_DDL)
    except Exception as exc:
        logger.debug("_ensure_job_table: %s (likely already exists)", exc)


def _save_job(catalog, job_id: str, job_type: str, status: str,
              run_id: str | None = None, error: str | None = None) -> None:
    """Insert or update a job record in DuckDB. Preserves created_at on updates."""
    now = datetime.now(tz=timezone.utc).isoformat()
    try:
        catalog.execute(
            "INSERT INTO _api_jobs "
            "(job_id, job_type, status, run_id, error, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (job_id) DO UPDATE SET "
            "status = excluded.status, run_id = excluded.run_id, "
            "error = excluded.error, created_at = _api_jobs.created_at, "
            "updated_at = excluded.updated_at",
            [job_id, job_type, status, run_id, error, now, now],
        )
    except Exception as exc:
        logger.warning("Failed to persist job %s: %s", job_id, exc)


def _load_job(catalog, job_id: str) -> dict | None:
    """Load a job record from DuckDB. Returns None if not found."""
    try:
        df = catalog.query(
            "SELECT job_id, job_type, status, run_id, error FROM _api_jobs WHERE job_id = ?",
            [job_id],
        )
        if df.is_empty():
            return None
        row = df.to_dicts()[0]
        return {
            "status": row["status"],
            "run_id": row["run_id"],
            "error": row["error"],
        }
    except Exception:
        return None


from cquant.api_server.schemas.common import WalkForwardConfig


class BacktestCreateBody(BaseModel):
    strategy_id: str
    dataset_version: str
    start_date: str  # ISO date
    end_date: str  # ISO date
    top_n: int = 10
    sort_factor: str = "ret_20d"
    feature_set_version: str = ""
    # ML strategy support
    strategy_type: str = "StaticTopN"  # "StaticTopN" | "MLModelStrategy" | "MultiFactor" | "MarketNeutral" | "SectorRotation" | "Combo"
    model_version: str = ""  # required when strategy_type == "MLModelStrategy"
    label_name: str = "ret_5d"  # prediction label for MLModelStrategy
    # Dataset split (OOS)
    train_end_date: str = ""  # if set, backtest only runs on data after this date (OOS)
    # Walk-forward config (optional)
    walk_forward: WalkForwardConfig | None = None
    eval_mode: str | None = None  # "train" | "valid" | "test" | "all"
    # MarketNeutral params
    short_n: int = 10
    # SectorRotation params
    sector_map: dict[str, str] = {}
    top_sectors: int = 3
    top_n_per_sector: int = 3
    # Combo params
    sub_strategy_configs: list[dict] = []
    combo_method: str = "equal_weight"


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

    # ML strategy params: read from strategy config first, then request body
    strategy_type = body.strategy_type if body.strategy_type != "StaticTopN" else parsed.get("strategy_type", "StaticTopN")
    model_version = body.model_version or parsed.get("model_id", "")
    label_name = body.label_name if body.label_name != "ret_5d" else parsed.get("label_name", "ret_5d")

    # MarketNeutral / SectorRotation / Combo params
    short_n = body.short_n if body.short_n != 10 else parsed.get("short_n", 10)
    sector_map = body.sector_map or parsed.get("sector_map", {})
    top_sectors = body.top_sectors if body.top_sectors != 3 else parsed.get("top_sectors", 3)
    top_n_per_sector = body.top_n_per_sector if body.top_n_per_sector != 3 else parsed.get("top_n_per_sector", 3)
    sub_strategy_configs = body.sub_strategy_configs or parsed.get("sub_strategy_configs", [])
    combo_method = body.combo_method if body.combo_method != "equal_weight" else parsed.get("combo_method", "equal_weight")

    from cquant.backtest_vector.run import BacktestRunSpec

    try:
        start = date.fromisoformat(body.start_date)
        end = date.fromisoformat(body.end_date)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Invalid date format: {e}")

    # OOS split: if train_end_date is set, adjust backtest start to next day
    if body.train_end_date:
        try:
            train_end = date.fromisoformat(body.train_end_date)
            oos_start = date.fromordinal(train_end.toordinal() + 1)
            if oos_start > start:
                start = oos_start
                logger.info("OOS split: adjusted start_date to %s (train_end_date=%s)", start, train_end)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=f"Invalid train_end_date format: {e}")

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
        strategy_type=strategy_type,
        model_version=model_version,
        label_name=label_name,
        eval_mode=body.eval_mode,
        walk_forward=body.walk_forward,
        short_n=short_n,
        sector_map=sector_map,
        top_sectors=top_sectors,
        top_n_per_sector=top_n_per_sector,
        sub_strategy_configs=sub_strategy_configs,
        combo_method=combo_method,
    )

    _ensure_job_table(catalog)
    job_id = str(uuid.uuid4())
    _save_job(catalog, job_id, job_type="backtest", status="running")

    def _run_job() -> None:
        try:
            run_id = _run_backtest(catalog, spec)
            _save_job(catalog, job_id, "backtest", "completed", run_id=run_id)
        except Exception as exc:
            logger.exception("Backtest job %s failed", job_id)
            _save_job(catalog, job_id, "backtest", "failed", error=f"Backtest failed: {str(exc)[:200]}")

    background_tasks.add_task(_run_job)
    return {"job_id": job_id, "strategy_id": body.strategy_id, "status": "running"}


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str, catalog: CatalogDep) -> dict:
    """查询回测任务运行状态。

    Returns {job_id, status: running|completed|failed, run_id: str|None, error: str|None}
    """
    _ensure_job_table(catalog)
    job = _load_job(catalog, job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return {"job_id": job_id, **job}


@router.get("")
async def list_backtests(catalog: CatalogDep, offset: int = 0, limit: int = 50) -> dict:
    """List backtest runs."""
    total_df = catalog.query("SELECT COUNT(*) as cnt FROM gold_backtest_runs")
    total = total_df["cnt"].item() if not total_df.is_empty() else 0
    df = catalog.query(
        "SELECT run_id, engine, strategy_id, dataset_version, started_at, "
        "completed_at, status FROM gold_backtest_runs ORDER BY started_at DESC LIMIT ? OFFSET ?",
        [limit, offset],
    )
    return {"items": df.to_dicts(), "total": total}


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

    _ensure_job_table(catalog)
    job_id = str(uuid.uuid4())
    _save_job(catalog, job_id, job_type="analysis", status="running")

    def _run_analysis() -> None:
        try:
            from cquant.bt_analyzer.run import AnalysisRunner, AnalysisRunSpec
            runner = AnalysisRunner(catalog)
            analysis_id = runner.run(AnalysisRunSpec(backtest_run_id=run_id))
            _save_job(catalog, job_id, "analysis", "completed", run_id=analysis_id)
        except Exception as exc:
            logger.exception("Analysis job %s failed", job_id)
            _save_job(catalog, job_id, "analysis", "failed", error=f"Analysis failed: {str(exc)[:200]}")

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


@router.get("/{run_id}/walk-forward-folds")
async def get_walk_forward_folds(run_id: str, catalog: CatalogDep) -> dict:
    """Get walk-forward fold details for a run."""
    run_df = catalog.query(
        "SELECT is_walk_forward, aggregated_metrics_json FROM gold_backtest_runs WHERE run_id = ?",
        [run_id],
    )
    if run_df.is_empty():
        raise HTTPException(status_code=404, detail=f"Backtest run '{run_id}' not found")

    run = run_df.to_dicts()[0]
    if not run.get("is_walk_forward"):
        raise HTTPException(status_code=400, detail="This run is not a walk-forward backtest")

    folds_df = catalog.query(
        "SELECT * FROM gold_wf_folds WHERE run_id = ? ORDER BY fold_id",
        [run_id],
    )

    folds = []
    for row in folds_df.to_dicts():
        fold_metrics = {}
        metrics_path = pathlib.Path("data/backtest_artifacts") / f"{row['fold_run_id']}.json"
        if metrics_path.exists():
            try:
                fold_metrics = json.loads(metrics_path.read_text())
            except Exception:
                pass
        folds.append({**row, "metrics": fold_metrics})

    aggregated = {}
    if run.get("aggregated_metrics_json"):
        try:
            aggregated = json.loads(run["aggregated_metrics_json"])
        except Exception:
            pass

    return {
        "run_id": run_id,
        "n_folds": len(folds),
        "folds": folds,
        "aggregated": aggregated,
    }
