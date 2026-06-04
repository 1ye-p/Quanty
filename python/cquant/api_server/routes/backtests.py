"""Backtest run routes."""

from __future__ import annotations

import asyncio
import json
import logging
import pathlib
import re
import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from cquant.api_server.deps import CatalogDep

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

def _fmt_metric(key: str, value: float | None) -> dict:
    """格式化单个指标为模板友好的 dict。

    Tuple format: (label, is_pct, invert)
    invert=True: higher value is worse (e.g. volatility, drawdown) — always show as "negative" class.
    invert=False: higher is better — positive=green, negative=red.
    """
    METRIC_LABELS: dict[str, tuple[str, bool, bool]] = {
        "total_return":       ("总收益率",         True,  False),
        "annualized_return":  ("年化收益",          True,  False),
        "cagr":               ("年化收益（CAGR）",   True,  False),
        "sharpe_ratio":       ("Sharpe Ratio",     False, False),
        "sortino_ratio":      ("Sortino Ratio",    False, False),
        "calmar_ratio":       ("Calmar Ratio",     False, False),
        "win_rate":           ("胜率",              True,  False),
        "max_drawdown":       ("最大回撤",          True,  True),   # always bad
        "annualized_volatility": ("年化波动率",         True,  True),   # always bad
        "information_ratio":  ("信息比率（IR）",      False, False),
        "tracking_error":     ("跟踪误差（TE）",      True,  True),   # always bad
        "alpha":              ("超额收益 Alpha",     True,  False),
        "beta":               ("Beta",              False, False),
    }
    label, is_pct, invert = METRIC_LABELS.get(key, (key, False, False))
    if value is None:
        return {"label": label, "value": "—", "cls": ""}
    display = f"{value * 100:.2f}%" if is_pct else f"{value:.3f}"
    if value == 0:
        cls = ""
    elif invert:
        cls = "negative"          # high value = bad for these metrics
    else:
        cls = "positive" if value > 0 else "negative"
    return {"label": label, "value": display, "cls": cls}


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
            # Auto-trigger overfitting analysis after successful backtest
            try:
                from cquant.bt_analyzer.run import AnalysisRunner, AnalysisRunSpec
                runner = AnalysisRunner(catalog)
                runner.run(AnalysisRunSpec(backtest_run_id=run_id))
                logger.info("Auto-analysis completed for run %s", run_id)
            except Exception as analysis_exc:
                logger.warning("Auto-analysis failed for run %s: %s", run_id, analysis_exc)
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
    """List backtest runs, including in-flight jobs from _api_jobs."""
    _ensure_job_table(catalog)

    # 1. Normal backtest list from gold_backtest_runs
    total_df = catalog.query("SELECT COUNT(*) as cnt FROM gold_backtest_runs")
    total = total_df["cnt"].item() if not total_df.is_empty() else 0
    df = catalog.query(
        "SELECT run_id, engine, strategy_id, dataset_version, started_at, "
        "completed_at, status FROM gold_backtest_runs ORDER BY started_at DESC LIMIT ? OFFSET ?",
        [limit, offset],
    )
    items = df.to_dicts()

    # 2. Running/pending jobs from _api_jobs (always count for total; merge items only on first page)
    running_df = catalog.query(
        "SELECT job_id, status, created_at, error, run_id "
        "FROM _api_jobs "
        "WHERE job_type = 'backtest' AND status IN ('running', 'pending')"
    )
    running_rows = running_df.to_dicts() if not running_df.is_empty() else []
    if offset == 0 and running_rows:
        existing_run_ids = {item.get("run_id") for item in items}
        for row in running_rows:
            if row.get("run_id") and row["run_id"] in existing_run_ids:
                continue
            items.insert(0, {
                "run_id": row.get("run_id") or row["job_id"],
                "engine": "",
                "strategy_id": "",
                "dataset_version": "",
                "started_at": row.get("created_at", ""),
                "completed_at": None,
                "status": row["status"],
                "error": row.get("error"),
                "is_running_job": True,  # W-3: flag for frontend to disable detail navigation
            })
    total += len(running_rows)

    return {"items": items, "total": total}


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


