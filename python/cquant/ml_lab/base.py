"""cquant.ml_lab.base — Shared abstractions and utilities for ML trainers."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Sequence

if TYPE_CHECKING:
    from cquant.datahub.catalog import Catalog

import numpy as np
import polars as pl
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

_NUMERIC_DTYPES = frozenset(
    [
        pl.Int8, pl.Int16, pl.Int32, pl.Int64,
        pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64,
        pl.Float32, pl.Float64,
    ]
)
_RESERVED_COLUMNS = frozenset({"asset_id", "trade_date"})


@dataclass(frozen=True)
class ModelArtifact:
    """Serialized model metadata returned by trainer implementations."""

    model_id: str
    trainer_name: str
    feature_names: list[str]
    target_name: str
    trained_at: datetime
    metrics: dict[str, float]
    model_path: str
    metadata: dict[str, Any] = field(default_factory=dict)


class Trainer(ABC):
    """Common trainer contract for all ML backends."""

    name: str = ""

    @abstractmethod
    def fit(self, train: pl.DataFrame, valid: pl.DataFrame, config: dict) -> ModelArtifact:
        """Fit a model and return its serialized artifact."""

    @abstractmethod
    def predict(self, features: pl.DataFrame, model_artifact: ModelArtifact) -> pl.Series:
        """Generate predictions from *features* using *model_artifact*."""


def infer_feature_names(
    frame: pl.DataFrame,
    target_name: str,
    configured: Sequence[str] | None = None,
) -> list[str]:
    """Infer or validate the list of feature column names."""
    if configured:
        missing = [name for name in configured if name not in frame.columns]
        if missing:
            raise ValueError(f"Configured feature columns not found in DataFrame: {missing}")
        return list(configured)
    return [
        name
        for name, dtype in frame.schema.items()
        if name not in _RESERVED_COLUMNS and name != target_name and dtype in _NUMERIC_DTYPES
    ]


def frame_to_matrix(frame: pl.DataFrame, feature_names: Sequence[str]) -> np.ndarray:
    """Convert selected Polars columns to a float64 numpy matrix."""
    prepared = frame.select(
        [pl.col(name).cast(pl.Float64).fill_null(0.0).fill_nan(0.0) for name in feature_names]
    )
    return np.asarray(prepared.to_numpy(), dtype=np.float64)


def target_to_vector(frame: pl.DataFrame, target_name: str) -> np.ndarray:
    """Extract the target column as a float64 numpy array."""
    if target_name not in frame.columns:
        raise ValueError(f"Target column '{target_name}' not found in DataFrame")
    target = frame.get_column(target_name).cast(pl.Float64)
    if target.null_count() > 0:
        raise ValueError(f"Target column '{target_name}' contains {target.null_count()} null values")
    return np.asarray(target.to_numpy(), dtype=np.float64)


def regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    """Compute standard regression evaluation metrics."""
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    mae = float(mean_absolute_error(y_true, y_pred))
    try:
        r2 = float(r2_score(y_true, y_pred))
    except ValueError:
        r2 = 0.0
    directional_accuracy = (
        float((np.sign(y_true) == np.sign(y_pred)).mean()) if y_true.size else 0.0
    )
    return {"rmse": rmse, "mae": mae, "r2": r2, "directional_accuracy": directional_accuracy}


def ensure_model_dir(config: dict[str, Any], trainer_name: str) -> Path:
    """Return (and create) the model output directory."""
    configured = config.get("model_dir")
    base_dir = Path(configured) if configured else Path("artifacts") / "ml_lab" / trainer_name
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir


def build_model_id(config: dict[str, Any], trainer_name: str) -> str:
    """Return a stable or random model identifier."""
    configured = config.get("model_id")
    return str(configured) if configured else f"{trainer_name}-{uuid.uuid4()}"


def persist_feature_importance(
    artifact: "ModelArtifact",
    importance: dict[str, float],
    catalog: "Catalog",
    job_id: str = "",
) -> None:
    """Write feature importance scores to meta_feature_importance DuckDB table.

    Parameters
    ----------
    artifact:
        The model artifact whose ``model_id`` and ``trainer_name`` are used as keys.
    importance:
        Dict of feature_name -> importance_score.
    catalog:
        Open Catalog connection.
    job_id:
        Optional ML job ID for traceability.
    """
    if not importance:
        return

    conn = catalog._get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS meta_feature_importance (
            model_id      VARCHAR NOT NULL,
            job_id        VARCHAR NOT NULL DEFAULT '',
            trainer_name  VARCHAR NOT NULL,
            feature_name  VARCHAR NOT NULL,
            importance    DOUBLE NOT NULL,
            created_at    TIMESTAMP NOT NULL,
            PRIMARY KEY (model_id, feature_name)
        )
    """)

    now = datetime.now(tz=timezone.utc).isoformat()
    rows = [
        (artifact.model_id, job_id, artifact.trainer_name, feat, score, now)
        for feat, score in importance.items()
    ]
    stage_df = pl.DataFrame(
        rows,
        schema=["model_id", "job_id", "trainer_name", "feature_name", "importance", "created_at"],
        orient="row",
    )
    stage = "_fi_stage"
    conn.register(stage, stage_df.to_arrow())
    try:
        conn.execute(f"""
            INSERT OR REPLACE INTO meta_feature_importance
                (model_id, job_id, trainer_name, feature_name, importance, created_at)
            SELECT model_id, job_id, trainer_name, feature_name, importance, created_at
            FROM {stage}
        """)
    finally:
        try:
            conn.unregister(stage)
        except Exception:
            pass


def persist_predictions(
    artifact: "ModelArtifact",
    features: "pl.DataFrame",
    predictions: "pl.Series",
    catalog: "Catalog",
    horizon: str = "5d",
    fold_id: str | None = None,
) -> None:
    """Write model predictions to gold_predictions DuckDB table.

    Parameters
    ----------
    artifact:
        The model artifact whose ``model_id`` and ``target_name`` are used as keys.
    features:
        Feature DataFrame used for prediction. Must contain ``asset_id`` and ``trade_date``.
    predictions:
        Float predictions series with the same length as *features*.
    catalog:
        Open Catalog connection.
    horizon:
        Prediction horizon label, e.g. ``'5d'``.
    """
    import polars as pl

    if "trade_date" not in features.columns:
        raise ValueError("features must contain 'trade_date' column to persist predictions")
    if "asset_id" not in features.columns:
        raise ValueError("features must contain 'asset_id' column to persist predictions")

    model_version = f"{artifact.model_id}_{fold_id}" if fold_id else artifact.model_id

    pred_df = (
        features.select(["asset_id", "trade_date"])
        .with_columns([
            pl.lit(model_version).alias("model_version"),
            predictions.alias("prediction"),
            pl.lit(horizon).alias("horizon"),
            pl.lit(artifact.target_name).alias("label_name"),
            pl.lit(None).cast(pl.Float64).alias("confidence"),
        ])
        .select([
            "model_version", "trade_date", "asset_id",
            "prediction", "horizon", "label_name", "confidence",
        ])
    )

    conn = catalog._get_conn()
    stage = "_predictions_stage"
    conn.register(stage, pred_df.to_arrow())
    try:
        conn.execute(f"""
            INSERT OR REPLACE INTO gold_predictions
                (model_version, trade_date, asset_id, prediction, horizon, label_name, confidence)
            SELECT model_version, trade_date, asset_id, prediction, horizon, label_name, confidence
            FROM {stage}
        """)
    finally:
        try:
            conn.unregister(stage)
        except Exception:
            pass
