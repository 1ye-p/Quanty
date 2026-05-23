"""Tests for ML predictions persistence to gold_predictions."""
from __future__ import annotations

from datetime import date, datetime, timezone

import polars as pl
import pytest

from cquant.datahub.catalog import Catalog
from cquant.ml_lab.base import ModelArtifact, persist_predictions

_REPO_ROOT = __import__("pathlib").Path(__file__).resolve().parents[3]


def _make_artifact() -> ModelArtifact:
    return ModelArtifact(
        model_id="test_model_v1",
        trainer_name="lightgbm_regressor",
        feature_names=["ret_5d", "vol_20d"],
        target_name="ret_5d",
        trained_at=datetime.now(tz=timezone.utc),
        metrics={"rmse": 0.05},
        model_path="/tmp/test.txt",
        metadata={},
    )


def _make_features() -> pl.DataFrame:
    return pl.DataFrame({
        "asset_id": ["SSE:600036", "SSE:000001", "SSE:600519"],
        "trade_date": [date(2025, 6, 1)] * 3,
        "ret_5d": [0.02, -0.01, 0.03],
        "vol_20d": [0.15, 0.20, 0.12],
    })


def _make_predictions() -> pl.Series:
    return pl.Series(name="prediction", values=[0.025, -0.008, 0.031])


@pytest.fixture()
def catalog(tmp_path):
    db_file = tmp_path / "test.duckdb"
    cat = Catalog(db_path=db_file, repo_root=_REPO_ROOT)
    cat.initialize()
    return cat


class TestPersistPredictions:
    def test_writes_rows_to_gold_predictions(self, catalog: Catalog) -> None:
        artifact = _make_artifact()
        features = _make_features()
        predictions = _make_predictions()

        persist_predictions(
            artifact=artifact,
            features=features,
            predictions=predictions,
            catalog=catalog,
            horizon="5d",
        )

        result = catalog.query("SELECT * FROM gold_predictions")
        assert len(result) == 3
        assert set(result["asset_id"].to_list()) == {
            "SSE:600036", "SSE:000001", "SSE:600519"
        }
        assert result["model_version"][0] == "test_model_v1"
        assert result["horizon"][0] == "5d"
        assert result["label_name"][0] == "ret_5d"

    def test_persist_is_idempotent(self, catalog: Catalog) -> None:
        artifact = _make_artifact()
        features = _make_features()
        predictions = _make_predictions()

        persist_predictions(artifact, features, predictions, catalog, "5d")
        persist_predictions(artifact, features, predictions, catalog, "5d")

        result = catalog.query("SELECT COUNT(*) as n FROM gold_predictions")
        assert result["n"][0] == 3  # not 6

    def test_raises_if_features_missing_trade_date(self, catalog: Catalog) -> None:
        features_no_date = pl.DataFrame({
            "asset_id": ["A"],
            "ret_5d": [0.01],
        })
        artifact = _make_artifact()
        predictions = pl.Series(name="prediction", values=[0.01])

        with pytest.raises(ValueError, match="trade_date"):
            persist_predictions(artifact, features_no_date, predictions, catalog, "5d")