@router.get("/best-recent")
async def best_recent_backtest(catalog: CatalogDep, days: int = 7) -> dict:
    """返回最近 N 天 Sharpe 最高的已完成回测摘要（用于 Dashboard）。"""
    days = max(1, min(365, int(days)))

    cutoff = f"CURRENT_DATE - INTERVAL '{days} days'"
    df = catalog.query(
        f"SELECT run_id, strategy_id, started_at FROM gold_backtest_runs "
        f"WHERE status = 'completed' AND started_at >= {cutoff} "
        f"ORDER BY started_at DESC LIMIT 20"
    )
    if df.is_empty():
        return {"run_id": None, "strategy_id": None, "sharpe": None, "max_drawdown": None, "cagr": None}

    best = None
    best_sharpe = float('-inf')
    for row in df.to_dicts():
        mpath = _safe_metrics_path(row["run_id"])
        if not mpath or not mpath.exists():
            continue
        try:
            m = json.loads(mpath.read_text())
        except Exception:
            continue
        s = m.get("sharpe_ratio")
        if s is not None and float(s) > best_sharpe:
            best_sharpe = float(s)
            best = {
                "run_id": row["run_id"],
                "strategy_id": row["strategy_id"],
                "sharpe": round(float(s), 3),
                "max_drawdown": round(float(m.get("max_drawdown") or 0) * 100, 2),
                "cagr": round(float(m.get("cagr") or 0) * 100, 2),
            }

    return best or {"run_id": None, "strategy_id": None, "sharpe": None, "max_drawdown": None, "cagr": None}


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


@router.get("/{run_id}/risk-rolling")
async def get_risk_rolling(
    run_id: str,
    catalog: CatalogDep,
    window: int = Query(default=60, ge=1, le=504),
) -> dict:
    """Get rolling risk metrics for a backtest run."""
    df = catalog.query(
        'SELECT trade_date, "window", '
        "rolling_var AS var_95, rolling_cvar AS cvar_95, "
        "rolling_vol AS volatility, rolling_sharpe AS sharpe_ratio, "
        'rolling_beta AS beta '
        'FROM gold_risk_rolling WHERE run_id = ? AND "window" = ? ORDER BY trade_date',
        [run_id, window],
    )
    if df.is_empty():
        raise HTTPException(status_code=404, detail=f"No rolling risk data for run '{run_id}'")
    return {
        "run_id": run_id,
        "window": window,
        "data": df.to_dicts(),
    }


@router.get("/{run_id}/drawdowns")
async def get_drawdowns(
    run_id: str,
    catalog: CatalogDep,
) -> dict:
    """Get drawdown periods for a backtest run."""
    df = catalog.query(
        "SELECT * FROM gold_drawdown_periods WHERE run_id = ? ORDER BY period_id",
        [run_id],
    )
    if df.is_empty():
        return {"run_id": run_id, "periods": []}
    return {
        "run_id": run_id,
        "periods": df.to_dicts(),
    }


@router.get("/{run_id}/drawdown-timeseries")
async def get_drawdown_timeseries(
    run_id: str,
    catalog: CatalogDep,
) -> dict:
    """Get daily underwater drawdown values for charting."""
    df = catalog.query(
        "SELECT trade_date, portfolio_return FROM gold_portfolio_returns "
        "WHERE run_id = ? ORDER BY trade_date",
        [run_id],
    )
    if df.is_empty():
        raise HTTPException(status_code=404, detail=f"No return data for run '{run_id}'")

    returns = df["portfolio_return"].to_list()
    dates = df["trade_date"].to_list()
    nav = 1.0
    peak = 1.0
    data = []
    for i, r in enumerate(returns):
        nav *= (1 + r)
        peak = max(peak, nav)
        dd = (nav - peak) / peak if peak > 0 else 0.0
        data.append({"trade_date": str(dates[i]), "drawdown": dd})

    return {"run_id": run_id, "data": data}


