"""Unit tests for trading API routes.

Tests order placement, cancellation, position queries, and account state.
Uses mocked QuoteFeed to avoid real AKShare calls.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from cquant.api_server.routes.trading import router


# ── Setup ─────────────────────────────────────────────────────────────────────

def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return app


async def _call(app: FastAPI, method: str, path: str, **kwargs):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        return await c.request(method, path, **kwargs)


# ── Mock QuoteFeed ────────────────────────────────────────────────────────────

class MockQuote:
    def __init__(self, asset_id: str, price: float):
        self.asset_id = asset_id
        self.price = price


def _mock_get_quotes(symbols):
    """Return mock quotes for testing."""
    prices = {"600036": 35.50, "000001": 12.80}
    return {s: MockQuote(f"SSE:{s}", prices.get(s, 10.0)) for s in symbols if s in prices}


# ── Order Validation Tests ────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestOrderValidation:
    def setup_method(self):
        self.app = _make_app()

    async def test_invalid_qty_rejected(self):
        resp = await _call(self.app, "POST", "/api/v1/trading/order", json={
            "asset_id": "SSE:600036",
            "side": "buy",
            "qty": -100,
        })
        assert resp.status_code == 422  # Pydantic validation error

    async def test_zero_qty_rejected(self):
        resp = await _call(self.app, "POST", "/api/v1/trading/order", json={
            "asset_id": "SSE:600036",
            "side": "buy",
            "qty": 0,
        })
        assert resp.status_code == 422

    async def test_invalid_side_rejected(self):
        resp = await _call(self.app, "POST", "/api/v1/trading/order", json={
            "asset_id": "SSE:600036",
            "side": "hold",
            "qty": 100,
        })
        assert resp.status_code == 422

    async def test_invalid_asset_id_rejected(self):
        resp = await _call(self.app, "POST", "/api/v1/trading/order", json={
            "asset_id": "600036",  # Missing exchange prefix
            "side": "buy",
            "qty": 100,
        })
        assert resp.status_code == 422

    async def test_invalid_order_type_rejected(self):
        resp = await _call(self.app, "POST", "/api/v1/trading/order", json={
            "asset_id": "SSE:600036",
            "side": "buy",
            "qty": 100,
            "order_type": "stop",
        })
        assert resp.status_code == 422


# ── Order Placement Tests ─────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestOrderPlacement:
    def setup_method(self):
        self.app = _make_app()
        # Reset singleton broker
        import cquant.api_server.routes.trading as trading_module
        trading_module._paper_broker = None

    @patch("cquant.api_server.routes.trading._get_paper_broker")
    @patch("cquant.datahub.connectors.realtime_connector.QuoteFeed")
    async def test_market_buy_order_filled(self, mock_feed_cls, mock_broker_getter):
        from cquant.execution.paper_broker import PaperBroker

        broker = PaperBroker(initial_cash=1_000_000)
        mock_broker_getter.return_value = broker

        mock_feed = MagicMock()
        mock_feed.get_quotes = _mock_get_quotes
        mock_feed_cls.return_value = mock_feed

        resp = await _call(self.app, "POST", "/api/v1/trading/order", json={
            "asset_id": "SSE:600036",
            "side": "buy",
            "qty": 1000,
            "broker": "paper",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "filled"
        assert body["filled_qty"] == 1000
        assert body["filled_price"] > 0

    @patch("cquant.api_server.routes.trading._get_paper_broker")
    async def test_limit_order_rejected_by_paper_broker(self, mock_broker_getter):
        from cquant.execution.paper_broker import PaperBroker

        broker = PaperBroker(initial_cash=1_000_000)
        mock_broker_getter.return_value = broker

        resp = await _call(self.app, "POST", "/api/v1/trading/order", json={
            "asset_id": "SSE:600036",
            "side": "buy",
            "qty": 1000,
            "order_type": "limit",
            "limit_price": 35.00,
            "broker": "paper",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "rejected"
        assert "market orders only" in body["reject_reason"]


# ── Account & Position Tests ──────────────────────────────────────────────────

@pytest.mark.asyncio
class TestAccountQueries:
    def setup_method(self):
        self.app = _make_app()
        import cquant.api_server.routes.trading as trading_module
        trading_module._paper_broker = None

    @patch("cquant.api_server.routes.trading._get_paper_broker")
    async def test_get_account_returns_initial_state(self, mock_broker_getter):
        from cquant.execution.paper_broker import PaperBroker

        broker = PaperBroker(initial_cash=500_000)
        mock_broker_getter.return_value = broker

        resp = await _call(self.app, "GET", "/api/v1/trading/account", params={"broker": "paper"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["cash"] == 500_000
        assert body["nav"] == 500_000
        assert body["positions_count"] == 0

    @patch("cquant.api_server.routes.trading._get_paper_broker")
    async def test_get_positions_empty(self, mock_broker_getter):
        from cquant.execution.paper_broker import PaperBroker

        broker = PaperBroker()
        mock_broker_getter.return_value = broker

        resp = await _call(self.app, "GET", "/api/v1/trading/positions", params={"broker": "paper"})
        assert resp.status_code == 200
        assert resp.json()["items"] == []

    @patch("cquant.api_server.routes.trading._get_paper_broker")
    async def test_get_pnl_initial_state(self, mock_broker_getter):
        from cquant.execution.paper_broker import PaperBroker

        broker = PaperBroker(initial_cash=1_000_000)
        mock_broker_getter.return_value = broker

        resp = await _call(self.app, "GET", "/api/v1/trading/pnl", params={"broker": "paper"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["realized_pnl"] == 0.0
        assert body["unrealized_pnl"] == 0.0
        assert body["total_pnl"] == 0.0


# ── Unsupported Broker Tests ──────────────────────────────────────────────────

@pytest.mark.asyncio
class TestUnsupportedBroker:
    def setup_method(self):
        self.app = _make_app()

    async def test_qmt_broker_returns_400(self):
        resp = await _call(self.app, "GET", "/api/v1/trading/account", params={"broker": "qmt"})
        assert resp.status_code == 400
        assert "Unsupported broker" in resp.json()["detail"]
