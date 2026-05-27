"""Backtest run routes."""

from __future__ import annotations

import asyncio
import json
import logging
import pathlib
import re
import uuid
from datetime import date, datetime, timezone

_ARTIFACTS_BASE = pathlib.Path("data/backtest_artifacts").resolve()
_UUID_RE = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')


def _safe_metrics_path(run_id: str) -> pathlib.Path | None:
    """Return path to metrics file only if run_id is a valid UUID and resolves within base dir."""
    if not _UUID_RE.match(run_id):
        return None
    p = (_ARTIFACTS_BASE / f"{run_id}.json").resolve()
    if not str(p).startswith(str(_ARTIFACTS_BASE)):
        return None
    return p

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


_schema_ensured = False


def _ensure_schema_extensions(catalog) -> None:
    """Add optional columns to gold_backtest_runs (idempotent, runs once per process)."""
    global _schema_ensured
    if _schema_ensured:
        return
    try:
        catalog.execute(
            "ALTER TABLE gold_backtest_runs ADD COLUMN IF NOT EXISTS benchmark_asset_id VARCHAR DEFAULT ''"
        )
    except Exception as exc:
        logger.debug("_ensure_schema_extensions: %s", exc)
    _schema_ensured = True


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
    # CustomWeightStrategy params
    custom_weights: dict[str, float] | None = None
    # Universe filtering
    universe_id: str = "all"
    # Benchmark
    benchmark_asset_id: str = ""
    # Cross-sectional scoring integration
    scoring_run_id: str = ""  # if set, use pre-computed scores as ranking signal


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
    custom_weights = body.custom_weights or parsed.get("custom_weights", {}) or {}
    universe_id = body.universe_id if body.universe_id != "all" else parsed.get("universe_id", "all")

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

    # Scoring run 校验 + 日期范围截断
    scoring_date_warning: str = ""
    if body.scoring_run_id:
        try:
            scoring_meta = catalog.query(
                "SELECT start_date, end_date, status FROM meta_scoring_runs WHERE run_id = ?",
                [body.scoring_run_id],
            )
            if scoring_meta.is_empty():
                raise HTTPException(
                    status_code=404,
                    detail=f"打分任务 '{body.scoring_run_id}' 不存在",
                )
            scoring_status = scoring_meta["status"][0]
            if scoring_status != "completed":
                raise HTTPException(
                    status_code=422,
                    detail=f"打分任务 '{body.scoring_run_id}' 尚未完成（当前状态: {scoring_status}），"
                           f"请等待打分完成后再提交回测",
                )
            s_start = str(scoring_meta["start_date"].item()).split()[0]
            s_end = str(scoring_meta["end_date"].item()).split()[0]
            bt_start = body.start_date
            bt_end = body.end_date
            effective_start = max(bt_start, s_start)
            effective_end = min(bt_end, s_end)
            if effective_start > effective_end:
                raise HTTPException(
                    status_code=400,
                    detail=f"回测日期范围 ({bt_start}~{bt_end}) 与打分结果范围 ({s_start}~{s_end}) 无交集",
                )
            if effective_start != bt_start or effective_end != bt_end:
                scoring_date_warning = (
                    f"回测范围已截断为 {effective_start}~{effective_end}（受打分数据范围限制）"
                )
                body = body.model_copy(update={
                    "start_date": effective_start,
                    "end_date": effective_end,
                })
                # Re-parse start/end so BacktestRunSpec receives truncated dates
                start = date.fromisoformat(effective_start)
                end = date.fromisoformat(effective_end)
        except HTTPException:
            raise
        except Exception as e:
            logger.warning("Failed to check scoring date range: %s", e)

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
        custom_weights=custom_weights,
        universe_id=universe_id,
        benchmark_asset_id=body.benchmark_asset_id,
        scoring_run_id=body.scoring_run_id,
    )

    _ensure_schema_extensions(catalog)
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
    return {"job_id": job_id, "strategy_id": body.strategy_id, "status": "running", "warning": scoring_date_warning}


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


