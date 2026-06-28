"""cquant.ml_lab.trainers.xgb — XGBoost regression trainer."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from cquant.datahub.catalog import Catalog

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


def _xgboost() -> Any:
    try:
        import xgboost as xgb
        return xgb
    except ImportError as exc:
        raise ImportError(
            "xgboost is required to use XGBTrainer. "
            "Install with: conda install -n cQuanty xgboost"
        ) from exc


class XGBTrainer(Trainer):
    """Train an XGBoost regressor on time-sliced Polars feature frames."""

    name = "xgboost_regressor"

    def fit(self, train: pl.DataFrame, valid: pl.DataFrame, config: dict) -> ModelArtifact:
        xgb = _xgboost()
        target_name = str(config.get("target_name", "ret_5d"))
        feature_names = infer_feature_names(train, target_name, config.get("feature_names"))

        x_train = frame_to_matrix(train, feature_names)
        y_train = target_to_vector(train, target_name)

        params: dict[str, Any] = {
            "objective": "reg:squarederror",
            "n_estimators": 300,
            "max_depth": 6,
            "learning_rate": 0.05,
            "subsample": 0.9,
            "colsample_bytree": 0.9,
            "random_state": 42,
        }
        params.update(config.get("params", {}))

        model = xgb.XGBRegressor(**params)

        if valid.is_empty():
            model.fit(x_train, y_train)
            y_eval, predictions = y_train, model.predict(x_train)
        else:
            x_valid = frame_to_matrix(valid, feature_names)
            y_valid = target_to_vector(valid, target_name)
            model.fit(x_train, y_train, eval_set=[(x_valid, y_valid)], verbose=False)
            y_eval, predictions = y_valid, model.predict(x_valid)

        metrics = regression_metrics(y_eval, predictions)
        model_id = build_model_id(config, "xgb")
        model_dir = ensure_model_dir(config, "xgb")
        model_path = model_dir / f"{model_id}.json"
        model.save_model(str(model_path))

        return ModelArtifact(
            model_id=model_id,
            trainer_name=self.name,
            feature_names=feature_names,
            target_name=target_name,
            trained_at=datetime.now(tz=timezone.utc),
            metrics=metrics,
            model_path=str(model_path),
            metadata={
                "params": params,
                "best_iteration": int(getattr(model, "best_iteration", 0) or 0),
                "train_rows": train.height,
                "valid_rows": valid.height,
                **config.get("metadata", {}),
            },
        )

    def predict(self, features: pl.DataFrame, model_artifact: ModelArtifact) -> pl.Series:
        xgb = _xgboost()
        model = xgb.XGBRegressor()
        model.load_model(model_artifact.model_path)
        predictions = model.predict(frame_to_matrix(features, model_artifact.feature_names))
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
