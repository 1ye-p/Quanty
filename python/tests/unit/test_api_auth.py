"""Tests for API Server Bearer Token authentication."""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import cquant.api_server.deps as deps
from cquant.api_server.app import app


@pytest.fixture()
def client():
    app.dependency_overrides[deps.get_catalog] = lambda: MagicMock()
    app.dependency_overrides[deps.get_kb_service] = lambda: MagicMock()
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides = {}


class TestAuthDisabledByDefault:
    def test_health_always_accessible(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_datasets_accessible_without_key_when_env_not_set(
        self, client: TestClient
    ) -> None:
        env = {k: v for k, v in os.environ.items() if k != "CQUANT_API_KEY"}
        with patch.dict(os.environ, env, clear=True):
            resp = client.get("/api/v1/datasets")
            assert resp.status_code == 200


class TestAuthEnabledWhenKeySet:
    def test_request_without_key_returns_401(self, client: TestClient) -> None:
        with patch.dict(os.environ, {"CQUANT_API_KEY": "test-secret-key"}):
            resp = client.get("/api/v1/datasets")
            assert resp.status_code == 401

    def test_request_with_correct_key_returns_200(self, client: TestClient) -> None:
        with patch.dict(os.environ, {"CQUANT_API_KEY": "test-secret-key"}):
            resp = client.get(
                "/api/v1/datasets",
                headers={"Authorization": "Bearer test-secret-key"},
            )
            assert resp.status_code == 200

    def test_request_with_wrong_key_returns_401(self, client: TestClient) -> None:
        with patch.dict(os.environ, {"CQUANT_API_KEY": "test-secret-key"}):
            resp = client.get(
                "/api/v1/datasets",
                headers={"Authorization": "Bearer wrong-key"},
            )
            assert resp.status_code == 401

    def test_health_still_accessible_when_key_set(self, client: TestClient) -> None:
        with patch.dict(os.environ, {"CQUANT_API_KEY": "test-secret-key"}):
            resp = client.get("/health")
            assert resp.status_code == 200