@router.get("/compare")
async def compare_backtests(run_ids: str, catalog: CatalogDep) -> dict:
    """批量获取多个回测的关键指标和净值曲线，用于横向对比。

    Args:
        run_ids: 逗号分隔的 run_id，最多 6 个
    """
    ids = [r.strip() for r in run_ids.split(",") if r.strip()]
    if not ids:
        raise HTTPException(status_code=400, detail="run_ids 不能为空")
    if len(ids) > 6:
        raise HTTPException(status_code=400, detail="最多同时对比 6 个回测")

    # 批量查询所有 run 的元数据 — 1 次 DB 查询
    in_ph = ",".join(["?" for _ in ids])
    runs_df = catalog.query(
        f"SELECT run_id, strategy_id, engine, status, started_at, dataset_version "
        f"FROM gold_backtest_runs WHERE run_id IN ({in_ph})",
        ids,
    )
    runs_by_id = {r["run_id"]: r for r in runs_df.to_dicts()}

    # 批量查询所有 run 的净值快照 — 1 次 DB 查询
    snaps_df = catalog.query(
        f"SELECT run_id, trade_date, nav FROM gold_portfolio_snapshots "
        f"WHERE run_id IN ({in_ph}) ORDER BY run_id, trade_date",
        ids,
    )
    snaps_by_run: dict[str, list[dict]] = {}
    for row in snaps_df.to_dicts():
        snaps_by_run.setdefault(row["run_id"], []).append(
            {"date": str(row["trade_date"]), "nav": float(row["nav"])}
        )

    # 从磁盘加载指标（无法批量，但是纯 I/O）
    results = []
    for run_id in ids:
        run_info = runs_by_id.get(run_id)
        if not run_info:
            continue

        metrics: dict = {}
        metrics_path = _safe_metrics_path(run_id)
        if metrics_path and metrics_path.exists():
            try:
                metrics = json.loads(metrics_path.read_text())
            except Exception:
                pass

        results.append({
            "run_id": run_id,
            "strategy_id": run_info.get("strategy_id", ""),
            "engine": run_info.get("engine", ""),
            "status": run_info.get("status", ""),
            "started_at": str(run_info.get("started_at", "")),
            "dataset_version": run_info.get("dataset_version", ""),
            "metrics": metrics,
            "nav_series": snaps_by_run.get(run_id, []),
        })

    return {"runs": results}


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
    metrics_path = _safe_metrics_path(run_id)
    if metrics_path and metrics_path.exists():
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

    # Load benchmark NAV series
    benchmark_nav: list[dict] = []
    benchmark_asset_id = ""
    try:
        run_meta = catalog.query(
            "SELECT benchmark_asset_id, started_at, completed_at "
            "FROM gold_backtest_runs WHERE run_id = ?",
            [run_id],
        )
        if not run_meta.is_empty():
            row = run_meta.to_dicts()[0]
            benchmark_asset_id = row.get("benchmark_asset_id") or ""
            if benchmark_asset_id and not snapshots_df.is_empty():
                dates = snapshots_df["trade_date"].to_list()
                start_d = str(min(dates))
                end_d = str(max(dates))
                bm_df = catalog.query(
                    "SELECT trade_date, close FROM silver_prices_1d "
                    "WHERE asset_id = ? AND trade_date >= ? AND trade_date <= ? "
                    "ORDER BY trade_date",
                    [benchmark_asset_id, start_d, end_d],
                )
                if not bm_df.is_empty():
                    first_close = float(bm_df["close"][0])
                    if first_close > 0:
                        benchmark_nav = [
                            {
                                "date": str(r["trade_date"]),
                                "nav": float(r["close"]) / first_close,
                            }
                            for r in bm_df.to_dicts()
                        ]
    except Exception as e:
        logger.warning("Failed to load benchmark NAV for %s: %s", run_id, e)

    return {
        "run": run_df.to_dicts()[0],
        "analysis": analysis,
        "risk_series": risk_df.to_dicts(),
        "snapshots": snapshots_df.to_dicts() if not snapshots_df.is_empty() else [],
        "note": "portfolio_returns are not yet persisted; use risk_series for PnL approximation",
        "benchmark_asset_id": benchmark_asset_id,
        "benchmark_nav": benchmark_nav,
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
        metrics_path = _safe_metrics_path(row["fold_run_id"])
        if metrics_path and metrics_path.exists():
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
