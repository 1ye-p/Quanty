"""Factor values and analytics routes."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from cquant.api_server.deps import CatalogDep

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/factors", tags=["factors"])


@router.get("")
async def list_factor_values(
    catalog: CatalogDep,
    feature_set_version: str | None = None,
    factor_name: str | None = None,
    limit: int = 100,
) -> dict:
    """List factor values with optional filtering."""
    conditions = ["1=1"]
    params: list = []
    if feature_set_version:
        conditions.append("feature_set_version = ?")
        params.append(feature_set_version)
    if factor_name:
        conditions.append("factor_name = ?")
        params.append(factor_name)
    params.append(limit)

    where = " AND ".join(conditions)
    df = catalog.query(
        f"SELECT feature_set_version, factor_name, trade_date, asset_id, value "
        f"FROM gold_factor_values WHERE {where} ORDER BY trade_date DESC LIMIT ?",
        params,
    )
    return {"items": df.to_dicts(), "total": df.height}


@router.get("/versions")
async def list_feature_set_versions(catalog: CatalogDep) -> dict:
    """List distinct feature set versions."""
    df = catalog.query(
        "SELECT DISTINCT feature_set_version, MIN(trade_date) AS start_date, "
        "MAX(trade_date) AS end_date, COUNT(*) AS row_count "
        "FROM gold_factor_values GROUP BY feature_set_version ORDER BY end_date DESC"
    )
    return {"items": df.to_dicts()}


class ICComputeBody(BaseModel):
    factor_name: str
    feature_set_version: str
    horizon_days: int = 1


class ICMatrixBody(BaseModel):
    factor_names: list[str]
    feature_set_version: str
    horizon_days: int = 1


@router.post("/analytics/matrix", status_code=202)
async def compute_ic_matrix(
    body: ICMatrixBody,
    background_tasks: BackgroundTasks,
    catalog: CatalogDep,
) -> dict:
    """Submit an async multi-factor IC correlation matrix job."""
    job_id = str(uuid.uuid4())
    now = datetime.now(tz=timezone.utc).isoformat()
    catalog.execute(
        "INSERT INTO meta_factor_analytics "
        "(job_id, factor_name, feature_set_version, horizon_days, status, submitted_at) "
        "VALUES (?, ?, ?, ?, 'pending', ?)",
        [job_id, "__matrix__:" + ",".join(body.factor_names), body.feature_set_version, body.horizon_days, now],
    )
    background_tasks.add_task(_compute_ic_matrix, job_id, body, catalog)
    return {"job_id": job_id, "status": "submitted"}


@router.get("/definitions")
async def factor_definitions() -> dict:
    """List all registered built-in factor definitions."""
    from cquant.factorlab.factors import BUILTIN_FACTORS
    items = [
        {"name": f.name, "description": f.description, "tags": f.tags}
        for f in BUILTIN_FACTORS
    ]
    return {"items": items, "total": len(items)}


@router.post("/analytics/compute", status_code=202)
async def compute_ic_analytics(
    body: ICComputeBody,
    background_tasks: BackgroundTasks,
    catalog: CatalogDep,
) -> dict:
    """Submit an async IC/IR computation job."""
    job_id = str(uuid.uuid4())
    now = datetime.now(tz=timezone.utc).isoformat()
    catalog.execute(
        "INSERT INTO meta_factor_analytics "
        "(job_id, factor_name, feature_set_version, horizon_days, status, submitted_at) "
        "VALUES (?, ?, ?, ?, 'pending', ?)",
        [job_id, body.factor_name, body.feature_set_version, body.horizon_days, now],
    )
    background_tasks.add_task(_compute_ic, job_id, body, catalog)
    return {"job_id": job_id, "status": "submitted"}


@router.get("/analytics/{job_id}")
async def get_ic_analytics(job_id: str, catalog: CatalogDep) -> dict:
    df = catalog.query(
        "SELECT * FROM meta_factor_analytics WHERE job_id = ?", [job_id]
    )
    if df.is_empty():
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return df.to_dicts()[0]


def _compute_ic(job_id: str, body: ICComputeBody, catalog: CatalogDep) -> None:
    """Background task: compute IC series for a factor."""
    import polars as pl
    import json
    import numpy as np
    from collections import defaultdict

    try:
        catalog.execute(
            "UPDATE meta_factor_analytics SET status = 'running' WHERE job_id = ?", [job_id]
        )

        # Verify gold_factor_values table exists and has data
        try:
            table_check = catalog.query(
                "SELECT COUNT(*) AS cnt FROM gold_factor_values "
                "WHERE feature_set_version = ? AND factor_name = ?",
                [body.feature_set_version, body.factor_name],
            )
            row_count = table_check["cnt"][0] if not table_check.is_empty() else 0
        except Exception as table_err:
            raise ValueError(
                f"无法查询 gold_factor_values 表，请先物化因子。"
                f"错误: {table_err}"
            ) from table_err

        if row_count == 0:
            raise ValueError(
                f"未找到因子 '{body.factor_name}' 在版本 '{body.feature_set_version}' 的数据。"
                f"请先在「因子研究」页面物化该因子，然后再计算 IC。"
            )

        # Load factor values and next-period returns
        factor_df = catalog.query(
            "SELECT trade_date, asset_id, value FROM gold_factor_values "
            "WHERE feature_set_version = ? AND factor_name = ? ORDER BY trade_date, asset_id",
            [body.feature_set_version, body.factor_name],
        )
        if factor_df.is_empty():
            raise ValueError(
                f"未找到因子 '{body.factor_name}' 的数据。请先物化该因子。"
            )

        # Try to load next-bar returns from silver_prices_1d
        ret_name = f"ret_{body.horizon_days}d"
        try:
            price_df = catalog.query(
                "SELECT trade_date, asset_id, close FROM silver_prices_1d ORDER BY asset_id, trade_date"
            )
        except Exception as price_err:
            raise ValueError(
                f"无法查询 silver_prices_1d 表: {price_err}"
            ) from price_err

        if price_df.is_empty():
            raise ValueError("silver_prices_1d 无价格数据，请先摄取市场数据。")

        price_with_ret = (
            price_df.sort(["asset_id", "trade_date"])
            .with_columns(
                (pl.col("close") / pl.col("close").shift(body.horizon_days).over("asset_id") - 1)
                .alias(ret_name)
            )
        )

        merged = factor_df.join(
            price_with_ret.select(["trade_date", "asset_id", ret_name]),
            on=["trade_date", "asset_id"],
            how="inner",
        ).drop_nulls()

        # Compute daily IC = cross-sectional rank correlation
        series = []
        for dt, group in merged.group_by("trade_date"):
            if group.height < 5:
                continue
            f_rank = group["value"].rank().to_numpy()
            r_rank = group[ret_name].rank().to_numpy()
            ic = float(np.corrcoef(f_rank, r_rank)[0, 1]) if len(f_rank) > 1 else 0.0
            series.append({"trade_date": str(dt[0]), "ic": round(ic, 6)})

        series.sort(key=lambda x: x["trade_date"])
        ic_values = [s["ic"] for s in series]
        summary = {
            "mean_ic": round(float(np.mean(ic_values)), 6) if ic_values else 0.0,
            "ir": round(float(np.mean(ic_values) / (np.std(ic_values) + 1e-12)), 4) if ic_values else 0.0,
            "hit_rate": round(float(sum(1 for v in ic_values if v > 0) / max(len(ic_values), 1)), 4),
            "observations": len(ic_values),
        }

        # ── Rank IC decay（lag 1-10）──────────────────────────────
        sorted_dates = sorted(merged["trade_date"].unique().to_list())
        date_map: dict = {dt[0]: grp for dt, grp in merged.group_by("trade_date")}
        rank_ic_decay = []
        for lag in range(1, 11):
            decay_ics = []
            for i in range(len(sorted_dates) - lag):
                date_t = sorted_dates[i]
                date_tlag = sorted_dates[i + lag]
                factor_t = date_map[date_t].select(["asset_id", "value"])
                ret_tlag = date_map.get(date_tlag, pl.DataFrame()).select(["asset_id", ret_name])
                joined = factor_t.join(ret_tlag, on="asset_id", how="inner")
                if joined.height < 5:
                    continue
                f_arr = joined["value"].rank().to_numpy()
                r_arr = joined[ret_name].rank().to_numpy()
                ic_val = float(np.corrcoef(f_arr, r_arr)[0, 1])
                if not np.isnan(ic_val):
                    decay_ics.append(ic_val)
            rank_ic_decay.append({
                "lag": lag,
                "ic": round(float(np.mean(decay_ics)), 6) if decay_ics else 0.0,
            })

        # ── Quantile returns（5 分组）────────────────────────────
        q_buckets: dict[int, list[float]] = defaultdict(list)
        for dt in sorted_dates:
            group = date_map[dt]
            if group.height < 10:
                continue
            sorted_g = group.sort("value")
            n = len(sorted_g)
            q_size = n // 5
            for q in range(5):
                start_idx = q * q_size
                end_idx = (q + 1) * q_size if q < 4 else n
                sliced = sorted_g.slice(start_idx, end_idx - start_idx)
                _m = sliced[ret_name].mean()
                mean_ret = float(_m) if _m is not None else 0.0
                q_buckets[q + 1].append(mean_ret)
        quantile_returns = [
            {"quantile": q, "mean_return": round(float(np.mean(vals)), 6)}
            for q, vals in sorted(q_buckets.items())
        ]

        # ── Factor turnover（Top 20%）────────────────────────────
        top_n_assets = max(1, int(0.2 * merged["asset_id"].n_unique()))
        turnovers: list[float] = []
        prev_top: set[str] = set()
        for dt in sorted_dates:
            today_top = set(
                date_map[dt]
                .sort("value", descending=True)
                .head(top_n_assets)["asset_id"]
                .to_list()
            )
            if prev_top:
                overlap = len(today_top & prev_top)
                turnovers.append(1.0 - overlap / max(len(today_top), 1))
            prev_top = today_top
        factor_turnover = round(float(np.mean(turnovers)), 4) if turnovers else 0.0

        # 追加到 summary
        summary["rank_ic_decay"] = rank_ic_decay
        summary["quantile_returns"] = quantile_returns
        summary["factor_turnover"] = factor_turnover

        catalog.execute(
            "UPDATE meta_factor_analytics SET status = 'done', series_json = ?, summary_json = ?, completed_at = ? WHERE job_id = ?",
            [json.dumps(series), json.dumps(summary), datetime.now(tz=timezone.utc).isoformat(), job_id],
        )
    except Exception as exc:
        error_msg = str(exc)
        logger.exception("IC compute job %s failed: %s", job_id, error_msg)
        # 用户友好的错误信息
        if "No factor values found" in error_msg or "未找到因子" in error_msg:
            user_msg = error_msg
        elif "INTERNAL Error" in error_msg or "unique_ptr" in error_msg:
            user_msg = (
                f"DuckDB 内部错误，可能是因子数据未物化或表结构问题。"
                f"请先在「因子研究」页面物化因子 '{body.factor_name}'。"
                f"原始错误: {error_msg[:200]}"
            )
        else:
            user_msg = f"IC 计算失败: {error_msg[:300]}"
        catalog.execute(
            "UPDATE meta_factor_analytics SET status = 'error', error_text = ?, completed_at = ? WHERE job_id = ?",
            [user_msg, datetime.now(tz=timezone.utc).isoformat(), job_id],
        )


def _compute_ic_matrix(job_id: str, body: ICMatrixBody, catalog: CatalogDep) -> None:
    """Background task: compute IC series for multiple factors and their correlation matrix."""
    import polars as pl
    import json
    import numpy as np

    try:
        catalog.execute(
            "UPDATE meta_factor_analytics SET status = 'running' WHERE job_id = ?", [job_id]
        )

        ret_name = f"ret_{body.horizon_days}d"
        price_df = catalog.query(
            "SELECT trade_date, asset_id, close FROM silver_prices_1d ORDER BY asset_id, trade_date"
        )
        if price_df.is_empty():
            raise ValueError("silver_prices_1d 无价格数据")

        price_with_ret = (
            price_df.sort(["asset_id", "trade_date"])
            .with_columns(
                (pl.col("close") / pl.col("close").shift(body.horizon_days).over("asset_id") - 1)
                .alias(ret_name)
            )
        )

        # Compute IC series for each factor
        factor_ics: dict[str, list[tuple[str, float]]] = {}
        for factor_name in body.factor_names:
            factor_df = catalog.query(
                "SELECT trade_date, asset_id, value FROM gold_factor_values "
                "WHERE feature_set_version = ? AND factor_name = ? ORDER BY trade_date, asset_id",
                [body.feature_set_version, factor_name],
            )
            if factor_df.is_empty():
                continue

            merged = factor_df.join(
                price_with_ret.select(["trade_date", "asset_id", ret_name]),
                on=["trade_date", "asset_id"],
                how="inner",
            ).drop_nulls()

            series = []
            for dt, group in merged.group_by("trade_date"):
                if group.height < 5:
                    continue
                f_rank = group["value"].rank().to_numpy()
                r_rank = group[ret_name].rank().to_numpy()
                ic = float(np.corrcoef(f_rank, r_rank)[0, 1]) if len(f_rank) > 1 else 0.0
                if not np.isnan(ic):
                    series.append((str(dt[0]), ic))
            series.sort(key=lambda x: x[0])
            factor_ics[factor_name] = series

        if not factor_ics:
            raise ValueError("未找到任何因子数据")

        # Build aligned IC matrix (dates x factors)
        all_dates = sorted(set(d for ics in factor_ics.values() for d, _ in ics))
        factor_names = sorted(factor_ics.keys())
        ic_map: dict[str, dict[str, float]] = {fn: dict(ics) for fn, ics in factor_ics.items()}

        ic_matrix = []
        for dt in all_dates:
            row = [ic_map.get(fn, {}).get(dt, 0.0) for fn in factor_names]
            ic_matrix.append(row)

        ic_array = np.array(ic_matrix)
        # Correlation between factor IC series
        corr = np.corrcoef(ic_array, rowvar=False)
        corr = np.nan_to_num(corr, nan=0.0).tolist()

        # Summary stats per factor
        factor_stats = {}
        for i, fn in enumerate(factor_names):
            vals = ic_array[:, i].tolist()
            factor_stats[fn] = {
                "mean_ic": round(float(np.mean(vals)), 6),
                "ir": round(float(np.mean(vals) / (np.std(vals) + 1e-12)), 4),
                "hit_rate": round(float(sum(1 for v in vals if v > 0) / max(len(vals), 1)), 4),
            }

        summary = {
            "factors": factor_names,
            "correlation": corr,
            "factor_stats": factor_stats,
            "observations": len(all_dates),
        }

        catalog.execute(
            "UPDATE meta_factor_analytics SET status = 'done', series_json = ?, summary_json = ?, completed_at = ? WHERE job_id = ?",
            [json.dumps([]), json.dumps(summary), datetime.now(tz=timezone.utc).isoformat(), job_id],
        )
    except Exception as exc:
        error_msg = str(exc)
        logger.exception("IC matrix job %s failed: %s", job_id, error_msg)
        catalog.execute(
            "UPDATE meta_factor_analytics SET status = 'error', error_text = ?, completed_at = ? WHERE job_id = ?",
            [f"IC 矩阵计算失败: {error_msg[:300]}", datetime.now(tz=timezone.utc).isoformat(), job_id],
        )


# ── Factor Quintile Returns ───────────────────────────────────────────────────

class QuintileRequest(BaseModel):
    factor_name: str
    feature_set_version: str
    horizon_days: int = 5
    start_date: str = ""
    end_date: str = ""
    n_groups: int = Field(default=5, ge=2, le=20)


@router.post("/analytics/quintiles")
async def compute_quintile_returns(body: QuintileRequest, catalog: CatalogDep) -> dict:
    """计算因子分层收益（Q1–Qn 平均收益）。"""
    import polars as pl

    ret_name = f"ret_{body.horizon_days}d"
    start = body.start_date or "2023-01-01"
    end = body.end_date or "2025-12-31"

    factor_df = catalog.query(
        "SELECT asset_id, trade_date, value FROM gold_factor_values "
        "WHERE feature_set_version = ? AND factor_name = ? "
        "AND trade_date >= ? AND trade_date <= ?",
        [body.feature_set_version, body.factor_name, start, end],
    )
    if factor_df.is_empty():
        return {"factor_name": body.factor_name, "n_groups": body.n_groups, "groups": []}

    prices_df = catalog.query(
        "SELECT asset_id, trade_date, close FROM silver_prices_1d "
        "WHERE trade_date >= ? AND trade_date <= ?",
        [start, end],
    )
    prices_df = prices_df.with_columns(
        (pl.col("close") / pl.col("close").shift(body.horizon_days).over("asset_id", order_by="trade_date") - 1)
        .alias(ret_name)
    )

    joined = factor_df.join(
        prices_df.select(["asset_id", "trade_date", ret_name]),
        on=["asset_id", "trade_date"],
        how="inner",
    ).drop_nulls()

    if joined.is_empty():
        return {"factor_name": body.factor_name, "n_groups": body.n_groups, "groups": []}

    n = body.n_groups
    # 全 Polars 向量化分组：rank → quintile，无 Python 循环
    labeled = (
        joined
        .with_columns(
            pl.col("value").rank(method="average").over("trade_date").alias("_rank"),
            pl.col("value").count().over("trade_date").alias("_n"),
        )
        .filter(pl.col("_n") >= n)
        .with_columns(
            ((pl.col("_rank") - 1) / pl.col("_n") * n)
            .cast(pl.Int32)
            .clip(0, n - 1)
            .add(1)
            .alias("quintile")  # Int32, not Utf8 — ensures numeric sort is correct
        )
        .drop(["_rank", "_n"])
    )

    if labeled.is_empty():
        return {"factor_name": body.factor_name, "n_groups": body.n_groups, "groups": []}

    group_stats = (
        labeled.group_by("quintile")
        .agg([
            pl.col(ret_name).mean().alias("mean_return"),
            pl.col(ret_name).std().alias("std_return"),
            pl.col(ret_name).count().alias("count"),
        ])
        .sort("quintile")
    )

    return {
        "factor_name": body.factor_name,
        "horizon_days": body.horizon_days,
        "n_groups": n,
        "groups": group_stats.to_dicts(),
    }


# ── Factor Correlation Matrix ─────────────────────────────────────────────────

class FactorCorrelationRequest(BaseModel):
    factor_names: list[str]
    feature_set_version: str
    start_date: str = ""
    end_date: str = ""


@router.post("/analytics/factor-correlation")
async def compute_factor_correlation(body: FactorCorrelationRequest, catalog: CatalogDep) -> dict:
    """计算多因子值之间的截面均值相关矩阵。"""
    import polars as pl

    if len(body.factor_names) < 2:
        return {"error": "需要至少 2 个因子", "factors": [], "matrix": []}
    if len(body.factor_names) > 50:
        return {"error": "因子数量不能超过 50 个", "factors": [], "matrix": []}

    start = body.start_date or "2023-01-01"
    end = body.end_date or "2025-12-31"

    # 使用参数化占位符，避免 SQL 注入
    in_placeholders = ",".join(["?" for _ in body.factor_names])
    params = [body.feature_set_version] + list(body.factor_names) + [start, end]

    df = catalog.query(
        f"SELECT asset_id, trade_date, factor_name, value FROM gold_factor_values "
        f"WHERE feature_set_version = ? AND factor_name IN ({in_placeholders}) "
        f"AND trade_date >= ? AND trade_date <= ?",
        params,
    )
    if df.is_empty():
        return {"error": "无数据", "factors": body.factor_names, "matrix": []}

    wide = df.pivot(index=["asset_id", "trade_date"], columns="factor_name", values="value")
    factor_cols = [c for c in body.factor_names if c in wide.columns]

    matrix = []
    for f1 in factor_cols:
        for f2 in factor_cols:
            if f1 == f2:
                corr: float | None = 1.0
            else:
                pair = wide.select([f1, f2]).drop_nulls()
                corr = float(pair[f1].corr(pair[f2])) if len(pair) >= 10 else None
            matrix.append({"factor_a": f1, "factor_b": f2, "correlation": corr})

    return {"factors": factor_cols, "matrix": matrix}
