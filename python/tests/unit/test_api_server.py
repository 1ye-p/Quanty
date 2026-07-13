"""Tests for cquant.api_server — FastAPI routes."""
from __future__ import annotations

from unittest.mock import MagicMock

import polars as pl
import pytest
from fastapi.testclient import TestClient

import cquant.api_server.deps as deps
from cquant.api_server.app import app


# ── Fixtures ─────────────────────────────────────────────────────────────────

def _mock_catalog() -> MagicMock:
    cat = MagicMock()
    cat.query.return_value = pl.DataFrame()
    cat.execute.return_value = None
    return cat


def _catalog_with_dataset() -> MagicMock:
    cat = MagicMock()
    cat.query.return_value = pl.DataFrame(
        {
            "version_id": ["tdx_v1"],
            "dataset_name": ["TDX Bulk"],
            "frequency": ["1d"],
            "start_date": ["2024-01-01"],
            "end_date": ["2025-12-31"],
            "asset_count": [6675],
            "row_count": [3_000_000],
            "source": ["tdx"],
            "created_at": ["2026-05-17T00:00:00"],
            "is_current": [True],
        }
    )
    return cat


def _mock_kb_service() -> MagicMock:
    from cquant.knowledge_base.schemas.search import SearchResponse, SearchQuery
    kb = MagicMock()
    result = SearchResponse(
        query=SearchQuery(text="test"),
        hits=[],
        total_found=0,
        latency_ms=0,
    )
    kb.search.return_value = result
    return kb


@pytest.fixture()
def client():
    app.dependency_overrides[deps.get_catalog] = _mock_catalog
    app.dependency_overrides[deps.get_kb_service] = _mock_kb_service
    with TestClient(app) as c:
        yield c
    app.dependency_overrides = {}


# ── Health ───────────────────────────────────────────────────────────────────

class TestHealth:
    def test_health_ok(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert "cquant" in body["service"]

    def test_health_has_service_field(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert "service" in resp.json()


# ── Datasets ─────────────────────────────────────────────────────────────────

class TestDatasets:
    def test_list_datasets_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/datasets")
        assert resp.status_code == 200
        body = resp.json()
        assert "items" in body
        assert isinstance(body["items"], list)
        assert body["total"] == 0

    def test_list_datasets_returns_rows(self, client: TestClient) -> None:
        app.dependency_overrides[deps.get_catalog] = _catalog_with_dataset
        resp = client.get("/api/v1/datasets")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["version_id"] == "tdx_v1"
        app.dependency_overrides[deps.get_catalog] = _mock_catalog

    def test_get_dataset_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/datasets/nonexistent_version")
        assert resp.status_code == 404


# ── Backtests ────────────────────────────────────────────────────────────────

class TestBacktests:
    def test_list_backtests_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/backtests")
        assert resp.status_code == 200
        body = resp.json()
        assert "items" in body

    def test_get_backtest_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/backtests/nonexistent_run_id")
        assert resp.status_code == 404


# ── Plugins ──────────────────────────────────────────────────────────────────

class TestPlugins:
    def test_list_plugins_returns_list(self, client: TestClient) -> None:
        resp = client.get("/api/v1/plugins")
        assert resp.status_code == 200
        body = resp.json()
        assert "items" in body
        assert isinstance(body["items"], list)


# ── Knowledge ────────────────────────────────────────────────────────────────

class TestKnowledge:
    def test_search_empty_results(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/knowledge/search",
            json={"text": "momentum factor A-shares", "top_k": 5},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "hits" in body
        assert isinstance(body["hits"], list)

    def test_search_returns_total_found(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/knowledge/search",
            json={"text": "momentum factor A-shares"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "total_found" in body

    def test_search_invalid_body_rejected(self, client: TestClient) -> None:
        resp = client.post("/api/v1/knowledge/search", json={})
        assert resp.status_code == 422


# ── OpenAPI schema ───────────────────────────────────────────────────────────

class TestOpenAPI:
    def test_openapi_schema_available(self, client: TestClient) -> None:
        resp = client.get("/api/openapi.json")
        assert resp.status_code == 200
        schema = resp.json()
        assert schema["info"]["title"] == "cQuant Research API"

    def test_docs_endpoint_available(self, client: TestClient) -> None:
        resp = client.get("/api/docs")
        assert resp.status_code == 200


# ── Share ─────────────────────────────────────────────────────────────────────

def _catalog_with_share() -> MagicMock:
    """Mock catalog that returns share data for get_share queries."""
    cat = MagicMock()

    def mock_query(sql, params=None):
        if "SELECT" in sql and "shares" in sql:
            return pl.DataFrame({
                "share_id": ["a1b2c3d4"],
                "content_type": ["backtest"],
                "content_id": ["run-123"],
                "created_by": ["test-user"],
                "created_at": ["2026-07-12T00:00:00+00:00"],
                "expires_at": [None],
            })
        return pl.DataFrame()

    cat.query.side_effect = mock_query
    cat.execute.return_value = None
    return cat


class TestShare:
    def test_create_share_returns_id(self, client: TestClient) -> None:
        resp = client.post("/api/v1/share", json={
            "content_type": "backtest",
            "content_id": "run-123",
            "created_by": "test-user",
        })
        assert resp.status_code == 201
        body = resp.json()
        assert "share_id" in body
        assert len(body["share_id"]) == 8
        assert body["url"].startswith("/share/")

    def test_create_share_with_defaults(self, client: TestClient) -> None:
        resp = client.post("/api/v1/share", json={
            "content_type": "strategy",
            "content_id": "strat-456",
        })
        assert resp.status_code == 201
        body = resp.json()
        assert "share_id" in body

    def test_create_share_invalid_content_type(self, client: TestClient) -> None:
        resp = client.post("/api/v1/share", json={
            "content_type": "invalid_type",
            "content_id": "run-123",
        })
        assert resp.status_code == 422

    def test_create_share_empty_content_id(self, client: TestClient) -> None:
        resp = client.post("/api/v1/share", json={
            "content_type": "backtest",
            "content_id": "",
        })
        assert resp.status_code == 422

    def test_get_share_returns_content(self, client: TestClient) -> None:
        app.dependency_overrides[deps.get_catalog] = _catalog_with_share
        resp = client.get("/api/v1/share/a1b2c3d4")
        assert resp.status_code == 200
        body = resp.json()
        assert body["share_id"] == "a1b2c3d4"
        assert body["content_type"] == "backtest"
        assert body["content_id"] == "run-123"
        app.dependency_overrides[deps.get_catalog] = _mock_catalog

    def test_get_share_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/share/nonexistent")
        assert resp.status_code == 404
