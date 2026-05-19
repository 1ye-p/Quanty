"""Unit tests for real-time quote connector.

Tests Quote parsing, QuoteFeed operations with mocked AKShare calls.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from cquant.datahub.connectors.realtime_connector import Quote, QuoteFeed, RealtimeQuoteConnector


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_mock_df() -> pd.DataFrame:
    """Create a mock DataFrame matching AKShare's stock_zh_a_spot_em output."""
    return pd.DataFrame([
        {
            "代码": "600036",
            "名称": "招商银行",
            "最新价": 35.50,
            "今开": 35.20,
            "最高": 35.80,
            "最低": 35.10,
            "昨收": 35.30,
            "成交量": 5000000,
            "成交额": 177500000.0,
            "买一价": 35.49,
            "卖一价": 35.51,
            "买一量": 1000,
            "卖一量": 800,
            "涨跌额": 0.20,
            "涨跌幅": 0.57,
        },
        {
            "代码": "000001",
            "名称": "平安银行",
            "最新价": 12.80,
            "今开": 12.70,
            "最高": 12.90,
            "最低": 12.65,
            "昨收": 12.75,
            "成交量": 8000000,
            "成交额": 102400000.0,
            "买一价": 12.79,
            "卖一价": 12.81,
            "买一量": 2000,
            "卖一量": 1500,
            "涨跌额": 0.05,
            "涨跌幅": 0.39,
        },
    ])


# ── Quote Dataclass Tests ─────────────────────────────────────────────────────

class TestQuoteDataclass:
    def test_to_dict_returns_all_fields(self):
        quote = Quote(
            asset_id="SSE:600036",
            symbol="600036",
            price=35.50,
            open=35.20,
            high=35.80,
            low=35.10,
            close=35.50,
            prev_close=35.30,
            volume=5000000,
            amount=177500000.0,
            bid1=35.49,
            ask1=35.51,
            bid1_vol=1000,
            ask1_vol=800,
            change=0.20,
            change_pct=0.57,
        )
        d = quote.to_dict()
        assert d["asset_id"] == "SSE:600036"
        assert d["symbol"] == "600036"
        assert d["price"] == 35.50
        assert d["volume"] == 5000000
        assert "timestamp" in d

    def test_timestamp_auto_generated(self):
        quote = Quote(
            asset_id="SSE:600036",
            symbol="600036",
            price=35.50,
            open=35.20,
            high=35.80,
            low=35.10,
            close=35.50,
            prev_close=35.30,
            volume=5000000,
            amount=177500000.0,
            bid1=35.49,
            ask1=35.51,
            bid1_vol=1000,
            ask1_vol=800,
            change=0.20,
            change_pct=0.57,
        )
        assert isinstance(quote.timestamp, datetime)
        assert quote.timestamp.tzinfo is not None


# ── QuoteFeed Tests ───────────────────────────────────────────────────────────

class TestQuoteFeed:
    @patch("akshare.stock_zh_a_spot_em")
    def test_get_quotes_returns_matched_symbols(self, mock_ak):
        mock_ak.return_value = _make_mock_df()
        feed = QuoteFeed()
        quotes = feed.get_quotes(["600036", "000001"])

        assert len(quotes) == 2
        assert "600036" in quotes
        assert "000001" in quotes
        assert quotes["600036"].price == 35.50
        assert quotes["000001"].price == 12.80

    @patch("akshare.stock_zh_a_spot_em")
    def test_get_quotes_filters_unmatched(self, mock_ak):
        mock_ak.return_value = _make_mock_df()
        feed = QuoteFeed()
        quotes = feed.get_quotes(["600036"])

        assert len(quotes) == 1
        assert "600036" in quotes
        assert "000001" not in quotes

    @patch("akshare.stock_zh_a_spot_em")
    def test_get_quotes_empty_symbols(self, mock_ak):
        mock_ak.return_value = _make_mock_df()
        feed = QuoteFeed()
        quotes = feed.get_quotes([])
        assert quotes == {}

    @patch("akshare.stock_zh_a_spot_em")
    def test_get_all_quotes_respects_limit(self, mock_ak):
        mock_ak.return_value = _make_mock_df()
        feed = QuoteFeed()
        quotes = feed.get_all_quotes(limit=1)
        assert len(quotes) == 1

    @patch("akshare.stock_zh_a_spot_em")
    def test_get_quotes_handles_akshare_error(self, mock_ak):
        mock_ak.side_effect = Exception("Network error")
        feed = QuoteFeed()
        quotes = feed.get_quotes(["600036"])
        assert quotes == {}

    @patch("akshare.stock_zh_a_spot_em")
    def test_parse_row_extracts_correct_fields(self, mock_ak):
        mock_ak.return_value = _make_mock_df()
        feed = QuoteFeed()
        quotes = feed.get_quotes(["600036"])
        q = quotes["600036"]

        assert q.asset_id == "SSE:600036"
        assert q.symbol == "600036"
        assert q.price == 35.50
        assert q.open == 35.20
        assert q.high == 35.80
        assert q.low == 35.10
        assert q.prev_close == 35.30
        assert q.volume == 5000000
        assert q.bid1 == 35.49
        assert q.ask1 == 35.51
        assert q.change == 0.20
        assert q.change_pct == 0.57

    @patch("akshare.stock_zh_a_spot_em")
    def test_szse_exchange_for_shenzhen_codes(self, mock_ak):
        mock_ak.return_value = _make_mock_df()
        feed = QuoteFeed()
        quotes = feed.get_quotes(["000001"])
        assert quotes["000001"].asset_id == "SZSE:000001"

    @patch("akshare.stock_zh_a_spot_em")
    def test_sse_exchange_for_shanghai_codes(self, mock_ak):
        mock_ak.return_value = _make_mock_df()
        feed = QuoteFeed()
        quotes = feed.get_quotes(["600036"])
        assert quotes["600036"].asset_id == "SSE:600036"


