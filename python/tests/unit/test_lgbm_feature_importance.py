"""Tests for LGBMTrainer.feature_importance()."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from cquant.ml_lab.base import ModelArtifact
from cquant.ml_lab.trainers.lgbm import LGBMTrainer


def _make_artifact(feature_names=None):
    return ModelArtifact(
        model_id="test_model",
        trainer_name="lightgbm_regressor",
        feature_names=feature_names or ["ret_5d", "vol_20d", "pe_ttm"],
        target_name="ret_5d",
        trained_at=datetime.now(tz=timezone.utc),
        metrics={"rmse": 0.05},
        model_path="/tmp/test_model.txt",
        metadata={},
    )


class TestLGBMFeatureImportance:
    def test_method_exists(self) -> None:
        trainer = LGBMTrainer()
        assert hasattr(trainer, "feature_importance")

    def test_returns_dict_with_feature_names(self) -> None:
        trainer = LGBMTrainer()
        artifact = _make_artifact(["ret_5d", "vol_20d", "pe_ttm"])

        mock_booster = MagicMock()
        mock_booster.feature_importance.return_value = [10.0, 5.0, 3.0]

        with patch("lightgbm.Booster", return_value=mock_booster):
            result = trainer.feature_importance(artifact)

        assert set(result.keys()) == {"ret_5d", "vol_20d", "pe_ttm"}

    def test_values_are_floats(self) -> None:
        trainer = LGBMTrainer()
        artifact = _make_artifact(["f1", "f2"])

        mock_booster = MagicMock()
        mock_booster.feature_importance.return_value = [100, 50]

        with patch("lightgbm.Booster", return_value=mock_booster):
            result = trainer.feature_importance(artifact)

        for v in result.values():
            assert isinstance(v, float)

    def test_importance_type_passed_to_booster(self) -> None:
        trainer = LGBMTrainer()
        artifact = _make_artifact(["f1"])

        mock_booster = MagicMock()
        mock_booster.feature_importance.return_value = [1.0]

        with patch("lightgbm.Booster", return_value=mock_booster):
            trainer.feature_importance(artifact, importance_type="split")

        mock_booster.feature_importance.assert_called_once_with(importance_type="split")

    def test_default_importance_type_is_gain(self) -> None:
        trainer = LGBMTrainer()
        artifact = _make_artifact(["f1"])

        mock_booster = MagicMock()
        mock_booster.feature_importance.return_value = [1.0]

        with patch("lightgbm.Booster", return_value=mock_booster):
            trainer.feature_importance(artifact)

        mock_booster.feature_importance.assert_called_once_with(importance_type="gain")
