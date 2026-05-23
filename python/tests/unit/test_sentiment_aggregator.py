"""测试新闻情感日度聚合功能。"""
from __future__ import annotations

from datetime import date, datetime, timezone, timedelta

import polars as pl
import pytest

from cquant.newsflow.sentiment_aggregator import aggregate_daily_sentiment


def _make_news_df(rows: list[dict]) -> pl.DataFrame:
    schema = {
        "event_id": pl.Utf8,
        "asset_ids_mentioned": pl.List(pl.Utf8),
        "available_at": pl.Datetime(time_unit="us", time_zone="UTC"),
        "sentiment_score": pl.Float64,
    }
    return pl.DataFrame(rows, schema=schema, strict=False)


class TestAggregateDailySentiment:
    def test_returns_empty_when_no_news(self) -> None:
        df = pl.DataFrame(schema={
            "event_id": pl.Utf8,
            "asset_ids_mentioned": pl.List(pl.Utf8),
            "available_at": pl.Datetime(time_unit="us", time_zone="UTC"),
            "sentiment_score": pl.Float64,
        })
        result = aggregate_daily_sentiment(df, as_of_date=date(2025, 6, 1))
        assert result == {}

    def test_aggregates_single_asset(self) -> None:
        dt = datetime(2025, 5, 31, 12, 0, tzinfo=timezone.utc)
        df = _make_news_df([
            {"event_id": "n1", "asset_ids_mentioned": ["SSE:600036"],
             "available_at": dt, "sentiment_score": 0.8},
            {"event_id": "n2", "asset_ids_mentioned": ["SSE:600036"],
             "available_at": dt, "sentiment_score": 0.4},
        ])
        result = aggregate_daily_sentiment(df, as_of_date=date(2025, 6, 1), lookback_days=3)
        assert "SSE:600036" in result
        assert result["SSE:600036"] == pytest.approx(0.6, abs=0.001)

    def test_excludes_future_news(self) -> None:
        future_dt = datetime(2025, 6, 2, 12, 0, tzinfo=timezone.utc)
        df = _make_news_df([
            {"event_id": "n1", "asset_ids_mentioned": ["SSE:600036"],
             "available_at": future_dt, "sentiment_score": 1.0},
        ])
        result = aggregate_daily_sentiment(df, as_of_date=date(2025, 6, 1))
        assert "SSE:600036" not in result

    def test_excludes_news_outside_lookback(self) -> None:
        old_dt = datetime(2025, 5, 20, 12, 0, tzinfo=timezone.utc)
        df = _make_news_df([
            {"event_id": "n1", "asset_ids_mentioned": ["SSE:600036"],
             "available_at": old_dt, "sentiment_score": 1.0},
        ])
        result = aggregate_daily_sentiment(df, as_of_date=date(2025, 6, 1), lookback_days=3)
        assert "SSE:600036" not in result

    def test_multiple_assets_aggregated_independently(self) -> None:
        dt = datetime(2025, 5, 31, 12, 0, tzinfo=timezone.utc)
        df = _make_news_df([
            {"event_id": "n1", "asset_ids_mentioned": ["SSE:600036", "SSE:000001"],
             "available_at": dt, "sentiment_score": 0.9},
            {"event_id": "n2", "asset_ids_mentioned": ["SSE:000001"],
             "available_at": dt, "sentiment_score": -0.3},
        ])
        result = aggregate_daily_sentiment(df, as_of_date=date(2025, 6, 1))
        assert "SSE:600036" in result
        assert "SSE:000001" in result
        assert result["SSE:600036"] == pytest.approx(0.9, abs=0.001)
        assert result["SSE:000001"] == pytest.approx(0.3, abs=0.001)
