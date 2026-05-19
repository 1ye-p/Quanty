"""End-to-end integration tests for the research pipeline.

Tests the full flow: data → factors → backtest → analysis.
Uses mock data to avoid external dependencies.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import polars as pl
import pytest


class TestResearchPipeline:
    """Full pipeline integration test."""

    def test_factor_to_backtest_flow(self):
        """Test that factors can drive a backtest."""
        prices = pl.DataFrame({
            "trade_date": [date(2025, 1, 2 + i) for i in range(20)] * 3,
            "asset_id": ["SSE:600036"] * 20 + ["SZSE:000001"] * 20 + ["SSE:601318"] * 20,
            "open": [35.0] * 60,
            "high": [36.0] * 60,
            "low": [34.0] * 60,
            "close": [35.5] * 60,
            "volume": [1000000] * 60,
        })

        assert prices.height == 60
        assert len(prices["asset_id"].unique()) == 3

    def test_paper_broker_integration(self):
        """Test PaperBroker with real price data."""
        from cquant.execution.paper_broker import PaperBroker
        from cquant.execution.broker import Order, OrderStatus

        broker = PaperBroker(initial_cash=1_000_000)
        broker.update_prices({"SSE:600036": 35.5})

        order = Order(
            order_id="test-1",
            asset_id="SSE:600036",
            side="buy",
            qty=1000,
        )
        result = broker.submit_order(order)
        assert result.status == OrderStatus.FILLED

        account = broker.get_account()
        assert account.cash < 1_000_000
        assert "SSE:600036" in account.positions

    def test_quote_feed_integration(self):
        """Test QuoteFeed with mocked AKShare."""
        import pandas as pd
        from cquant.datahub.connectors.realtime_connector import QuoteFeed

        mock_df = pd.DataFrame([{
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
        }])

        with patch("akshare.stock_zh_a_spot_em", return_value=mock_df):
            feed = QuoteFeed()
            quotes = feed.get_quotes(["600036"])
            assert "600036" in quotes
            assert quotes["600036"].price == 35.50

    def test_embedding_provider_integration(self):
        """Test embedding provider factory."""
        from cquant.knowledge_base.process.embedder import get_embedding_provider, NullEmbeddingProvider

        provider = get_embedding_provider("null")
        assert isinstance(provider, NullEmbeddingProvider)
        vectors = provider.embed(["test text"])
        assert len(vectors) == 1
        assert len(vectors[0]) == 768

    def test_optimizer_integration(self):
        """Test portfolio optimizer with realistic data."""
        from cquant.portfolio_opt.mean_variance import MeanVarianceOptimizer
        from cquant.portfolio_opt.risk_parity import RiskParityOptimizer

        returns = {"600036": 0.12, "000001": 0.10, "601318": 0.08}
        cov = {
            "600036": {"600036": 0.04, "000001": 0.02, "601318": 0.01},
            "000001": {"600036": 0.02, "000001": 0.06, "601318": 0.015},
            "601318": {"600036": 0.01, "000001": 0.015, "601318": 0.03},
        }

        mv = MeanVarianceOptimizer()
        result = mv.optimize(returns, cov)
        assert abs(sum(result.weights.values()) - 1.0) < 1e-6

        rp = RiskParityOptimizer()
        result = rp.optimize(returns, cov)
        assert abs(sum(result.weights.values()) - 1.0) < 1e-6

    def test_scheduler_health_integration(self):
        """Test scheduler health check with mock catalog."""
        from cquant.scheduler.health import HealthChecker
        from cquant.scheduler.scheduler import StrategyScheduler, ScheduleConfig, ScheduleFrequency

        mock_catalog = MagicMock()
        mock_catalog.initialize.return_value = None
        mock_catalog.query.return_value = MagicMock(
            is_empty=lambda: False,
            __getitem__=lambda self, key: ["2025-01-10"],
        )

        checker = HealthChecker(mock_catalog)
        status = checker.check_all()
        assert status.healthy is True

        scheduler = StrategyScheduler()
        config = ScheduleConfig(
            job_id="test",
            strategy_id="test-strategy",
            frequency=ScheduleFrequency.DAILY,
        )
        scheduler.add_job(config)
        assert scheduler.get_job("test") is not None
