"""Factor values and analytics routes."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

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

        # Load factor values and next-period returns
        factor_df = catalog.query(
            "SELECT trade_date, asset_id, value FROM gold_factor_values "
            "WHERE feature_set_version = ? AND factor_name = ? ORDER BY trade_date, asset_id",
            [body.feature_set_version, body.factor_name],
        )
        if factor_df.is_empty():
            raise ValueError("No factor values found")

        # Try to load next-bar returns from silver_prices_1d
        ret_name = f"ret_{body.horizon_days}d"
        price_df = catalog.query(
            "SELECT trade_date, asset_id, close FROM silver_prices_1d ORDER BY asset_id, trade_date"
        )

        if price_df.is_empty():
            raise ValueError("No price data found for IC computation")

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
        logger.exception("IC compute job %s failed: %s", job_id, exc)
        catalog.execute(
            "UPDATE meta_factor_analytics SET status = 'error', error_text = ?, completed_at = ? WHERE job_id = ?",
            [str(exc), datetime.now(tz=timezone.utc).isoformat(), job_id],
        )
