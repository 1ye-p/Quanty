"""Tests for walk-forward ML pipeline fixes."""
from __future__ import annotations

import polars as pl
import pytest
from unittest.mock import MagicMock, patch
from datetime import date, datetime, timezone

from cquant.ml_lab.base import ModelArtifact, persist_predictions


def _make_artifact(model_id: str = "lgbm-abc") -> ModelArtifact:
    return ModelArtifact(
        model_id=model_id,
        trainer_name="lightgbm_regressor",
        feature_names=["f1", "f2"],
        target_name="ret_5d",
        trained_at=datetime.now(tz=timezone.utc),
        metrics={"rmse": 0.1},
        model_path="/tmp/model.txt",
    )


def _make_features(n: int = 5) -> pl.DataFrame:
    return pl.DataFrame({
        "asset_id": [f"SH{600000 + i}" for i in range(n)],
        "trade_date": [date(2025, 1, 1 + i) for i in range(n)],
        "f1": [float(i) for i in range(n)],
        "f2": [float(i * 2) for i in range(n)],
    })


def test_persist_predictions_with_fold_id():
    """persist_predictions should append fold_id to model_version when provided."""
    artifact = _make_artifact("lgbm-abc")
    features = _make_features(3)
    predictions = pl.Series("prediction", [0.01, 0.02, 0.03])

    catalog = MagicMock()
    conn = MagicMock()
    catalog._get_conn.return_value = conn

    persist_predictions(artifact, features, predictions, catalog, horizon="5d", fold_id="fold0")

    # Verify the Arrow table contains the composite model_version
    register_call = conn.register.call_args
    arrow_table = register_call[0][1]
    model_versions = arrow_table.column("model_version").to_pylist()
    assert all(v == "lgbm-abc_fold0" for v in model_versions), (
        f"Expected 'lgbm-abc_fold0', got {model_versions}"
    )


def test_persist_predictions_without_fold_id():
    """persist_predictions should use original model_id when fold_id is None."""
    artifact = _make_artifact("lgbm-abc")
    features = _make_features(3)
    predictions = pl.Series("prediction", [0.01, 0.02, 0.03])

    catalog = MagicMock()
    conn = MagicMock()
    catalog._get_conn.return_value = conn

    persist_predictions(artifact, features, predictions, catalog, horizon="5d")

    # Verify the Arrow table uses the original model_id (no fold_id suffix)
    register_call = conn.register.call_args
    arrow_table = register_call[0][1]
    model_versions = arrow_table.column("model_version").to_pylist()
    assert all(v == "lgbm-abc" for v in model_versions)


def test_pipeline_persists_all_folds():
    """run_ml_prediction_pipeline should persist OOS predictions for each fold, not just the last."""
    catalog = MagicMock()
    conn = MagicMock()
    catalog._get_conn.return_value = conn
    catalog.execute = MagicMock()

    # Create features with enough dates for 3 splits
    dates = [date(2025, 1, 1 + i) for i in range(30)]
    features = pl.DataFrame({
        "asset_id": ["SH600000"] * 30,
        "trade_date": dates,
        "f1": [float(i) for i in range(30)],
        "ret_5d": [0.01 * (i % 5 - 2) for i in range(30)],
    })

    with patch("cquant.ml_lab.trainers.lgbm.LGBMTrainer") as MockTrainer:
        mock_trainer = MagicMock()
        MockTrainer.return_value = mock_trainer

        # Mock fit to return an artifact
        artifact = _make_artifact("lgbm-test")
        mock_trainer.fit.return_value = artifact

        # Mock predict to return predictions
        mock_trainer.predict.return_value = pl.Series("prediction", [0.01] * 10)

        from cquant.ml_lab.pipeline import run_ml_prediction_pipeline

        model_id = run_ml_prediction_pipeline(
            catalog=catalog,
            features=features,
            target_col="ret_5d",
            model_id_prefix="test",
            n_splits=3,
            gap_days=0,
        )

    # Should return a composite model_id
    assert "wf_3folds" in model_id

    # Should have called predict_and_persist for each fold (3 times)
    assert mock_trainer.predict_and_persist.call_count == 3

    # Each call should use valid_df (OOS data), not full features
    for call in mock_trainer.predict_and_persist.call_args_list:
        called_features = call.kwargs.get("features", None)
        if called_features is None:
            called_features = call.args[0]
        # Each fold's features should be a subset (OOS period)
        assert called_features.height < features.height


def test_lgbm_predict_and_persist_forwards_fold_id():
    """LGBMTrainer.predict_and_persist should forward fold_id to persist_predictions."""
    from cquant.ml_lab.trainers.lgbm import LGBMTrainer

    trainer = LGBMTrainer()
    artifact = _make_artifact("lgbm-abc")
    features = _make_features(3)
    predictions = pl.Series("prediction", [0.01, 0.02, 0.03])

    catalog = MagicMock()
    conn = MagicMock()
    catalog._get_conn.return_value = conn

    with patch.object(trainer, "predict", return_value=predictions), \
         patch("cquant.ml_lab.base.persist_predictions") as mock_persist:
        trainer.predict_and_persist(features, artifact, catalog, horizon="5d", fold_id="fold0")

    # Verify fold_id was forwarded to persist_predictions
    mock_persist.assert_called_once()
    call_kwargs = mock_persist.call_args.kwargs
    assert call_kwargs.get("fold_id") == "fold0"


def test_ml_strategy_queries_composite_model_id():
    """MLModelStrategy should use LIKE prefix match for composite model_ids."""
    from cquant.backtest_vector.strategies.ml_strategy import MLModelStrategy
    from cquant.backtest_vector.strategy import StrategyContext

    strategy = MLModelStrategy(
        strategy_id="test",
        model_version="ml_wf_3folds",
        top_n=5,
        label_name="ret_5d",
    )

    catalog = MagicMock()
    # Mock query to return predictions from multiple folds
    catalog.query.return_value = pl.DataFrame({
        "asset_id": ["SH600000", "SH600001", "SH600002"],
        "prediction": [0.05, 0.03, 0.01],
    })

    ctx = StrategyContext(
        as_of_date=date(2025, 1, 15),
        universe_id="",
        extra={"catalog": catalog},
    )

    strategy.generate_signals(ctx)

    # Verify the query uses LIKE for prefix matching
    query_call = catalog.query.call_args
    sql = query_call[0][0]
    assert "LIKE" in sql or "like" in sql
    params = query_call[0][1]
    assert params[0] == "ml_wf_3folds%"  # prefix match


def test_rolling_config_defaults():
    """RollingConfig should have sensible defaults."""
    from cquant.qlib_bridge.ml_rolling import RollingConfig

    cfg = RollingConfig()
    assert cfg.n_splits == 3
    assert cfg.gap_days == 5
    assert cfg.window_type == "expanding"


def test_generate_rolling_splits_native():
    """generate_rolling_splits should produce date ranges for each fold (native fallback)."""
    from cquant.qlib_bridge.ml_rolling import RollingConfig, generate_rolling_splits
    from datetime import timedelta

    base = date(2024, 1, 1)
    dates = [base + timedelta(days=i) for i in range(60)]
    cfg = RollingConfig(n_splits=3, gap_days=2, window_type="expanding")

    splits = generate_rolling_splits(dates, cfg)

    assert len(splits) == 3
    for split in splits:
        assert split.train_start <= split.train_end
        assert split.test_start <= split.test_end
        assert split.train_end < split.test_start  # no overlap
