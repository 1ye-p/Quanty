"""cquant.ml_lab.base — Shared abstractions and utilities for ML trainers."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

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
