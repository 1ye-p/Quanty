"""测试 ML 预测管道工具函数。"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from cquant.datahub.catalog import Catalog
from cquant.ml_lab.pipeline import run_ml_prediction_pipeline

_REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture()
def catalog_with_features(tmp_path):
    cat = Catalog(db_path=tmp_path / "test.duckdb", repo_root=_REPO_ROOT)
    cat.initialize()
    rng = np.random.default_rng(42)
    n = 200
    dates = [date(2024, 1, 1) + timedelta(days=i) for i in range(n)]
    assets = ["SSE:600036", "SSE:000001"]
    rows = []
    for d in dates:
        for a in assets:
            rows.append({
                "asset_id": a,
                "trade_date": d,
                "ret_5d": float(rng.normal(0.001, 0.02)),
                "vol_20d": float(abs(rng.normal(0.15, 0.05))),
                "ret_20d": float(rng.normal(0.005, 0.03)),
            })
    return cat, pl.DataFrame(rows)


class TestMLPredictionPipeline:
    def test_returns_model_id(self, catalog_with_features) -> None:
        cat, features = catalog_with_features
        model_id = run_ml_prediction_pipeline(
            catalog=cat,
            features=features,
            target_col="ret_5d",
            model_id_prefix="test",
            n_splits=2,
        )
        assert isinstance(model_id, str)
        assert len(model_id) > 0

    def test_predictions_written_to_gold_predictions(self, catalog_with_features) -> None:
        cat, features = catalog_with_features
        model_id = run_ml_prediction_pipeline(
            catalog=cat,
            features=features,
            target_col="ret_5d",
            model_id_prefix="test2",
            n_splits=2,
        )
        preds = cat.query(
            "SELECT COUNT(*) as n FROM gold_predictions WHERE model_version LIKE ?",
            [f"{model_id}%"],
        )
        assert preds["n"][0] > 0
