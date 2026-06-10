"""predict_service — model loading and online inference."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import polars as pl

logger = logging.getLogger(__name__)


def _load_model(trainer_name: str, model_path: str) -> Any:
    p = Path(model_path)
    if not p.exists():
        raise FileNotFoundError(f"Model file not found: {model_path}")

    if "lightgbm" in trainer_name:
        import lightgbm as lgb
        if p.is_dir():
            model_files = list(p.glob("**/*.txt"))
            if not model_files:
                raise FileNotFoundError(f"No LightGBM model file in {model_path}")
            return lgb.Booster(model_file=str(model_files[0]))
        return lgb.Booster(model_file=str(p))

    elif "xgboost" in trainer_name:
        import xgboost as xgb
        model = xgb.XGBRegressor()
        if p.is_dir():
            model_files = list(p.glob("**/*.json"))
            if not model_files:
                raise FileNotFoundError(f"No XGBoost model file in {model_path}")
            model.load_model(str(model_files[0]))
        else:
            model.load_model(str(p))
        return model

    else:
        raise ValueError(f"Unsupported trainer for prediction: {trainer_name}")


def _predict_with_model(model: Any, trainer_name: str, features: pl.DataFrame, feature_names: list[str]) -> pl.Series:
    import numpy as np

    X = features.select(feature_names).to_numpy().astype(np.float64)
    preds = model.predict(X)
    return pl.Series("prediction", preds)


def run_online_prediction(
    catalog,
    model_version: str,
    target_date: str | None = None,
    top_n: int = 50,
) -> dict:
    job_df = catalog.query(
        "SELECT job_id, trainer_name, artifact_path, feature_set_version, target_name "
        "FROM meta_ml_jobs WHERE mlflow_run_id = ? OR job_id = ?",
        [model_version, model_version],
    )
    if job_df.is_empty():
        raise ValueError(f"Model '{model_version}' not found in meta_ml_jobs")

    row = job_df.to_dicts()[0]
    trainer_name = row["trainer_name"]
    artifact_path = row["artifact_path"]
    feature_set_version = row["feature_set_version"]
    target_name = row["target_name"]

    if not artifact_path:
        raise ValueError(f"Model '{model_version}' has no persisted artifact_path")

    factor_df = catalog.query(
        "SELECT DISTINCT factor_name FROM gold_factor_values WHERE feature_set_version = ?",
        [feature_set_version],
    )
    all_factors = factor_df["factor_name"].to_list() if not factor_df.is_empty() else []
    feature_names = [f for f in all_factors if f != target_name]

    if not feature_names:
        raise ValueError(f"No factors found for feature_set_version='{feature_set_version}'")

    if target_date:
        pred_date = target_date
    else:
        date_df = catalog.query(
            "SELECT MAX(trade_date) as d FROM gold_factor_values WHERE feature_set_version = ?",
            [feature_set_version],
        )
        if date_df.is_empty() or date_df["d"][0] is None:
            raise ValueError(f"No factor data for feature_set_version='{feature_set_version}'")
        pred_date = str(date_df["d"][0])

    placeholders = ",".join(["?" for _ in feature_names])
    features_df = catalog.query(
        f"SELECT asset_id, trade_date, factor_name, value "
        f"FROM gold_factor_values "
        f"WHERE feature_set_version = ? AND trade_date = ? "
        f"  AND factor_name IN ({placeholders})",
        [feature_set_version, pred_date] + feature_names,
    )

    if features_df.is_empty():
        raise ValueError(f"No factor data for date={pred_date}, feature_set={feature_set_version}")

    pivot_df = features_df.pivot(
        values="value", index=["asset_id", "trade_date"], on="factor_name"
    )
    pivot_df = pivot_df.fill_null(0)

    model = _load_model(trainer_name, artifact_path)
    predictions = _predict_with_model(model, trainer_name, pivot_df, feature_names)

    result_df = pivot_df.select("asset_id").with_columns(predictions)
    result_df = result_df.sort("prediction", descending=True)
    result_df = result_df.with_columns(
        pl.arange(1, len(result_df) + 1).alias("rank")
    )
    top_df = result_df.head(top_n)

    # Persist all predictions to gold_predictions
    try:
        from cquant.ml_lab.base import persist_predictions, ModelArtifact
        from datetime import datetime, timezone

        artifact = ModelArtifact(
            model_id=model_version,
            trainer_name=trainer_name,
            feature_names=feature_names,
            target_name=target_name,
            trained_at=datetime.now(tz=timezone.utc),
            metrics={},
            model_path=artifact_path,
        )
        # Build a features DataFrame with asset_id + trade_date for persistence
        persist_features = pivot_df.select("asset_id").with_columns(
            pl.lit(pred_date).alias("trade_date"),
        )
        persist_predictions(artifact, persist_features, predictions, catalog)
        logger.info("Persisted %d predictions for model %s on %s", len(predictions), model_version, pred_date)
    except Exception as exc:
        logger.warning("Failed to persist predictions: %s", exc)

    predictions_list = [
        {"asset_id": row["asset_id"], "prediction": round(float(row["prediction"]), 6), "rank": int(row["rank"])}
        for row in top_df.to_dicts()
    ]

    return {
        "date": pred_date,
        "model_version": model_version,
        "trainer_name": trainer_name,
        "predictions": predictions_list,
        "total_assets": len(result_df),
        "top_n": top_n,
    }
