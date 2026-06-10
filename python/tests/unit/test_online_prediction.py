"""Tests for online prediction enhancement — ModelRegistry and AccuracyTracker."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import polars as pl
import pytest

from cquant.ml_lab.model_registry import ModelRegistry
from cquant.ml_lab.accuracy import AccuracyTracker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_catalog() -> MagicMock:
    """Create a mock Catalog that behaves like a real one for registry/tracker."""
    cat = MagicMock()
    # Default: return empty DataFrame for queries
    cat.query.return_value = pl.DataFrame()
    return cat


def _mock_catalog_with_rows(rows: list[dict], columns: list[str] | None = None) -> MagicMock:
    """Create a mock Catalog whose query returns a specific DataFrame."""
    cat = MagicMock()
    if rows:
        cat.query.return_value = pl.DataFrame(rows)
    else:
        cat.query.return_value = pl.DataFrame()
    return cat


# ===========================================================================
# ModelRegistry tests
# ===========================================================================


class TestModelRegistry:
    """Tests for ModelRegistry lifecycle management."""

    def test_init_creates_table(self):
        cat = _mock_catalog()
        registry = ModelRegistry(cat)
        # execute should have been called with the DDL
        cat.execute.assert_called()
        ddl_call = cat.execute.call_args[0][0]
        assert "meta_model_registry" in ddl_call

    def test_register_model(self):
        cat = _mock_catalog()
        registry = ModelRegistry(cat)

        result = registry.register(
            model_id="lgbm-v1",
            model_version="lgbm-v1-20260607",
            trainer_name="lightgbm",
            artifact_path="/models/lgbm_v1.txt",
            feature_set_version="fs_v1",
            target_name="ret_5d",
            metrics={"rmse": 0.05},
            description="Test model",
        )

        assert result["model_id"] == "lgbm-v1"
        assert result["model_version"] == "lgbm-v1-20260607"
        assert result["stage"] == "staging"
        assert "registered_at" in result
        # execute called with INSERT
        execute_calls = [str(c) for c in cat.execute.call_args_list]
        assert any("INSERT" in c.upper() or "REPLACE" in c.upper() for c in execute_calls)

    def test_promote_model(self):
        cat = _mock_catalog()
        # First call: _get_row check (SELECT), second call: demote (UPDATE), third: promote (UPDATE)
        cat.query.return_value = pl.DataFrame({
            "model_id": ["lgbm-v1"],
            "model_version": ["v1"],
            "stage": ["staging"],
        })
        registry = ModelRegistry(cat)

        result = registry.promote("lgbm-v1", "v1")

        assert result["model_id"] == "lgbm-v1"
        assert result["model_version"] == "v1"
        assert result["stage"] == "production"
        assert "promoted_at" in result

    def test_promote_nonexistent_model_raises(self):
        cat = _mock_catalog()
        cat.query.return_value = pl.DataFrame()  # not found
        registry = ModelRegistry(cat)

        with pytest.raises(ValueError, match="not found"):
            registry.promote("nonexistent", "v1")

    def test_archive_model(self):
        cat = _mock_catalog()
        cat.query.return_value = pl.DataFrame({
            "model_id": ["lgbm-v1"],
            "model_version": ["v1"],
            "stage": ["production"],
        })
        registry = ModelRegistry(cat)

        result = registry.archive("lgbm-v1", "v1")

        assert result["model_id"] == "lgbm-v1"
        assert result["model_version"] == "v1"
        assert result["stage"] == "archived"
        assert "archived_at" in result

    def test_archive_nonexistent_model_raises(self):
        cat = _mock_catalog()
        cat.query.return_value = pl.DataFrame()
        registry = ModelRegistry(cat)

        with pytest.raises(ValueError, match="not found"):
            registry.archive("nonexistent", "v1")

    def test_get_production_returns_model(self):
        cat = _mock_catalog()
        cat.query.return_value = pl.DataFrame({
            "model_id": ["lgbm-v1"],
            "model_version": ["v1"],
            "trainer_name": ["lightgbm"],
            "stage": ["production"],
            "metrics_json": ['{"rmse": 0.05}'],
        })
        registry = ModelRegistry(cat)

        result = registry.get_production("lgbm-v1")

        assert result is not None
        assert result["model_id"] == "lgbm-v1"
        assert result["metrics"]["rmse"] == 0.05

    def test_get_production_returns_none_when_missing(self):
        cat = _mock_catalog()
        cat.query.return_value = pl.DataFrame()
        registry = ModelRegistry(cat)

        result = registry.get_production("nonexistent")
        assert result is None

    def test_list_models_all(self):
        cat = _mock_catalog()
        cat.query.return_value = pl.DataFrame({
            "model_id": ["m1", "m2"],
            "model_version": ["v1", "v1"],
            "stage": ["staging", "production"],
            "metrics_json": ['{}', '{}'],
        })
        registry = ModelRegistry(cat)

        result = registry.list_models()

        assert len(result) == 2

    def test_list_models_filtered_by_stage(self):
        cat = _mock_catalog()
        cat.query.return_value = pl.DataFrame({
            "model_id": ["m1"],
            "model_version": ["v1"],
            "stage": ["production"],
            "metrics_json": ['{}'],
        })
        registry = ModelRegistry(cat)

        result = registry.list_models(stage="production")

        assert len(result) == 1
        # Verify the query was called with stage filter
        query_calls = [str(c) for c in cat.query.call_args_list]
        assert any("production" in c for c in query_calls)

    def test_list_models_filtered_by_model_id(self):
        cat = _mock_catalog()
        cat.query.return_value = pl.DataFrame({
            "model_id": ["lgbm-v1"],
            "model_version": ["v1"],
            "stage": ["staging"],
            "metrics_json": ['{}'],
        })
        registry = ModelRegistry(cat)

        result = registry.list_models(model_id="lgbm-v1")

        assert len(result) == 1

    def test_list_models_empty(self):
        cat = _mock_catalog()
        cat.query.return_value = pl.DataFrame()
        registry = ModelRegistry(cat)

        result = registry.list_models()
        assert result == []


# ===========================================================================
# AccuracyTracker tests
# ===========================================================================


class TestAccuracyTracker:
    """Tests for AccuracyTracker metric computation."""

    def test_init_creates_table(self):
        cat = _mock_catalog()
        tracker = AccuracyTracker(cat)
        cat.execute.assert_called()
        ddl_call = cat.execute.call_args[0][0]
        assert "gold_prediction_accuracy" in ddl_call

    def test_compute_accuracy_perfect_correlation(self):
        cat = _mock_catalog()
        tracker = AccuracyTracker(cat)

        predictions = pl.DataFrame({
            "asset_id": ["A", "B", "C", "D", "E"],
            "prediction": [0.1, 0.2, 0.3, 0.4, 0.5],
        })
        realized = pl.DataFrame({
            "asset_id": ["A", "B", "C", "D", "E"],
            "return": [0.1, 0.2, 0.3, 0.4, 0.5],
        })

        result = tracker.compute_accuracy("model-v1", "2026-06-07", predictions, realized)

        assert result["ic"] == pytest.approx(1.0, abs=1e-6)
        assert result["rank_ic"] == pytest.approx(1.0, abs=1e-6)
        assert result["hit_rate"] == pytest.approx(1.0, abs=1e-6)
        assert result["sample_count"] == 5

    def test_compute_accuracy_inverse_correlation(self):
        cat = _mock_catalog()
        tracker = AccuracyTracker(cat)

        # Predictions decrease while returns increase => rank_ic = -1.0
        # Magnitudes arranged so IC is also negative
        predictions = pl.DataFrame({
            "asset_id": ["A", "B", "C", "D", "E"],
            "prediction": [0.5, 0.3, 0.1, -0.1, -0.3],
        })
        realized = pl.DataFrame({
            "asset_id": ["A", "B", "C", "D", "E"],
            "return": [-0.5, -0.3, -0.1, 0.1, 0.3],
        })

        result = tracker.compute_accuracy("model-v1", "2026-06-07", predictions, realized)

        assert result["ic"] == pytest.approx(-1.0, abs=1e-6)
        assert result["rank_ic"] == pytest.approx(-1.0, abs=1e-6)
        assert result["hit_rate"] == pytest.approx(0.0, abs=1e-6)

    def test_compute_accuracy_no_overlap(self):
        cat = _mock_catalog()
        tracker = AccuracyTracker(cat)

        predictions = pl.DataFrame({
            "asset_id": ["X", "Y"],
            "prediction": [0.1, 0.2],
        })
        realized = pl.DataFrame({
            "asset_id": ["A", "B"],
            "return": [0.1, 0.2],
        })

        result = tracker.compute_accuracy("model-v1", "2026-06-07", predictions, realized)

        assert result["sample_count"] == 0
        assert result["ic"] == 0.0
        assert result["rank_ic"] == 0.0
        assert result["hit_rate"] == 0.0

    def test_compute_accuracy_partial_match(self):
        cat = _mock_catalog()
        tracker = AccuracyTracker(cat)

        predictions = pl.DataFrame({
            "asset_id": ["A", "B", "C", "D", "E"],
            "prediction": [0.1, -0.2, 0.3, -0.4, 0.5],
        })
        realized = pl.DataFrame({
            "asset_id": ["A", "B", "C", "D", "E"],
            "return": [0.15, -0.25, 0.35, -0.45, 0.55],
        })

        result = tracker.compute_accuracy("model-v1", "2026-06-07", predictions, realized)

        assert result["sample_count"] == 5
        assert result["hit_rate"] == pytest.approx(1.0, abs=1e-6)  # all signs match
        assert result["ic"] > 0.9  # high correlation

    def test_compute_accuracy_persists_results(self):
        cat = _mock_catalog()
        tracker = AccuracyTracker(cat)

        predictions = pl.DataFrame({
            "asset_id": ["A", "B"],
            "prediction": [0.1, 0.2],
        })
        realized = pl.DataFrame({
            "asset_id": ["A", "B"],
            "return": [0.1, 0.2],
        })

        tracker.compute_accuracy("model-v1", "2026-06-07", predictions, realized)

        # Verify upsert was called
        cat.upsert.assert_called_once()
        upsert_args = cat.upsert.call_args[0]
        assert upsert_args[0] == "gold_prediction_accuracy"

    def test_get_accuracy_history(self):
        cat = _mock_catalog()
        cat.query.return_value = pl.DataFrame({
            "model_version": ["v1", "v1"],
            "eval_date": ["2026-06-07", "2026-06-06"],
            "metric_name": ["ic", "ic"],
            "metric_value": [0.8, 0.75],
            "sample_count": [100, 95],
            "computed_at": ["2026-06-07T00:00:00", "2026-06-06T00:00:00"],
        })
        tracker = AccuracyTracker(cat)

        history = tracker.get_accuracy_history("v1", metric_name="ic")

        assert len(history) == 2

    def test_get_accuracy_history_empty(self):
        cat = _mock_catalog()
        cat.query.return_value = pl.DataFrame()
        tracker = AccuracyTracker(cat)

        history = tracker.get_accuracy_history("nonexistent")
        assert history == []

    def test_get_latest_accuracy(self):
        cat = _mock_catalog()
        cat.query.return_value = pl.DataFrame({
            "metric_name": ["ic", "rank_ic", "hit_rate"],
            "metric_value": [0.85, 0.82, 0.71],
            "eval_date": ["2026-06-07", "2026-06-07", "2026-06-07"],
        })
        tracker = AccuracyTracker(cat)

        result = tracker.get_latest_accuracy("v1")

        assert result is not None
        assert result["ic"] == 0.85
        assert result["rank_ic"] == 0.82
        assert result["hit_rate"] == 0.71

    def test_get_latest_accuracy_returns_none_when_empty(self):
        cat = _mock_catalog()
        cat.query.return_value = pl.DataFrame()
        tracker = AccuracyTracker(cat)

        result = tracker.get_latest_accuracy("nonexistent")
        assert result is None
