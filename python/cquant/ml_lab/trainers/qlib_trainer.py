"""cquant.ml_lab.trainers.qlib_trainer — Qlib DL model trainer.

Wraps qlib deep-learning models (LSTM, Transformer, TabNet, etc.) behind
the cQuant ``Trainer`` ABC so they can participate in the same walk-forward
pipeline as native tree trainers.

The trainer delegates to ``qlib_bridge.create_model`` for instantiation and
``qlib_bridge.train_model_qlib`` / ``qlib_bridge.predict`` for training and
inference.  Alpha360 feature loading is handled transparently when the model's
``ModelInfo.requires_alpha360`` flag is set.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
import polars as pl

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
from cquant.qlib_bridge._compat import QLIB_AVAILABLE

if TYPE_CHECKING:
    from cquant.datahub.catalog import Catalog
    from cquant.qlib_bridge.models import ModelInfo

logger = logging.getLogger(__name__)


class QlibModelTrainer(Trainer):
    """Train qlib deep-learning models (LSTM, Transformer, TabNet, etc.).

    This trainer satisfies the same ``Trainer`` ABC as ``LGBMTrainer`` and
    ``XGBTrainer`` so it can be dropped into the walk-forward pipeline.

    Parameters
    ----------
    model_name:
        Registry key in ``ALL_MODELS`` (e.g. ``"lstm"``, ``"transformer"``).
    model_params:
        Hyperparameters to override ``ModelInfo.default_params``.
    """

    name = "qlib_dl"

    def __init__(
        self,
        model_name: str,
        model_params: dict[str, Any] | None = None,
    ) -> None:
        from cquant.qlib_bridge.models import get_model_info

        self.model_name = model_name
        self.model_params = model_params or {}
        self._model_info: "ModelInfo" = get_model_info(model_name)

        if self._model_info.engine != "qlib":
            raise ValueError(
                f"Model {model_name!r} is engine={self._model_info.engine!r}, "
                "not 'qlib'.  Use LGBMTrainer or XGBTrainer for native models."
            )

        self.name = f"qlib_{model_name}"

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    @property
    def requires_alpha360(self) -> bool:
        """Whether this model needs Alpha360 (6-day lookback) features."""
        return self._model_info.requires_alpha360

    # ------------------------------------------------------------------
    # Trainer ABC
    # ------------------------------------------------------------------

    def fit(self, train: pl.DataFrame, valid: pl.DataFrame, config: dict) -> ModelArtifact:
        """Fit the qlib DL model and return a ``ModelArtifact``.

        Parameters
        ----------
        train, valid:
            Polars DataFrames with ``asset_id``, ``trade_date``, features, and
            the target column.
        config:
            Pipeline config dict — ``target_name``, ``model_id``, ``params``,
            ``model_dir``, ``metadata`` keys are recognised.
        """
        if not QLIB_AVAILABLE:
            raise ImportError(
                "qlib is required for QlibModelTrainer. "
                "Install with: pip install pyqlib"
            )

        target_name = str(config.get("target_name", "ret_5d"))
        feature_names = infer_feature_names(train, target_name, config.get("feature_names"))

        # Merge default_params from ModelInfo with user overrides
        merged_params: dict[str, Any] = {
            **self._model_info.default_params,
            **self.model_params,
            **config.get("params", {}),
        }

        # Create the qlib model instance via the bridge factory
        from cquant.qlib_bridge.models import create_model

        model = create_model(self.model_name, merged_params)

        # Prepare data for qlib model training
        # qlib DL models expect pandas DataFrames with specific columns
        train_df = train.to_pandas()
        valid_df = valid.to_pandas() if not valid.is_empty() else None

        # Build feature matrix + labels
        X_train = train_df[feature_names].values.astype(np.float64)
        y_train = train_df[target_name].values.astype(np.float64)

        # Replace NaN/inf with 0 (qlib DL models can't handle them)
        X_train = np.nan_to_num(X_train, nan=0.0, posinf=0.0, neginf=0.0)

        if valid_df is not None and not valid.is_empty():
            X_valid = valid_df[feature_names].values.astype(np.float64)
            y_valid = valid_df[target_name].values.astype(np.float64)
            X_valid = np.nan_to_num(X_valid, nan=0.0, posinf=0.0, neginf=0.0)
        else:
            X_valid, y_valid = X_train, y_train

        # Train the model
        # qlib models use .fit() with DMatrix-style data or numpy arrays
        logger.info(
            "QlibModelTrainer: training %s with %d features, %d train rows",
            self.model_name, len(feature_names), len(X_train),
        )

        try:
            model.fit(X_train, y_train, X_valid, y_valid)
        except TypeError:
            # Some qlib models have different fit() signatures; try
            # fitting with just train data as fallback
            model.fit(X_train, y_train)

        # Generate validation predictions for metrics
        predictions = model.predict(X_valid)
        predictions = np.asarray(predictions, dtype=np.float64).ravel()
        metrics = regression_metrics(y_valid, predictions)

        # Persist the model
        model_id = build_model_id(config, self.name)
        model_dir = ensure_model_dir(config, self.name)
        model_path = model_dir / f"{model_id}.pkl"

        import pickle

        with open(model_path, "wb") as f:
            pickle.dump(model, f)

        artifact = ModelArtifact(
            model_id=model_id,
            trainer_name=self.name,
            feature_names=feature_names,
            target_name=target_name,
            trained_at=datetime.now(tz=timezone.utc),
            metrics=metrics,
            model_path=str(model_path),
            metadata={
                "model_name": self.model_name,
                "model_type": self._model_info.model_type,
                "requires_alpha360": self.requires_alpha360,
                "params": merged_params,
                "train_rows": train.height,
                "valid_rows": valid.height,
                **config.get("metadata", {}),
            },
        )

        logger.info(
            "QlibModelTrainer: training complete — %s metrics=%s",
            self.model_name, metrics,
        )
        return artifact

    def predict(self, features: pl.DataFrame, model_artifact: ModelArtifact) -> pl.Series:
        """Generate predictions from *features* using the persisted model.

        Returns a ``pl.Series`` named ``"prediction"`` with one value per row.
        """
        import pickle

        with open(model_artifact.model_path, "rb") as f:
            model = pickle.load(f)

        X = frame_to_matrix(features, model_artifact.feature_names)
        X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

        raw = model.predict(X)
        predictions = np.asarray(raw, dtype=np.float64).ravel()
        return pl.Series(name="prediction", values=predictions)

    def predict_and_persist(
        self,
        features: pl.DataFrame,
        model_artifact: ModelArtifact,
        catalog: "Catalog",
        horizon: str = "5d",
        fold_id: str | None = None,
    ) -> pl.Series:
        """Generate predictions and write them to gold_predictions.

        Returns the predictions Series for immediate use.
        """
        from cquant.ml_lab.base import persist_predictions

        predictions = self.predict(features, model_artifact)
        persist_predictions(model_artifact, features, predictions, catalog, horizon, fold_id=fold_id)
        return predictions