# ── Subscribe/Stop Tests ──────────────────────────────────────────────────────

class TestQuoteFeedPolling:
    @patch("akshare.stock_zh_a_spot_em")
    def test_subscribe_starts_polling(self, mock_ak):
        mock_ak.return_value = _make_mock_df()
        feed = QuoteFeed()
        received = []

        def callback(quotes):
            received.append(quotes)

        feed.subscribe(["600036"], callback, interval=0.1)
        assert feed._polling is True

        # Wait for at least one poll
        import time
        time.sleep(0.3)

        feed.stop()
        assert feed._polling is False
        assert len(received) >= 1

    @patch("akshare.stock_zh_a_spot_em")
    def test_stop_idempotent(self, mock_ak):
        mock_ak.return_value = _make_mock_df()
        feed = QuoteFeed()
        feed.stop()  # Should not raise
        feed.stop()


# ── RealtimeQuoteConnector Tests ──────────────────────────────────────────────

class TestRealtimeQuoteConnector:
    @patch("akshare.stock_zh_a_spot_em")
    def test_get_quote_single(self, mock_ak):
        mock_ak.return_value = _make_mock_df()
        connector = RealtimeQuoteConnector()
        quote = connector.get_quote("600036")

        assert quote is not None
        assert quote.price == 35.50

    @patch("akshare.stock_zh_a_spot_em")
    def test_get_quote_not_found(self, mock_ak):
        mock_ak.return_value = _make_mock_df()
        connector = RealtimeQuoteConnector()
        quote = connector.get_quote("999999")
        assert quote is None

    @patch("akshare.stock_zh_a_spot_em")
    def test_get_quotes_multiple(self, mock_ak):
        mock_ak.return_value = _make_mock_df()
        connector = RealtimeQuoteConnector()
        quotes = connector.get_quotes(["600036", "000001"])
        assert len(quotes) == 2

    @patch("akshare.stock_zh_a_spot_em")
    def test_feed_property(self, mock_ak):
        connector = RealtimeQuoteConnector()
        assert isinstance(connector.feed, QuoteFeed)


# ── Edge Cases ────────────────────────────────────────────────────────────────

class TestEdgeCases:
    @patch("akshare.stock_zh_a_spot_em")
    def test_missing_fields_use_defaults(self, mock_ak):
        """Test that missing/None fields default to 0."""
        df = pd.DataFrame([{
            "代码": "600036",
            "最新价": None,
            "今开": "-",
            "最高": None,
            "最低": None,
            "昨收": None,
            "成交量": None,
            "成交额": None,
            "买一价": None,
            "卖一价": None,
            "买一量": None,
            "卖一量": None,
            "涨跌额": None,
            "涨跌幅": None,
        }])
        mock_ak.return_value = df
        feed = QuoteFeed()
        quotes = feed.get_quotes(["600036"])
        q = quotes["600036"]

        assert q.price == 0.0
        assert q.open == 0.0
        assert q.volume == 0

    @patch("akshare.stock_zh_a_spot_em")
    def test_empty_dataframe(self, mock_ak):
        mock_ak.return_value = pd.DataFrame()
        feed = QuoteFeed()
        quotes = feed.get_quotes(["600036"])
        assert quotes == {}

    def test_persist_quotes_without_catalog(self):
        """Should silently skip if no catalog."""
        feed = QuoteFeed(catalog=None)
        feed.persist_quotes({})  # Should not raise
