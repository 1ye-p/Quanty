"""News events routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from cquant.api_server.deps import CatalogDep

router = APIRouter(prefix="/news", tags=["news"])


@router.get("/events")
async def list_news_events(
    catalog: CatalogDep,
    source: str | None = None,
    asset_id: str | None = None,
    event_type: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    sentiment_min: float | None = None,
    limit: int = 100,
) -> dict:
    """List news events with optional filters."""
    conditions = ["1=1"]
    params: list = []

    if source:
        conditions.append("source = ?")
        params.append(source)
    if event_type:
        conditions.append("event_type = ?")
        params.append(event_type)
    if from_date:
        conditions.append("published_at >= ?")
        params.append(from_date)
    if to_date:
        conditions.append("published_at <= ?")
        params.append(to_date)
    if sentiment_min is not None:
        conditions.append("sentiment_score >= ?")
        params.append(sentiment_min)
    if asset_id:
        # DuckDB array contains
        conditions.append(f"list_contains(asset_ids_mentioned, ?)")
        params.append(asset_id)

    params.append(limit)
    where = " AND ".join(conditions)
    df = catalog.query(
        f"SELECT event_id, source, headline, published_at, available_at, "
        f"asset_ids_mentioned, sentiment_score, event_type, language "
        f"FROM silver_news_events WHERE {where} "
        f"ORDER BY published_at DESC LIMIT ?",
        params,
    )
    return {"items": df.to_dicts(), "total": df.height}


@router.get("/events/{event_id}")
async def get_news_event(event_id: str, catalog: CatalogDep) -> dict:
    """Get full news event including body text."""
    df = catalog.query(
        "SELECT * FROM silver_news_events WHERE event_id = ?",
        [event_id],
    )
    if df.is_empty():
        raise HTTPException(status_code=404, detail=f"News event '{event_id}' not found")
    return df.to_dicts()[0]


@router.get("/stats")
async def news_stats(
    catalog: CatalogDep,
    asset_id: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
) -> dict:
    """Aggregated news statistics with optional filters."""
    # Build WHERE clauses for optional filters
    conditions = ["1=1"]
    params: list = []

    if asset_id:
        conditions.append("list_contains(asset_ids_mentioned, ?)")
        params.append(asset_id)
    if from_date:
        conditions.append("published_at >= ?")
        params.append(from_date)
    if to_date:
        conditions.append("published_at <= ?")
        params.append(to_date)

    where = " AND ".join(conditions)

    total_df = catalog.query(f"SELECT COUNT(*) AS n FROM silver_news_events WHERE {where}", params)
    total = int(total_df["n"].item()) if not total_df.is_empty() else 0

    source_df = catalog.query(
        f"SELECT source, COUNT(*) AS count FROM silver_news_events WHERE {where} GROUP BY source ORDER BY count DESC",
        params,
    )
    type_df = catalog.query(
        f"SELECT event_type, COUNT(*) AS count FROM silver_news_events WHERE {where} GROUP BY event_type ORDER BY count DESC",
        params,
    )
    sentiment_df = catalog.query(
        f"SELECT AVG(sentiment_score) AS avg_sentiment FROM silver_news_events WHERE {where} AND sentiment_score IS NOT NULL",
        params,
    )

    daily_df = catalog.query(
        f"SELECT DATE_TRUNC('day', published_at) as date, "
        f"  AVG(sentiment_score) as avg_sentiment, COUNT(*) as n_events "
        f"FROM silver_news_events "
        f"WHERE {where} AND published_at >= CURRENT_DATE - INTERVAL '35 days' "
        f"AND sentiment_score IS NOT NULL "
        f"GROUP BY 1 ORDER BY 1 DESC LIMIT 35",
        params,
    )
    daily_sentiment = [
        {
            "date": str(r["date"])[:10],
            "avg_sentiment": round(float(r["avg_sentiment"]), 4),
            "n_events": int(r["n_events"]),
        }
        for r in daily_df.to_dicts()
    ] if not daily_df.is_empty() else []

    return {
        "total_events": total,
        "source_counts": {r["source"]: r["count"] for r in source_df.to_dicts()},
        "event_type_counts": {r["event_type"]: r["count"] for r in type_df.to_dicts()},
        "avg_sentiment": (
            v if (v := sentiment_df["avg_sentiment"].item()) is None else float(v)
        ) if not sentiment_df.is_empty() else None,
        "daily_sentiment": daily_sentiment,
    }


@router.get("/sentiment/{asset_id}")
async def get_asset_sentiment(asset_id: str, catalog: CatalogDep, days: int = Query(default=90, ge=1, le=365)) -> dict:
    """Daily sentiment time series for a specific asset."""
    df = catalog.query(
        "SELECT DATE_TRUNC('day', published_at) as d, "
        "  AVG(sentiment_score) as avg_sentiment, COUNT(*) as n "
        "FROM silver_news_events "
        "WHERE list_contains(asset_ids_mentioned, ?) "
        "  AND published_at >= CURRENT_DATE - ? * INTERVAL '1 DAY' "
        "  AND sentiment_score IS NOT NULL "
        "GROUP BY 1 ORDER BY 1",
        [asset_id, days],
    )
    rows = df.to_dicts()
    return {
        "asset_id": asset_id,
        "dates": [str(r["d"])[:10] for r in rows],
        "values": [round(r["avg_sentiment"], 4) for r in rows],
        "counts": [r["n"] for r in rows],
    }
