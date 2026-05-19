"""Unit tests for new API route modules (news, strategies, live).

Uses FastAPI dependency overrides + httpx.AsyncClient for isolated HTTP-level tests.
No real database or MLflow connections are made.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import polars as pl
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from cquant.api_server.deps import get_catalog
from cquant.api_server.routes import live, news, strategies


# ── Shared helpers ────────────────────────────────────────────────────────────

def _make_app(catalog: MagicMock) -> FastAPI:
    """Build a minimal FastAPI app with the three tested routers + mock catalog."""
    app = FastAPI()
    prefix = "/api/v1"
    app.include_router(strategies.router, prefix=prefix)
    app.include_router(news.router, prefix=prefix)
    app.include_router(live.router, prefix=prefix)
    app.dependency_overrides[get_catalog] = lambda: catalog
    return app


async def _call(app: FastAPI, method: str, path: str, **kwargs):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        return await c.request(method, path, **kwargs)


# ── _parse_config (unit, sync) ────────────────────────────────────────────────

class TestParseConfig:
    def test_valid_json_returns_dict(self) -> None:
        result = strategies._parse_config('{"lookback": 20}', "json")
        assert result == {"lookback": 20}

    def test_invalid_json_returns_none(self) -> None:
        assert strategies._parse_config("{lookback: 20", "json") is None

    def test_empty_string_returns_none(self) -> None:
        assert strategies._parse_config("", "json") is None

    def test_toml_format_returns_none(self) -> None:
        assert strategies._parse_config('lookback = 20\n', "toml") is None


# ── Strategies routes ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestStrategiesRoutes:
    def setup_method(self) -> None:
        self.catalog = MagicMock()
        self.app = _make_app(self.catalog)

    async def test_list_returns_items(self) -> None:
        self.catalog.query.return_value = pl.DataFrame([{
            "strategy_id": "alpha", "config_format": "json",
            "universe_id": "cn", "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-02T00:00:00Z",
        }])
        resp = await _call(self.app, "GET", "/api/v1/strategies")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["strategy_id"] == "alpha"

    async def test_create_success_returns_201(self) -> None:
        self.catalog.query.return_value = pl.DataFrame()   # no duplicate
        resp = await _call(self.app, "POST", "/api/v1/strategies", json={
            "strategy_id": "alpha",
            "config_text": '{"lookback": 20}',
            "config_format": "json",
            "universe_id": "cn",
        })
        assert resp.status_code == 201
        assert resp.json() == {"strategy_id": "alpha", "status": "created"}
        # Verify parsed_config is stored as valid JSON
        insert_params = self.catalog.execute.call_args.args[1]
        assert json.loads(insert_params[3]) == {"lookback": 20}

    async def test_create_duplicate_returns_409(self) -> None:
        self.catalog.query.return_value = pl.DataFrame([{"strategy_id": "alpha"}])
        resp = await _call(self.app, "POST", "/api/v1/strategies", json={
            "strategy_id": "alpha",
            "config_text": '{"lookback": 20}',
            "config_format": "json",
        })
        assert resp.status_code == 409
        assert "already exists" in resp.json()["detail"]
        self.catalog.execute.assert_not_called()

    async def test_create_invalid_json_returns_422(self) -> None:
        resp = await _call(self.app, "POST", "/api/v1/strategies", json={
            "strategy_id": "alpha",
            "config_text": "{lookback: 20",
            "config_format": "json",
        })
        assert resp.status_code == 422
        assert resp.json()["detail"] == "config_text is not valid JSON"
        self.catalog.query.assert_not_called()
        self.catalog.execute.assert_not_called()

    async def test_get_existing_returns_200(self) -> None:
        self.catalog.query.return_value = pl.DataFrame([{
            "strategy_id": "alpha", "config_text": '{"lookback": 20}',
            "config_format": "json", "parsed_config": '{"lookback": 20}',
            "universe_id": "cn", "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }])
        resp = await _call(self.app, "GET", "/api/v1/strategies/alpha")
        assert resp.status_code == 200
        assert resp.json()["strategy_id"] == "alpha"

    async def test_get_missing_returns_404(self) -> None:
        self.catalog.query.return_value = pl.DataFrame()
        resp = await _call(self.app, "GET", "/api/v1/strategies/missing")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]

    async def test_update_existing_returns_200(self) -> None:
        self.catalog.query.return_value = pl.DataFrame([{"strategy_id": "alpha"}])
        resp = await _call(self.app, "PUT", "/api/v1/strategies/alpha", json={
            "config_text": '{"lookback": 40}',
            "config_format": "json",
        })
        assert resp.status_code == 200
        assert resp.json() == {"strategy_id": "alpha", "status": "updated"}
        update_params = self.catalog.execute.call_args.args[1]
        assert json.loads(update_params[2]) == {"lookback": 40}

    async def test_update_missing_returns_404(self) -> None:
        self.catalog.query.return_value = pl.DataFrame()
        resp = await _call(self.app, "PUT", "/api/v1/strategies/missing", json={
            "config_text": '{"lookback": 20}', "config_format": "json",
        })
        assert resp.status_code == 404
        self.catalog.execute.assert_not_called()

    async def test_update_invalid_json_returns_422(self) -> None:
        self.catalog.query.return_value = pl.DataFrame([{"strategy_id": "alpha"}])
        resp = await _call(self.app, "PUT", "/api/v1/strategies/alpha", json={
            "config_text": "{lookback: 20", "config_format": "json",
        })
        assert resp.status_code == 422
        self.catalog.execute.assert_not_called()

    async def test_delete_existing_returns_200(self) -> None:
        self.catalog.query.return_value = pl.DataFrame([{"strategy_id": "alpha"}])
        resp = await _call(self.app, "DELETE", "/api/v1/strategies/alpha")
        assert resp.status_code == 200
        assert resp.json() == {"strategy_id": "alpha", "status": "deleted"}
        self.catalog.execute.assert_called_once_with(
            "DELETE FROM meta_strategy_configs WHERE strategy_id = ?",
            ["alpha"],
        )

    async def test_delete_missing_returns_404(self) -> None:
        self.catalog.query.return_value = pl.DataFrame()
        resp = await _call(self.app, "DELETE", "/api/v1/strategies/nonexistent")
        assert resp.status_code == 404


# ── News routes ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestNewsRoutes:
    def setup_method(self) -> None:
        self.catalog = MagicMock()
        self.app = _make_app(self.catalog)

    async def test_list_events_with_filters_passes_correct_params(self) -> None:
        self.catalog.query.return_value = pl.DataFrame([{
            "event_id": "evt-1", "source": "reuters",
            "headline": "Company beats expectations",
            "published_at": "2024-01-02T00:00:00Z",
            "available_at": "2024-01-02T00:01:00Z",
            "asset_ids_mentioned": ["SSE:600036"],
            "sentiment_score": 0.9,
            "event_type": "earnings",
            "language": "zh-CN",
        }])
        resp = await _call(self.app, "GET", "/api/v1/news/events", params={
            "source": "reuters", "event_type": "earnings", "limit": 25,
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        sql, params = self.catalog.query.call_args.args
        assert "source = ?" in sql
        assert "event_type = ?" in sql
        assert "reuters" in params
        assert "earnings" in params
        assert 25 in params

    async def test_list_events_no_filters_returns_200(self) -> None:
        self.catalog.query.return_value = pl.DataFrame()
        resp = await _call(self.app, "GET", "/api/v1/news/events")
        assert resp.status_code == 200
        assert resp.json() == {"items": [], "total": 0}

    async def test_stats_returns_aggregated_data(self) -> None:
        self.catalog.query.side_effect = [
            pl.DataFrame({"n": [5]}),
            pl.DataFrame([{"source": "sina", "count": 3}, {"source": "reuters", "count": 2}]),
            pl.DataFrame([{"event_type": "news", "count": 5}]),
            pl.DataFrame({"avg_sentiment": [0.3]}),
        ]
        resp = await _call(self.app, "GET", "/api/v1/news/stats")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_events"] == 5
        assert body["source_counts"] == {"sina": 3, "reuters": 2}
        assert body["event_type_counts"] == {"news": 5}
        assert abs(body["avg_sentiment"] - 0.3) < 1e-6

    async def test_stats_null_sentiment_when_no_data(self) -> None:
        self.catalog.query.side_effect = [
            pl.DataFrame({"n": [0]}),
            pl.DataFrame({"source": [], "count": []}),
            pl.DataFrame({"event_type": [], "count": []}),
            pl.DataFrame({"avg_sentiment": [None]}),
        ]
        resp = await _call(self.app, "GET", "/api/v1/news/stats")
        assert resp.status_code == 200
        assert resp.json()["avg_sentiment"] is None


# ── Live routes ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestLiveRoutes:
    def setup_method(self) -> None:
        self.catalog = MagicMock()
        self.app = _make_app(self.catalog)

    async def test_list_strategies_empty_returns_banner(self) -> None:
        self.catalog.query.return_value = pl.DataFrame()
        resp = await _call(self.app, "GET", "/api/v1/live/strategies")
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["total"] == 0
        assert body["display_mode"] == live._DISPLAY_BANNER

    async def test_list_strategies_with_data_returns_items(self) -> None:
        self.catalog.query.return_value = pl.DataFrame([{
            "strategy_id": "momentum",
            "last_run_id": "run-1",
            "last_update": "2024-01-10T00:00:00Z",
            "status": "completed",
        }])
        resp = await _call(self.app, "GET", "/api/v1/live/strategies")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1
        assert resp.json()["items"][0]["strategy_id"] == "momentum"

    async def test_pnl_no_completed_run_returns_404(self) -> None:
        self.catalog.query.return_value = pl.DataFrame()
        resp = await _call(self.app, "GET", "/api/v1/live/strategies/alpha/pnl")
        assert resp.status_code == 404
        assert "No completed runs" in resp.json()["detail"]

    async def test_pnl_returns_series_and_banner(self) -> None:
        self.catalog.query.side_effect = [
            pl.DataFrame({"run_id": ["run-1"]}),
            pl.DataFrame([{
                "snapshot_ts": "2024-01-01T00:00:00Z",
                "drawdown": -0.05,
                "gross_leverage": 1.2,
                "net_leverage": 0.4,
                "var_95": 0.02,
            }]),
        ]
        resp = await _call(self.app, "GET", "/api/v1/live/strategies/alpha/pnl")
        assert resp.status_code == 200
        body = resp.json()
        assert body["run_id"] == "run-1"
        assert len(body["series"]) == 1
        assert body["display_mode"] == live._DISPLAY_BANNER
        # Verify limit=500 is appended
        _, pnl_params = self.catalog.query.call_args_list[1].args
        assert pnl_params[-1] == 500

    async def test_pnl_with_date_filters_adds_conditions(self) -> None:
        self.catalog.query.side_effect = [
            pl.DataFrame({"run_id": ["run-1"]}),
            pl.DataFrame(),
        ]
        resp = await _call(self.app, "GET", "/api/v1/live/strategies/alpha/pnl",
                          params={"from_date": "2024-01-01", "to_date": "2024-01-31"})
        assert resp.status_code == 200
        sql, params = self.catalog.query.call_args_list[1].args
        assert "snapshot_ts >= ?" in sql
        assert "snapshot_ts <= ?" in sql
        assert "2024-01-01" in params
        assert "2024-01-31" in params

    async def test_risk_returns_snapshot_history_and_banner(self) -> None:
        snap = {"strategy_id": "alpha", "snapshot_ts": "2024-01-10T00:00:00Z",
                "drawdown": -0.02, "gross_leverage": 1.1, "var_95": 0.03}
        self.catalog.query.side_effect = [
            pl.DataFrame([snap]),
            pl.DataFrame([snap]),
        ]
        resp = await _call(self.app, "GET", "/api/v1/live/strategies/alpha/risk")
        assert resp.status_code == 200
        body = resp.json()
        assert body["latest_snapshot"]["strategy_id"] == "alpha"
        assert len(body["history"]) == 1
        assert body["display_mode"] == live._DISPLAY_BANNER

    async def test_risk_no_snapshot_returns_null_latest(self) -> None:
        self.catalog.query.side_effect = [
            pl.DataFrame(),
            pl.DataFrame(),
        ]
        resp = await _call(self.app, "GET", "/api/v1/live/strategies/beta/risk")
        assert resp.status_code == 200
        assert resp.json()["latest_snapshot"] is None
        assert resp.json()["history"] == []
