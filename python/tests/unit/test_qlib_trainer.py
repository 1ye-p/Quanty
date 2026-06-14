"""Unit tests for QlibModelTrainer and pipeline routing."""

from __future__ import annotations

import pickle
from unittest.mock import MagicMock, patch

import numpy as np
import polars as pl
import pytest

from cquant.qlib_bridge.models import ModelInfo, is_qlib_model


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_features(n: int = 100, n_features: int = 6) -> pl.DataFrame:
    """Build a synthetic feature DataFrame with asset_id, trade_date, and target."""
    rng = np.random.default_rng(42)
    data = {
        "asset_id": [f"SH60000{i % 5}" for i in range(n)],
        "trade_date": sorted([f"2025-01-{(i % 28) + 1:02d}" for i in range(n)]),
    }
    for j in range(n_features):
        data[f"f_{j}"] = rng.standard_normal(n)
    data["ret_5d"] = rng.standard_normal(n) * 0.02
    return pl.DataFrame(data)


def _mock_model_info(name: str = "lstm", engine: str = "qlib") -> ModelInfo:
    return ModelInfo(
        name=name,
        display_name=name.upper(),
        model_type="deep_learning",
        engine=engine,
        description=f"Test {name}",
        default_params={"d_feat": 6, "hidden_size": 32, "n_epochs": 2},
        requires_alpha360=True,
        class_path="test.Model",
    )


class _FakeModel:
    """A picklable stand-in for a qlib model."""

    def __init__(self, **kwargs):
        self._params = kwargs
        self._rng = np.random.default_rng(42)

    def fit(self, X_train, y_train, X_valid=None, y_valid=None):
        pass

    def predict(self, X):
        return self._rng.standard_normal(len(X))


# ---------------------------------------------------------------------------
# QlibModelTrainer unit tests
# ---------------------------------------------------------------------------


class TestQlibModelTrainerInit:
    """Test QlibModelTrainer constructor validation."""

    @patch("cquant.qlib_bridge.models.ALL_MODELS", new_callable=dict)
    def test_init_rejects_unknown_model(self, mock_models):
        mock_models.clear()
        from cquant.ml_lab.trainers.qlib_trainer import QlibModelTrainer

        with pytest.raises(KeyError, match="Unknown model"):
            QlibModelTrainer("nonexistent_model")

    @patch("cquant.qlib_bridge.models.ALL_MODELS", new_callable=dict)
    def test_init_rejects_native_model(self, mock_models):
        mock_models.clear()
        mock_models["lgbm"] = _mock_model_info("lgbm", engine="native")
        from cquant.ml_lab.trainers.qlib_trainer import QlibModelTrainer

        with pytest.raises(ValueError, match="not 'qlib'"):
            QlibModelTrainer("lgbm")

    @patch("cquant.qlib_bridge.models.ALL_MODELS", new_callable=dict)
    def test_init_accepts_qlib_model(self, mock_models):
        mock_models.clear()
        mock_models["lstm"] = _mock_model_info("lstm", engine="qlib")
        from cquant.ml_lab.trainers.qlib_trainer import QlibModelTrainer

        trainer = QlibModelTrainer("lstm")
        assert trainer.model_name == "lstm"
        assert trainer.requires_alpha360 is True
        assert trainer.name == "qlib_lstm"


class TestQlibModelTrainerRequiresAlpha360:
    """Test requires_alpha360 property."""

    @patch("cquant.qlib_bridge.models.ALL_MODELS", new_callable=dict)
    def test_alpha360_true(self, mock_models):
        mock_models.clear()
        mock_models["lstm"] = _mock_model_info("lstm")
        from cquant.ml_lab.trainers.qlib_trainer import QlibModelTrainer

        trainer = QlibModelTrainer("lstm")
        assert trainer.requires_alpha360 is True

    @patch("cquant.qlib_bridge.models.ALL_MODELS", new_callable=dict)
    def test_alpha360_false(self, mock_models):
        mock_models.clear()
        mock_models["linear"] = ModelInfo(
            name="linear", display_name="Linear", model_type="linear",
            engine="qlib", description="test", requires_alpha360=False,
        )
        from cquant.ml_lab.trainers.qlib_trainer import QlibModelTrainer

        trainer = QlibModelTrainer("linear")
        assert trainer.requires_alpha360 is False


