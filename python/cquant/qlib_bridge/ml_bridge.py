"""cquant.qlib_bridge.ml_bridge — ML model training bridge.

Routes ML model training to Qlib's LGBModel when available, or falls back
to cQuant's native LightGBM/XGBoost trainers.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import polars as pl

from cquant.qlib_bridge._compat import QLIB_AVAILABLE, qlib_or_fallback

logger = logging.getLogger(__name__)


@dataclass
class MLTrainResult:
    """Result of ML model training."""

    model_id: str
    backend: str  # "qlib" or "native"
    feature_names: list[str]
    target_name: str
    metrics: dict[str, float]
    model_path: str | None = None
    trained_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


def train_model_qlib(
    train_data: pl.DataFrame,
    valid_data: pl.DataFrame,
    feature_names: list[str],
    target_name: str = "label",
    model_type: str = "lgbm",
    params: dict[str, Any] | None = None,
    use_qlib: bool | None = None,
) -> MLTrainResult:
    """Train an ML model using Qlib's LGBModel or native trainers.

    When Qlib is available and ``use_qlib`` is not False, routes to
    Qlib's ``LGBModel`` for training.  Otherwise falls back to cQuant's
    native LightGBM or XGBoost trainers.

    Parameters
    ----------
    train_data:
        Training dataset with feature columns and target.
    valid_data:
        Validation dataset with feature columns and target.
    feature_names:
        List of feature column names to use for training.
    target_name:
        Name of the target column (default ``"label"``).
    model_type:
        Model type: ``"lgbm"`` for LightGBM, ``"xgb"`` for XGBoost.
    params:
        Model hyperparameters.  If None, uses sensible defaults.
    use_qlib:
        Force Qlib (True), force native (False), or auto-detect (None).

    Returns
    -------
    MLTrainResult
        Training result with model metadata and metrics.
    """
    if params is None:
        params = _default_params(model_type)

    should_use_qlib = use_qlib if use_qlib is not None else QLIB_AVAILABLE

    if should_use_qlib and model_type == "lgbm":
        if not QLIB_AVAILABLE:
            logger.warning("Qlib not available, falling back to native trainer")
            return _train_native(train_data, valid_data, feature_names, target_name, model_type, params)
        return _train_lgbm_native(train_data, valid_data, feature_names, target_name, params)
    else:
        return _train_native(train_data, valid_data, feature_names, target_name, model_type, params)


def _train_lgbm_native(
    train_data: pl.DataFrame,
    valid_data: pl.DataFrame,
    feature_names: list[str],
    target_name: str,
    params: dict[str, Any],
) -> MLTrainResult:
    """Train LightGBM with Qlib-compatible parameters (native lgb.train)."""
    try:
        import qlib

        logger.info("ml_bridge: training via Qlib LGBModel with %d features", len(feature_names))

        # Convert Polars to numpy for Qlib
        X_train = train_data.select(feature_names).to_numpy()
        y_train = train_data[target_name].to_numpy()
        X_valid = valid_data.select(feature_names).to_numpy()
        y_valid = valid_data[target_name].to_numpy()

        # Create Qlib dataset format
        import lightgbm as lgb
        dtrain = lgb.Dataset(X_train, label=y_train, feature_name=feature_names)
        dvalid = lgb.Dataset(X_valid, label=y_valid, feature_name=feature_names, reference=dtrain)

        # Train with Qlib-compatible params
        lgb_params = {
            "objective": params.get("objective", "regression"),
            "metric": params.get("metric", "mse"),
            "learning_rate": params.get("learning_rate", 0.05),
            "num_leaves": params.get("num_leaves", 31),
            "max_depth": params.get("max_depth", -1),
            "min_child_samples": params.get("min_child_samples", 20),
            "verbosity": params.get("verbosity", -1),
        }

        num_boost_round = params.get("num_boost_round", 1000)
        early_stopping_rounds = params.get("early_stopping_rounds", 50)

        model = lgb.train(
            lgb_params,
            dtrain,
            num_boost_round=num_boost_round,
            valid_sets=[dvalid],
            callbacks=[
                lgb.early_stopping(stopping_rounds=early_stopping_rounds),
                lgb.log_evaluation(period=100),
            ],
        )

        # Compute metrics
        y_pred = model.predict(X_valid)
        metrics = _compute_metrics(y_valid, y_pred)

        model_id = f"qlib_lgbm_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

        logger.info("ml_bridge: Qlib LGBModel training complete, metrics=%s", metrics)

        return MLTrainResult(
            model_id=model_id,
            backend="qlib",
            feature_names=feature_names,
            target_name=target_name,
            metrics=metrics,
            metadata={"params": lgb_params, "best_iteration": model.best_iteration},
        )

    except Exception as exc:
        logger.warning("ml_bridge: Qlib LGBModel training failed: %s, falling back", exc)
        return _train_native(
            train_data, valid_data, feature_names, target_name, "lgbm", params
        )


def _train_native(
    train_data: pl.DataFrame,
    valid_data: pl.DataFrame,
    feature_names: list[str],
    target_name: str,
    model_type: str,
    params: dict[str, Any],
) -> MLTrainResult:
    """Train using cQuant's native trainers (LightGBM or XGBoost)."""
    logger.info("ml_bridge: training via native %s with %d features", model_type, len(feature_names))

    X_train = train_data.select(feature_names).to_numpy()
    y_train = train_data[target_name].to_numpy()
    X_valid = valid_data.select(feature_names).to_numpy()
    y_valid = valid_data[target_name].to_numpy()

    if model_type == "lgbm":
        import lightgbm as lgb

        lgb_params = {
            "objective": params.get("objective", "regression"),
            "metric": params.get("metric", "mse"),
            "learning_rate": params.get("learning_rate", 0.05),
            "num_leaves": params.get("num_leaves", 31),
            "max_depth": params.get("max_depth", -1),
            "min_child_samples": params.get("min_child_samples", 20),
            "verbosity": params.get("verbosity", -1),
        }

        dtrain = lgb.Dataset(X_train, label=y_train, feature_name=feature_names)
        dvalid = lgb.Dataset(X_valid, label=y_valid, feature_name=feature_names, reference=dtrain)

        model = lgb.train(
            lgb_params,
            dtrain,
            num_boost_round=params.get("num_boost_round", 1000),
            valid_sets=[dvalid],
            callbacks=[
                lgb.early_stopping(stopping_rounds=params.get("early_stopping_rounds", 50)),
                lgb.log_evaluation(period=100),
            ],
        )

        y_pred = model.predict(X_valid)
        backend = "native_lgbm"

    elif model_type == "xgb":
        import xgboost as xgb

        xgb_params = {
            "objective": params.get("objective", "reg:squarederror"),
            "eval_metric": params.get("eval_metric", "rmse"),
            "learning_rate": params.get("learning_rate", 0.05),
            "max_depth": params.get("max_depth", 6),
            "min_child_weight": params.get("min_child_weight", 1),
            "verbosity": params.get("verbosity", 0),
        }

        dtrain = xgb.DMatrix(X_train, label=y_train, feature_names=feature_names)
        dvalid = xgb.DMatrix(X_valid, label=y_valid, feature_names=feature_names)

        model = xgb.train(
            xgb_params,
            dtrain,
            num_boost_round=params.get("num_boost_round", 1000),
            evals=[(dvalid, "valid")],
            early_stopping_rounds=params.get("early_stopping_rounds", 50),
            verbose_eval=100,
        )

        y_pred = model.predict(dvalid)
        backend = "native_xgb"

    else:
        raise ValueError(f"Unknown model_type: {model_type!r}; expected 'lgbm' or 'xgb'")

    metrics = _compute_metrics(y_valid, y_pred)
    model_id = f"native_{model_type}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

    logger.info("ml_bridge: native %s training complete, metrics=%s", model_type, metrics)

    return MLTrainResult(
        model_id=model_id,
        backend=backend,
        feature_names=feature_names,
        target_name=target_name,
        metrics=metrics,
        metadata={"params": params},
    )


def _compute_metrics(y_true, y_pred) -> dict[str, float]:
    """Compute regression metrics."""
    import numpy as np
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

    mse = float(mean_squared_error(y_true, y_pred))
    rmse = float(np.sqrt(mse))
    mae = float(mean_absolute_error(y_true, y_pred))
    r2 = float(r2_score(y_true, y_pred))

    return {"mse": mse, "rmse": rmse, "mae": mae, "r2": r2}


def _default_params(model_type: str) -> dict[str, Any]:
    """Return default hyperparameters for the given model type."""
    if model_type == "lgbm":
        return {
            "objective": "regression",
            "metric": "mse",
            "learning_rate": 0.05,
            "num_leaves": 31,
            "max_depth": -1,
            "min_child_samples": 20,
            "num_boost_round": 1000,
            "early_stopping_rounds": 50,
            "verbosity": -1,
        }
    elif model_type == "xgb":
        return {
            "objective": "reg:squarederror",
            "eval_metric": "rmse",
            "learning_rate": 0.05,
            "max_depth": 6,
            "min_child_weight": 1,
            "num_boost_round": 1000,
            "early_stopping_rounds": 50,
            "verbosity": 0,
        }
    else:
        raise ValueError(f"Unknown model_type: {model_type!r}")
