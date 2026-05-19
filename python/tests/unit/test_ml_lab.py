"""Unit tests for ml_lab module.

Tests trainer base, XGBoost trainer, dataset splitting, and walk-forward validation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import polars as pl
import pytest

from cquant.ml_lab.base import (
    ModelArtifact,
    Trainer,
    build_model_id,
    ensure_model_dir,
    frame_to_matrix,
    infer_feature_names,
    regression_metrics,
    target_to_vector,
)
from cquant.ml_lab.datasets import MLDataset
from cquant.ml_lab.walk_forward import WalkForwardValidator


# ── Base Utilities Tests ──────────────────────────────────────────────────────

class TestBaseUtilities:
    def test_infer_feature_names_auto(self):
        df = pl.DataFrame({
            "asset_id": ["A", "B"],
            "trade_date": [datetime(2025, 1, 1), datetime(2025, 1, 2)],
            "feature_1": [1.0, 2.0],
            "feature_2": [3.0, 4.0],
            "target": [0.1, 0.2],
        })
        features = infer_feature_names(df, "target")
        assert "feature_1" in features
        assert "feature_2" in features
        assert "target" not in features
        assert "asset_id" not in features

    def test_infer_feature_names_configured(self):
        df = pl.DataFrame({
            "f1": [1.0, 2.0],
            "f2": [3.0, 4.0],
            "target": [0.1, 0.2],
        })
        features = infer_feature_names(df, "target", configured=["f1"])
        assert features == ["f1"]

    def test_infer_feature_names_missing_column(self):
        df = pl.DataFrame({"f1": [1.0], "target": [0.1]})
        with pytest.raises(ValueError, match="not found"):
            infer_feature_names(df, "target", configured=["missing_col"])

    def test_frame_to_matrix(self):
        df = pl.DataFrame({"a": [1.0, 2.0], "b": [3.0, 4.0]})
        matrix = frame_to_matrix(df, ["a", "b"])
        assert matrix.shape == (2, 2)
        assert matrix.dtype == np.float64

    def test_frame_to_matrix_handles_nulls(self):
        df = pl.DataFrame({"a": [1.0, None], "b": [3.0, float("nan")]})
        matrix = frame_to_matrix(df, ["a", "b"])
        assert not np.isnan(matrix).any()
        assert matrix[1, 0] == 0.0

    def test_target_to_vector(self):
        df = pl.DataFrame({"target": [1.0, 2.0, 3.0]})
        vec = target_to_vector(df, "target")
        assert len(vec) == 3
        assert vec[0] == 1.0

    def test_target_to_vector_missing_column(self):
        df = pl.DataFrame({"other": [1.0]})
        with pytest.raises(ValueError, match="not found"):
            target_to_vector(df, "target")

    def test_regression_metrics(self):
        y_true = np.array([1.0, 2.0, 3.0])
        y_pred = np.array([1.1, 2.2, 2.8])
        metrics = regression_metrics(y_true, y_pred)
        assert "rmse" in metrics
        assert "mae" in metrics
        assert "r2" in metrics
        assert "directional_accuracy" in metrics
        assert metrics["rmse"] > 0

    def test_build_model_id_random(self):
        config = {}
        model_id = build_model_id(config, "xgb")
        assert model_id.startswith("xgb-")

    def test_build_model_id_configured(self):
        config = {"model_id": "my-model"}
        model_id = build_model_id(config, "xgb")
        assert model_id == "my-model"

    def test_ensure_model_dir_creates_directory(self, tmp_path):
        config = {"model_dir": str(tmp_path / "test_models")}
        model_dir = ensure_model_dir(config, "xgb")
        assert model_dir.exists()


# ── MLDataset Tests ───────────────────────────────────────────────────────────

class TestMLDataset:
    def test_train_valid_test_split(self):
        from datetime import timedelta
        base = datetime(2025, 1, 1)
        dates = [base + timedelta(days=i) for i in range(100)]
        df = pl.DataFrame({
            "trade_date": dates,
            "asset_id": ["SSE:600036"] * 100,
            "feature_1": np.random.randn(100).tolist(),
            "target": np.random.randn(100).tolist(),
        })
        dataset = MLDataset(data=df, feature_names=["feature_1"], target_name="target")
        train, valid, test = dataset.train_valid_test_split(train_ratio=0.6, valid_ratio=0.2)

        assert train.height == 60
        assert valid.height == 20
        assert test.height == 20

    def test_split_preserves_time_order(self):
        from datetime import timedelta
        base = datetime(2025, 1, 1)
        dates = [base + timedelta(days=i) for i in range(10)]
        df = pl.DataFrame({
            "trade_date": dates,
            "asset_id": ["SSE:600036"] * 10,
            "feature_1": list(range(10)),
            "target": list(range(10)),
        })
        dataset = MLDataset(data=df, feature_names=["feature_1"], target_name="target")
        train, valid, test = dataset.train_valid_test_split(train_ratio=0.6, valid_ratio=0.2)

        assert train["trade_date"].max() < valid["trade_date"].min()
        assert valid["trade_date"].max() < test["trade_date"].min()


# ── WalkForwardValidator Tests ────────────────────────────────────────────────

class TestWalkForwardValidator:
    def _make_dates(self, n: int):
        from datetime import timedelta
        base = datetime(2025, 1, 1)
        return [base + timedelta(days=i) for i in range(n)]

    def test_walk_forward_generates_folds(self):
        dates = self._make_dates(100)
        df = pl.DataFrame({
            "trade_date": dates,
            "feature_1": np.random.randn(100).tolist(),
            "target": np.random.randn(100).tolist(),
        })

        validator = WalkForwardValidator(n_splits=5, gap_days=0)
        folds = list(validator.split(df))

        assert len(folds) > 0
        for train_df, valid_df in folds:
            assert train_df.height > 0
            assert valid_df.height > 0

    def test_walk_forward_no_lookahead(self):
        dates = self._make_dates(100)
        df = pl.DataFrame({
            "trade_date": dates,
            "feature_1": list(range(100)),
            "target": list(range(100)),
        })

        validator = WalkForwardValidator(n_splits=5, gap_days=0)
        folds = list(validator.split(df))

        for train_df, valid_df in folds:
            assert train_df["trade_date"].max() < valid_df["trade_date"].min()

    def test_walk_forward_with_gap(self):
        dates = self._make_dates(100)
        df = pl.DataFrame({
            "trade_date": dates,
            "feature_1": list(range(100)),
            "target": list(range(100)),
        })

        validator = WalkForwardValidator(n_splits=3, gap_days=5)
        folds = list(validator.split(df))

        assert len(folds) > 0
        for train_df, valid_df in folds:
            gap = (valid_df["trade_date"].min() - train_df["trade_date"].max()).days
            assert gap >= 5


# ── ModelArtifact Tests ───────────────────────────────────────────────────────

class TestModelArtifact:
    def test_artifact_creation(self):
        artifact = ModelArtifact(
            model_id="test-model",
            trainer_name="xgboost_regressor",
            feature_names=["f1", "f2"],
            target_name="target",
            trained_at=datetime.now(tz=timezone.utc),
            metrics={"rmse": 0.5},
            model_path="/tmp/model.json",
            metadata={},
        )
        assert artifact.model_id == "test-model"
        assert artifact.trainer_name == "xgboost_regressor"
        assert len(artifact.feature_names) == 2


# ── XGBClassifierTrainer Tests ────────────────────────────────────────────────

class TestXGBClassifierTrainer:
    def test_classifier_fit_and_predict(self):
        from cquant.ml_lab.trainers.xgb_classifier import XGBClassifierTrainer

        trainer = XGBClassifierTrainer()
        train = pl.DataFrame({
            "feature_1": [1.0, 2.0, 3.0, 4.0, 5.0] * 20,
            "feature_2": [5.0, 4.0, 3.0, 2.0, 1.0] * 20,
            "target": [0, 1, 0, 1, 0] * 20,
        })
        valid = pl.DataFrame({
            "feature_1": [1.5, 2.5, 3.5],
            "feature_2": [4.5, 3.5, 2.5],
            "target": [0, 1, 0],
        })

        artifact = trainer.fit(train, valid, {"target_name": "target"})
        assert artifact.trainer_name == "xgboost_classifier"
        assert "accuracy" in artifact.metrics
        assert "f1" in artifact.metrics
        assert "feature_importance" in artifact.metadata

        predictions = trainer.predict(valid, artifact)
        assert len(predictions) == 3

    def test_classifier_name(self):
        from cquant.ml_lab.trainers.xgb_classifier import XGBClassifierTrainer
        assert XGBClassifierTrainer.name == "xgboost_classifier"
