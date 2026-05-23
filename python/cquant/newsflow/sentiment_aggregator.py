"""cquant.newsflow.sentiment_aggregator — 新闻情感日度聚合工具。

将 silver_news_events 的逐条情感得分聚合为每日每股平均情感因子，
符合 PIT（Point-In-Time）原则，仅使用 as_of_date 之前已发布的新闻。
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import polars as pl


def aggregate_daily_sentiment(
    news_df: pl.DataFrame,
    as_of_date: date,
    lookback_days: int = 3,
) -> dict[str, float]:
    """计算各资产在最近 N 天内的平均情感得分。

    Parameters
    ----------
    news_df:
        包含列 [asset_ids_mentioned (List[str]), available_at (Datetime), sentiment_score (Float64)]
        的新闻 DataFrame（来自 silver_news_events）。
    as_of_date:
        计算截止日期（不含当日 00:00:00 UTC 之后的新闻）。
    lookback_days:
        向前回看的天数。

    Returns
    -------
    ``dict[asset_id, avg_sentiment_score]``
    """
    if news_df.is_empty() or "sentiment_score" not in news_df.columns:
        return {}

    cutoff = datetime(
        as_of_date.year, as_of_date.month, as_of_date.day,
        tzinfo=timezone.utc,
    )
    start_dt = cutoff - timedelta(days=lookback_days)

    filtered = news_df.filter(
        (pl.col("available_at") >= start_dt)
        & (pl.col("available_at") < cutoff)
        & pl.col("sentiment_score").is_not_null()
    )

    if filtered.is_empty():
        return {}

    exploded = filtered.explode("asset_ids_mentioned").filter(
        pl.col("asset_ids_mentioned").is_not_null()
        & (pl.col("asset_ids_mentioned").str.len_chars() > 0)
    )

    if exploded.is_empty():
        return {}

    agg = (
        exploded
        .group_by("asset_ids_mentioned")
        .agg(pl.col("sentiment_score").mean().alias("avg_sentiment"))
    )

    return dict(zip(
        agg["asset_ids_mentioned"].to_list(),
        agg["avg_sentiment"].to_list(),
    ))