@router.get("/{run_id}/return-distribution")
async def get_return_distribution(
    run_id: str,
    catalog: CatalogDep,
    bins: int = Query(default=50, ge=2, le=1000),
) -> dict:
    """Get return distribution histogram data for a backtest run."""
    import numpy as np

    df = catalog.query(
        "SELECT portfolio_return FROM gold_portfolio_returns WHERE run_id = ? ORDER BY trade_date",
        [run_id],
    )
    if df.is_empty():
        raise HTTPException(status_code=404, detail=f"No return data for run '{run_id}'")

    returns = df["portfolio_return"].to_numpy()
    counts, bin_edges = np.histogram(returns, bins=bins)

    data = []
    for i in range(len(counts)):
        data.append({
            "bin_start": float(bin_edges[i]),
            "bin_end": float(bin_edges[i + 1]),
            "count": int(counts[i]),
            "bin_label": f"{bin_edges[i]:.3f}",
        })

    return {
        "run_id": run_id,
        "bins": bins,
        "data": data,
        "stats": {
            "mean": float(np.mean(returns)),
            "std": float(np.std(returns)),
            "skewness": float(np.mean(((returns - np.mean(returns)) / np.std(returns)) ** 3)) if np.std(returns) > 0 else 0.0,
            "kurtosis": float(np.mean(((returns - np.mean(returns)) / np.std(returns)) ** 4)) if np.std(returns) > 0 else 0.0,
            "min": float(np.min(returns)),
            "max": float(np.max(returns)),
        },
    }


def _fetch_position_prices(catalog, run_id: str) -> tuple[list[str], "pd.DataFrame"]:
    """Fetch asset IDs and price data for a backtest run.

    Returns (asset_ids, pandas DataFrame with trade_date, asset_id, close).
    Raises HTTPException on missing data.
    """
    import pandas as pd

    pos_df = catalog.query(
        "SELECT DISTINCT asset_id FROM gold_positions WHERE run_id = ?",
        [run_id],
    )
    if pos_df.is_empty():
        raise HTTPException(status_code=404, detail=f"No positions found for run '{run_id}'")
    asset_ids = pos_df["asset_id"].to_list()

    snap_df = catalog.query(
        "SELECT MIN(trade_date) as start_date, MAX(trade_date) as end_date "
        "FROM gold_portfolio_snapshots WHERE run_id = ?",
        [run_id],
    )
    if snap_df.is_empty():
        raise HTTPException(status_code=404, detail=f"No snapshots for run '{run_id}'")
    start_date = str(snap_df["start_date"].item()).split()[0]
    end_date = str(snap_df["end_date"].item()).split()[0]

    asset_ph = ",".join(["?" for _ in asset_ids])
    price_df = catalog.query(
        f"SELECT trade_date, asset_id, close FROM silver_prices_1d "
        f"WHERE asset_id IN ({asset_ph}) AND trade_date >= ? AND trade_date <= ? "
        f"ORDER BY trade_date",
        asset_ids + [start_date, end_date],
    )
    if price_df.is_empty():
        raise HTTPException(status_code=404, detail="No price data available")

    return asset_ids, price_df.to_pandas()


@router.get("/{run_id}/correlation")
async def get_correlation_matrix(
    run_id: str,
    catalog: CatalogDep,
    window: int = Query(default=60, ge=2, le=504),
) -> dict:
    """Get asset correlation matrix for a backtest run."""
    from cquant.backtest_vector.risk_analysis import compute_correlation_matrix

    _, pdf = _fetch_position_prices(catalog, run_id)
    return compute_correlation_matrix(pdf, window=window)


