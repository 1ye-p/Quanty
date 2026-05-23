"""Tests for newsflow keyword-based sentiment scorer."""
from __future__ import annotations

import pytest

from cquant.newsflow.sentiment import score_sentiment


class TestSentimentScorer:
    def test_positive_chinese_headline_positive_score(self) -> None:
        result = score_sentiment("股票大涨停，投资者盈利", language="zh-CN")
        assert result is not None
        assert result > 0

    def test_negative_chinese_headline_negative_score(self) -> None:
        result = score_sentiment("股票暴跌亏损，市场下滑", language="zh-CN")
        assert result is not None
        assert result < 0

    def test_positive_english_headline_positive_score(self) -> None:
        result = score_sentiment("Stocks rally on strong earnings growth", language="en")
        assert result is not None
        assert result > 0

    def test_negative_english_headline_negative_score(self) -> None:
        result = score_sentiment("Market plunge as losses mount and profits decline", language="en")
        assert result is not None
        assert result < 0

    def test_neutral_text_returns_none(self) -> None:
        result = score_sentiment("Today is Monday.", language="en")
        assert result is None

    def test_empty_text_returns_none(self) -> None:
        assert score_sentiment("", "en") is None
        assert score_sentiment("  ", "zh-CN") is None

    def test_score_bounded_to_minus_one_plus_one(self) -> None:
        result = score_sentiment("涨涨涨涨涨涨停停停", "zh-CN")
        if result is not None:
            assert -1.0 <= result <= 1.0


class TestSentimentWiredIntoNormalizer:
    def test_normalizer_sets_sentiment_score_not_always_none(self) -> None:
        from datetime import datetime, timezone
        from cquant.newsflow.connectors.base import RawNewsEnvelope
        from cquant.newsflow.normalize import NewsNormalizer

        normalizer = NewsNormalizer()
        envelope = RawNewsEnvelope(
            source="eastmoney",
            vendor_id="test_001",
            published_at=datetime.now(tz=timezone.utc),
            received_at=datetime.now(tz=timezone.utc),
            raw_payload={"headline": "A股大涨停，投资者盈利丰厚", "body": ""},
        )
        df = normalizer.normalize([envelope])
        assert not df.is_empty()
        score = df["sentiment_score"][0]
        # With strong positive keywords, score should not be None
        assert score is not None
        assert score > 0