class TestQlibModelTrainerFit:
    """Test QlibModelTrainer.fit() with a picklable fake model."""

    @patch("cquant.ml_lab.trainers.qlib_trainer.QLIB_AVAILABLE", True)
    @patch("cquant.qlib_bridge.models.ALL_MODELS", new_callable=dict)
    @patch("cquant.qlib_bridge.models.create_model")
    def test_fit_returns_artifact(self, mock_create, mock_models, tmp_path):
        mock_models.clear()
        mock_models["lstm"] = _mock_model_info("lstm")
        mock_create.return_value = _FakeModel()

        from cquant.ml_lab.trainers.qlib_trainer import QlibModelTrainer

        trainer = QlibModelTrainer("lstm")
        train_df = _make_features(80)
        valid_df = _make_features(20)

        artifact = trainer.fit(train_df, valid_df, {
            "target_name": "ret_5d",
            "model_dir": str(tmp_path),
        })

        assert artifact.trainer_name == "qlib_lstm"
        assert artifact.target_name == "ret_5d"
        assert len(artifact.feature_names) == 6
        assert "rmse" in artifact.metrics
        assert "mae" in artifact.metrics
        assert artifact.metadata["model_name"] == "lstm"
        assert artifact.metadata["requires_alpha360"] is True

        mock_create.assert_called_once()

    @patch("cquant.ml_lab.trainers.qlib_trainer.QLIB_AVAILABLE", False)
    @patch("cquant.qlib_bridge.models.ALL_MODELS", new_callable=dict)
    @patch("cquant.qlib_bridge.models.create_model")
    def test_fit_raises_when_qlib_missing(self, mock_create, mock_models, tmp_path):
        mock_models.clear()
        mock_models["lstm"] = _mock_model_info("lstm")
        from cquant.ml_lab.trainers.qlib_trainer import QlibModelTrainer

        trainer = QlibModelTrainer("lstm")
        with pytest.raises(ImportError, match="qlib is required"):
            trainer.fit(_make_features(80), _make_features(20), {})
        mock_create.assert_not_called()

    @patch("cquant.ml_lab.trainers.qlib_trainer.QLIB_AVAILABLE", True)
    @patch("cquant.qlib_bridge.models.ALL_MODELS", new_callable=dict)
    @patch("cquant.qlib_bridge.models.create_model")
    def test_fit_with_empty_valid(self, mock_create, mock_models, tmp_path):
        mock_models.clear()
        mock_models["lstm"] = _mock_model_info("lstm")
        mock_create.return_value = _FakeModel()

        from cquant.ml_lab.trainers.qlib_trainer import QlibModelTrainer

        trainer = QlibModelTrainer("lstm")
        train_df = _make_features(80)
        empty_valid = train_df.clear()

        artifact = trainer.fit(train_df, empty_valid, {
            "target_name": "ret_5d",
            "model_dir": str(tmp_path),
        })
        assert artifact.metrics["rmse"] >= 0


class TestQlibModelTrainerPredict:
    """Test QlibModelTrainer.predict() with a pickled fake model."""

    @patch("cquant.ml_lab.trainers.qlib_trainer.QLIB_AVAILABLE", True)
    @patch("cquant.qlib_bridge.models.ALL_MODELS", new_callable=dict)
    @patch("cquant.qlib_bridge.models.create_model")
    def test_predict_returns_series(self, mock_create, mock_models, tmp_path):
        mock_models.clear()
        mock_models["lstm"] = _mock_model_info("lstm")
        mock_create.return_value = _FakeModel()

        from cquant.ml_lab.trainers.qlib_trainer import QlibModelTrainer

        trainer = QlibModelTrainer("lstm")
        train_df = _make_features(80)
        valid_df = _make_features(20)

        artifact = trainer.fit(train_df, valid_df, {
            "target_name": "ret_5d",
            "model_dir": str(tmp_path),
        })

        # predict() should load from disk and return a pl.Series
        pred_series = trainer.predict(valid_df, artifact)
        assert isinstance(pred_series, pl.Series)
        assert pred_series.name == "prediction"
        assert len(pred_series) == 20


# ---------------------------------------------------------------------------
# Pipeline routing tests
# ---------------------------------------------------------------------------


class TestPipelineRouting:
    """Test _create_trainer routing logic."""

    @patch("cquant.qlib_bridge.models.ALL_MODELS", new_callable=dict)
    def test_routes_lgbm_to_native(self, mock_models):
        mock_models.clear()
        mock_models["lgbm"] = ModelInfo(
            name="lgbm", display_name="LGBM", model_type="tree",
            engine="native", description="test",
        )
        from cquant.ml_lab.pipeline import _create_trainer
        from cquant.ml_lab.trainers.lgbm import LGBMTrainer

        trainer = _create_trainer("lgbm")
        assert isinstance(trainer, LGBMTrainer)

    @patch("cquant.qlib_bridge.models.ALL_MODELS", new_callable=dict)
    def test_routes_xgb_to_native(self, mock_models):
        mock_models.clear()
        mock_models["xgb"] = ModelInfo(
            name="xgb", display_name="XGB", model_type="tree",
            engine="native", description="test",
        )
        from cquant.ml_lab.pipeline import _create_trainer
        from cquant.ml_lab.trainers.xgb import XGBTrainer

        trainer = _create_trainer("xgb")
        assert isinstance(trainer, XGBTrainer)

    @patch("cquant.qlib_bridge.models.ALL_MODELS", new_callable=dict)
    def test_routes_lstm_to_qlib_trainer(self, mock_models):
        mock_models.clear()
        mock_models["lstm"] = _mock_model_info("lstm")
        from cquant.ml_lab.pipeline import _create_trainer
        from cquant.ml_lab.trainers.qlib_trainer import QlibModelTrainer

        trainer = _create_trainer("lstm")
        assert isinstance(trainer, QlibModelTrainer)
        assert trainer.model_name == "lstm"

    @patch("cquant.qlib_bridge.models.ALL_MODELS", new_callable=dict)
    def test_passes_model_params_to_qlib_trainer(self, mock_models):
        mock_models.clear()
        mock_models["transformer"] = _mock_model_info("transformer")
        from cquant.ml_lab.pipeline import _create_trainer
        from cquant.ml_lab.trainers.qlib_trainer import QlibModelTrainer

        params = {"n_epochs": 50, "lr": 0.01}
        trainer = _create_trainer("transformer", params)
        assert isinstance(trainer, QlibModelTrainer)
        assert trainer.model_params == params

    @patch("cquant.qlib_bridge.models.ALL_MODELS", new_callable=dict)
    def test_is_qlib_model_false_for_native(self, mock_models):
        mock_models.clear()
        mock_models["lgbm"] = ModelInfo(
            name="lgbm", display_name="LGBM", model_type="tree",
            engine="native", description="test",
        )
        assert is_qlib_model("lgbm") is False
        assert is_qlib_model("lstm") is False  # not in registry