@router.get("/{run_id}/factor-exposure")
async def get_factor_exposure(
    run_id: str,
    catalog: CatalogDep,
    window: int = Query(default=20, ge=5, le=120),
) -> dict:
    """Get factor exposure time series for a backtest run."""
    from cquant.backtest_vector.risk_analysis import compute_factor_exposures

    _, pdf = _fetch_position_prices(catalog, run_id)
    return compute_factor_exposures(pdf, window=window)


@router.get("/{run_id}/stress-test")
async def get_stress_test(run_id: str, catalog: CatalogDep) -> dict:
    """Run stress test scenarios on a backtest run."""
    from cquant.backtest_vector.risk_analysis import run_stress_test

    # Get portfolio returns
    ret_df = catalog.query(
        "SELECT portfolio_return FROM gold_portfolio_returns WHERE run_id = ? ORDER BY trade_date",
        [run_id],
    )
    if ret_df.is_empty():
        raise HTTPException(status_code=404, detail=f"No return data for run '{run_id}'")

    returns = ret_df["portfolio_return"].to_numpy()

    # Get NAV series
    snap_df = catalog.query(
        "SELECT nav FROM gold_portfolio_snapshots WHERE run_id = ? ORDER BY trade_date",
        [run_id],
    )
    nav_series = snap_df["nav"].to_numpy() if not snap_df.is_empty() else None

    result = run_stress_test(returns, nav_series=nav_series)
    return result


@router.get("/{run_id}/risk-contribution")
async def get_risk_contribution(
    run_id: str,
    catalog: CatalogDep,
    window: int = Query(default=60, ge=2, le=504),
) -> dict:
    """Get risk contribution by asset for a backtest run."""
    from cquant.backtest_vector.risk_analysis import compute_risk_contribution

    # Get latest positions with weights
    pos_df = catalog.query(
        "SELECT asset_id, weight FROM gold_positions WHERE run_id = ? "
        "AND trade_date = (SELECT MAX(trade_date) FROM gold_positions WHERE run_id = ?)",
        [run_id, run_id],
    )
    if pos_df.is_empty():
        raise HTTPException(status_code=404, detail=f"No positions found for run '{run_id}'")

    weights = {row["asset_id"]: float(row["weight"]) for row in pos_df.to_dicts()}

    _, pdf = _fetch_position_prices(catalog, run_id)
    return compute_risk_contribution(weights, pdf, window=window)


@router.get("/{run_id}/tca")
async def get_backtest_tca(run_id: str, catalog: CatalogDep) -> dict:
    """Get TCA for a backtest run."""
    df = catalog.query(
        "SELECT * FROM gold_bt_tca WHERE analysis_run_id IN "
        "(SELECT analysis_run_id FROM gold_bt_analysis_runs WHERE backtest_run_id = ? "
        "ORDER BY created_at DESC LIMIT 1)",
        [run_id],
    )
    if df.is_empty():
        raise HTTPException(status_code=404, detail=f"No TCA data for run '{run_id}'")
    return df.to_dicts()[0]


@router.get("/{run_id}/attribution")
async def get_backtest_attribution(run_id: str, catalog: CatalogDep) -> dict:
    """Get Brinson attribution for a backtest run."""
    df = catalog.query(
        "SELECT * FROM gold_bt_attribution WHERE analysis_run_id IN "
        "(SELECT analysis_run_id FROM gold_bt_analysis_runs WHERE backtest_run_id = ? "
        "ORDER BY created_at DESC LIMIT 1)",
        [run_id],
    )
    if df.is_empty():
        raise HTTPException(status_code=404, detail=f"No attribution data for run '{run_id}'")
    row = df.to_dicts()[0]
    if row.get("daily_json"):
        row["daily"] = json.loads(row.pop("daily_json"))
    else:
        row["daily"] = []
        row.pop("daily_json", None)
    if row.get("sector_details_json"):
        row["sector_details"] = json.loads(row.pop("sector_details_json"))
    else:
        row["sector_details"] = {}
        row.pop("sector_details_json", None)
    return row


