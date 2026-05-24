"""cquant.ml_lab.trainers.lgbm — LightGBM regression trainer."""

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


def _lightgbm() -> Any:
    try:
        import lightgbm as lgb
        return lgb
    except ImportError as exc:
        raise ImportError(
            "lightgbm is required to use LGBMTrainer. "
            "Install with: conda install -n cQuanty lightgbm"
        ) from exc


class LGBMTrainer(Trainer):
    """Train a LightGBM regressor on time-sliced Polars feature frames."""

    name = "lightgbm_regressor"

    def fit(self, train: pl.DataFrame, valid: pl.DataFrame, config: dict) -> ModelArtifact:
        lgb = _lightgbm()
        target_name = str(config.get("target_name", "ret_5d"))
        feature_names = infer_feature_names(train, target_name, config.get("feature_names"))

        x_train = frame_to_matrix(train, feature_names)
        y_train = target_to_vector(train, target_name)

        params: dict[str, Any] = {
            "objective": "regression",
            "n_estimators": 300,
            "learning_rate": 0.05,
            "num_leaves": 31,
            "subsample": 0.9,
            "colsample_bytree": 0.9,
            "random_state": 42,
            "verbosity": -1,
        }
        params.update(config.get("params", {}))

        model = lgb.LGBMRegressor(**params)

        if valid.is_empty():
            model.fit(x_train, y_train)
            y_eval, predictions = y_train, model.predict(x_train)
        else:
            x_valid = frame_to_matrix(valid, feature_names)
            y_valid = target_to_vector(valid, target_name)
            model.fit(x_train, y_train, eval_set=[(x_valid, y_valid)])
            y_eval, predictions = y_valid, model.predict(x_valid)

        metrics = regression_metrics(y_eval, predictions)
        model_id = build_model_id(config, "lgbm")
        model_dir = ensure_model_dir(config, "lgbm")
        model_path = model_dir / f"{model_id}.txt"
        model.booster_.save_model(str(model_path))

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
                "best_iteration": int(model.best_iteration_ or 0),
                "train_rows": train.height,
                "valid_rows": valid.height,
                **config.get("metadata", {}),
            },
        )

    def predict(self, features: pl.DataFrame, model_artifact: ModelArtifact) -> pl.Series:
        lgb = _lightgbm()
        booster = lgb.Booster(model_file=model_artifact.model_path)
        predictions = booster.predict(frame_to_matrix(features, model_artifact.feature_names))
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

    def feature_importance(
        self,
        model_artifact: ModelArtifact,
        importance_type: str = "gain",
    ) -> dict[str, float]:
        """Return feature importance scores from the trained LightGBM model.

        Parameters
        ----------
        model_artifact:
            Trained model artifact with ``model_path`` and ``feature_names``.
        importance_type:
            ``"gain"`` (default) — total gain of all splits using the feature.
            ``"split"`` — number of times the feature is used in splits.

        Returns
        -------
        ``dict[feature_name, importance_score]``
        """
        lgb = _lightgbm()
        booster = lgb.Booster(model_file=model_artifact.model_path)
        importances = booster.feature_importance(importance_type=importance_type)
        return {
            feature: float(score)
            for feature, score in zip(model_artifact.feature_names, importances)
        }