# ── HTML Report SVG helpers ───────────────────────────────────────────────────

def _nav_to_svg(
    nav_dates: list[str],
    nav_values: list[float],
    bm_values: list[float] | None = None,
    width: int = 900,
    height: int = 320,
) -> str:
    """Render NAV + optional benchmark as an inline SVG (no external dependencies)."""
    if not nav_values:
        return '<p style="text-align:center;color:#94a3b8;padding:40px">暂无净值数据</p>'
    PL, PR, PT, PB = 62, 20, 20, 32
    cw, ch = width - PL - PR, height - PT - PB
    all_vals = list(nav_values) + (list(bm_values) if bm_values else [])
    lo, hi = min(all_vals), max(all_vals)
    rng = (hi - lo) or 0.01
    n = len(nav_values)

    def px(i: int, total: int = 0) -> float:
        return PL + i * cw / max((total or n) - 1, 1)

    def py(v: float) -> float:
        return PT + ch - (v - lo) / rng * ch

    def polyline(vals: list[float], total: int = 0) -> str:
        return " ".join(f"{px(i, total):.1f},{py(v):.1f}" for i, v in enumerate(vals))

    parts: list[str] = [
        f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto">',
        f'<rect x="{PL}" y="{PT}" width="{cw}" height="{ch}" fill="#f8fafc" rx="4"/>',
    ]
    # Y grid + labels
    for t in range(5):
        frac = t / 4
        v = lo + frac * rng
        y = PT + ch * (1 - frac)
        parts += [
            f'<line x1="{PL}" y1="{y:.0f}" x2="{PL + cw}" y2="{y:.0f}" stroke="#e2e8f0" stroke-dasharray="3,3"/>',
            f'<text x="{PL - 6}" y="{y + 4:.0f}" text-anchor="end" font-size="10" fill="#94a3b8">{v:.3f}</text>',
        ]
    # X labels (up to 6)
    x_step = max(1, n // 6)
    for i in range(0, n, x_step):
        lbl = nav_dates[i][:7] if len(nav_dates[i]) >= 7 else nav_dates[i]
        parts.append(f'<text x="{px(i):.0f}" y="{height - 4}" text-anchor="middle" font-size="10" fill="#94a3b8">{lbl}</text>')
    # Benchmark
    if bm_values:
        parts.append(f'<polyline points="{polyline(bm_values, len(bm_values))}" fill="none" stroke="#94a3b8" stroke-width="1.5" stroke-dasharray="5,3"/>')
    # Area fill — use chart bottom (py(lo)) so polygon is always inside the viewBox
    # Using py(max(lo, 1.0)) would break when all values < 1.0 (yields negative Y)
    base_y = float(PT + ch)
    pts = polyline(nav_values)
    parts.append(f'<polygon points="{PL:.0f},{base_y:.0f} {pts} {PL + cw:.0f},{base_y:.0f}" fill="rgba(37,99,235,0.07)"/>')
    # Line
    parts.append(f'<polyline points="{pts}" fill="none" stroke="#2563eb" stroke-width="2" stroke-linejoin="round"/>')
    # Axes
    parts += [
        f'<line x1="{PL}" y1="{PT}" x2="{PL}" y2="{PT + ch}" stroke="#e2e8f0"/>',
        f'<line x1="{PL}" y1="{PT + ch}" x2="{PL + cw}" y2="{PT + ch}" stroke="#e2e8f0"/>',
        '</svg>',
    ]
    return ''.join(parts)


def _annual_returns_svg(years: list[str], rets: list[float], width: int = 600, height: int = 220) -> str:
    """Render annual returns as an inline SVG bar chart."""
    if not years or not rets:
        return ''
    PL, PR, PT, PB = 48, 20, 16, 28
    cw, ch = width - PL - PR, height - PT - PB
    max_abs = max(abs(r) for r in rets) or 0.01
    zero_y = PT + ch / 2
    scale = ch / 2 / max_abs
    n = len(years)
    bar_w = max(6, cw / n * 0.55)
    gap = cw / n
    parts: list[str] = [
        f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto">',
        f'<line x1="{PL}" y1="{zero_y:.0f}" x2="{PL + cw}" y2="{zero_y:.0f}" stroke="#e2e8f0"/>',
    ]
    for i, (year, ret) in enumerate(zip(years, rets)):
        cx = PL + gap * i + gap / 2
        bh = abs(ret) * scale
        by = zero_y - bh if ret >= 0 else zero_y
        col = "#16a34a" if ret >= 0 else "#dc2626"
        parts += [
            f'<rect x="{cx - bar_w / 2:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" fill="{col}" rx="2"/>',
            f'<text x="{cx:.0f}" y="{PT + ch + PB - 3}" text-anchor="middle" font-size="10" fill="#64748b">{year}</text>',
            f'<text x="{cx:.0f}" y="{(by - 3 if ret >= 0 else by + bh + 11):.0f}" text-anchor="middle" font-size="9" fill="{col}">{ret * 100:.1f}%</text>',
        ]
    parts.append('</svg>')
    return ''.join(parts)


@router.get("/{run_id}/export")
async def export_backtest_report(
    run_id: str,
    catalog: CatalogDep,
    format: str = "html",
) -> HTMLResponse:
    """生成回测独立 HTML 报告（内嵌 SVG 图表，无外部依赖，支持离线打开）。"""
    from datetime import datetime as dt
    from jinja2 import Environment, FileSystemLoader, select_autoescape

    if format != "html":
        raise HTTPException(status_code=400, detail=f"Unsupported format '{format}'. Only 'html' is supported.")

    # 1. 加载运行元数据（合并为单次查询）
    run_df = catalog.query(
        "SELECT run_id, strategy_id, engine, status, dataset_version, "
        "benchmark_asset_id, started_at, completed_at "
        "FROM gold_backtest_runs WHERE run_id = ?",
        [run_id],
    )
    if run_df.is_empty():
        raise HTTPException(status_code=404, detail=f"Backtest run '{run_id}' not found")
    run_info = run_df.to_dicts()[0]

    # 2. 加载指标
    metrics: dict = {}
    mpath = _safe_metrics_path(run_id)
    if mpath and mpath.exists():
        try:
            metrics = json.loads(mpath.read_text())
        except Exception:
            pass

    key_metrics = [
        _fmt_metric(k, metrics.get(k))
        for k in [
            "total_return", "annualized_return", "sharpe_ratio", "max_drawdown",
            "sortino_ratio", "calmar_ratio", "win_rate", "annualized_volatility",
            "information_ratio", "tracking_error", "alpha", "beta",
        ]
    ]

    # 3. 加载净值曲线
    snaps_df = catalog.query(
        "SELECT trade_date, nav FROM gold_portfolio_snapshots "
        "WHERE run_id = ? ORDER BY trade_date",
        [run_id],
    )
    snaps = snaps_df.to_dicts() if not snaps_df.is_empty() else []
    nav_dates = [str(r["trade_date"]) for r in snaps]
    nav_values = [float(r["nav"]) for r in snaps]

    # 4. 加载基准曲线（如果有）
    bm_values: list[float] = []
    bm_asset = run_info.get("benchmark_asset_id") or ""
    if bm_asset and nav_dates:
        bm_df = catalog.query(
            "SELECT trade_date, close FROM silver_prices_1d "
            "WHERE asset_id = ? AND trade_date >= ? AND trade_date <= ? ORDER BY trade_date",
            [bm_asset, nav_dates[0], nav_dates[-1]],
        )
        if not bm_df.is_empty():
            first = float(bm_df["close"][0])
            bm_values = [float(r["close"]) / first for r in bm_df.to_dicts()]

    # 5. 年度收益
    annual_returns: list[tuple[str, float]] = []
    if nav_dates and nav_values:
        import polars as pl
        df_nav = pl.DataFrame({"date": nav_dates, "nav": nav_values}).with_columns(
            pl.col("date").str.slice(0, 4).alias("year")
        )
        for year in sorted(df_nav["year"].unique().to_list()):
            yr_df = df_nav.filter(pl.col("year") == year).sort("date")
            if len(yr_df) >= 2:
                annual_returns.append((year, float(yr_df["nav"][-1]) / float(yr_df["nav"][0]) - 1))

    # 6. 最近 20 笔交易
    fills_df = catalog.query(
        "SELECT trade_date, asset_id, side, quantity, price FROM gold_fills "
        "WHERE run_id = ? ORDER BY trade_date DESC LIMIT 20",
        [run_id],
    )
    fills = fills_df.to_dicts() if not fills_df.is_empty() else []

    # 7. 生成服务端 SVG 图表（无外部依赖，离线可用）
    nav_svg = _nav_to_svg(nav_dates, nav_values, bm_values=bm_values or None)
    annual_svg = _annual_returns_svg(
        [y for y, _ in annual_returns], [r for _, r in annual_returns]
    )

    # 8. 渲染 HTML（启用 autoescape 防止 XSS）
    tmpl_dir = pathlib.Path(__file__).parent.parent / "templates"
    env = Environment(
        loader=FileSystemLoader(str(tmpl_dir)),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template("backtest_report.html")

    html_content = template.render(
        run_id=run_id,
        strategy_id=run_info.get("strategy_id", ""),
        engine=run_info.get("engine", ""),
        status=run_info.get("status", ""),
        dataset_version=run_info.get("dataset_version", ""),
        start_date=nav_dates[0] if nav_dates else "—",
        end_date=nav_dates[-1] if nav_dates else "—",
        key_metrics=key_metrics,
        nav_svg=nav_svg,
        annual_svg=annual_svg,
        fills=fills,
        has_annual=bool(annual_returns),
        generated_at=dt.now().strftime("%Y-%m-%d %H:%M"),
    )

    # 9. 文件大小守护（PRD: < 2MB）
    content_bytes = html_content.encode("utf-8")
    if len(content_bytes) > 2 * 1024 * 1024:
        logger.warning("HTML report for %s is %d bytes (> 2MB)", run_id, len(content_bytes))

    filename = f"backtest_report_{run_id[:12]}.html"
    return HTMLResponse(
        content=content_bytes.decode("utf-8"),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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
async def get_backtest_fills(
    run_id: str,
    catalog: CatalogDep,
    offset: int = 0,
    limit: int = 50,
    sort_by: str = "trade_date",
    sort_order: str = "desc",
) -> dict:
    """Get fill records for a backtest run with pagination and sorting."""
    offset = max(0, offset)
    limit = max(1, min(limit, 500))
    allowed_sorts = {"trade_date", "asset_id", "side", "qty", "price", "notional", "total_cost"}
    if sort_by not in allowed_sorts:
        sort_by = "trade_date"
    order = "DESC" if sort_order.lower() == "desc" else "ASC"

    count_df = catalog.query(
        "SELECT COUNT(*) as cnt FROM gold_fills WHERE run_id = ?", [run_id]
    )
    total = count_df["cnt"].item() if not count_df.is_empty() else 0

    df = catalog.query(
        f"SELECT trade_date, asset_id, side, qty, price, notional, "
        f"commission, stamp_duty, slippage, total_cost "
        f"FROM gold_fills WHERE run_id = ? ORDER BY {sort_by} {order} LIMIT ? OFFSET ?",
        [run_id, limit, offset],
    )
    return {"items": df.to_dicts(), "total": total, "offset": offset, "limit": limit}


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
