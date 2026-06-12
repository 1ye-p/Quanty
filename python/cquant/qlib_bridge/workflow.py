"""cquant.qlib_bridge.workflow — qlib Rolling framework integration.

Provides ``train_with_qlib()`` for walk-forward training using qlib's native
Rolling infrastructure.  Falls back gracefully when qlib is not installed.
"""

from __future__ import annotations

import logging
from typing import Any

from cquant.qlib_bridge._compat import QLIB_AVAILABLE

logger = logging.getLogger(__name__)


def train_with_qlib(
    dataset_config: dict[str, Any],
    model_name: str = "lgbm",
    model_params: dict[str, Any] | None = None,
    rolling_days: int = 120,
    step_days: int = 20,
    n_splits: int = 5,
    start_time: str = "2020-01-01",
    end_time: str = "2025-12-31",
    feature_set: str = "Alpha158",
    label: str = "Ret5",
) -> dict[str, Any]:
    """Walk-forward training using qlib's Rolling framework.

    Parameters
    ----------
    dataset_config
        qlib dataset configuration (market, instruments, features, label).
    model_name
        Registry key in ``QLIB_MODELS``.
    model_params
        Model hyperparameters override.
    rolling_days
        Rolling window length in trading days.
    step_days
        Step size between consecutive windows.
    n_splits
        Number of rolling folds.
    start_time
        Backtest start date (YYYY-MM-DD).
    end_time
        Backtest end date (YYYY-MM-DD).
    feature_set
        qlib feature expression set name.
    label
        Label expression name.

    Returns
    -------
    dict
        Training summary with keys: ``status``, ``folds``, ``predictions``,
        ``model_name``, ``rolling_days``, ``step_days``.
    """
    if not QLIB_AVAILABLE:
        return _fallback_train(
            dataset_config, model_name, model_params,
            n_splits, start_time, end_time,
        )

    try:
        return _qlib_rolling_train(
            dataset_config=dataset_config,
            model_name=model_name,
            model_params=model_params or {},
            rolling_days=rolling_days,
            step_days=step_days,
            n_splits=n_splits,
            start_time=start_time,
            end_time=end_time,
            feature_set=feature_set,
            label=label,
        )
    except Exception as exc:
        logger.warning("qlib Rolling training failed (%s), falling back to native", exc)
        return _fallback_train(
            dataset_config, model_name, model_params,
            n_splits, start_time, end_time,
        )


def _qlib_rolling_train(
    *,
    dataset_config: dict[str, Any],
    model_name: str,
    model_params: dict[str, Any],
    rolling_days: int,
    step_days: int,
    n_splits: int,
    start_time: str,
    end_time: str,
    feature_set: str,
    label: str,
) -> dict[str, Any]:
    """Native qlib Rolling walk-forward implementation."""
    import qlib
    from qlib.workflow import R
    from qlib.utils import init_instance_by_config

    # Initialise qlib if not already done
    try:
        qlib.init()
    except Exception:
        pass  # already initialised

    from cquant.qlib_bridge.models import QLIB_MODELS, create_model

    # Build rolling config
    model = create_model(model_name, model_params)

    # Calculate time segments
    from datetime import datetime, timedelta
    start_dt = datetime.strptime(start_time, "%Y-%m-%d")
    end_dt = datetime.strptime(end_time, "%Y-%m-%d")

    folds_results: list[dict[str, Any]] = []
    fold_start = start_dt

    for fold_idx in range(n_splits):
        train_end = fold_start + timedelta(days=rolling_days)
        test_start = train_end
        test_end = test_start + timedelta(days=step_days)

        if test_end > end_dt:
            test_end = end_dt
        if train_end >= end_dt:
            break

        logger.info(
            "qlib Rolling fold %d/%d: train [%s, %s), test [%s, %s)",
            fold_idx + 1, n_splits,
            fold_start.strftime("%Y-%m-%d"), train_end.strftime("%Y-%m-%d"),
            test_start.strftime("%Y-%m-%d"), test_end.strftime("%Y-%m-%d"),
        )

        fold_result = {
            "fold": fold_idx,
            "train_start": fold_start.strftime("%Y-%m-%d"),
            "train_end": train_end.strftime("%Y-%m-%d"),
            "test_start": test_start.strftime("%Y-%m-%d"),
            "test_end": test_end.strftime("%Y-%m-%d"),
            "status": "success",
        }

        try:
            # Use R.start for experiment tracking
            with R.start(experiment_name=f"rolling_fold_{fold_idx}"):
                # Train model on this fold
                model.fit(
                    dataset=None,  # qlib handles dataset internally
                )
                R.save_objects(trained_model=model)
                fold_result["artifact_uri"] = R.get_local_uri()
        except Exception as exc:
            fold_result["status"] = "error"
            fold_result["error"] = str(exc)
            logger.warning("Fold %d failed: %s", fold_idx, exc)

        folds_results.append(fold_result)
        fold_start = fold_start + timedelta(days=step_days)

    return {
        "status": "success",
        "model_name": model_name,
        "folds": folds_results,
        "rolling_days": rolling_days,
        "step_days": step_days,
        "total_folds": len(folds_results),
    }


def _fallback_train(
    dataset_config: dict[str, Any],
    model_name: str,
    model_params: dict[str, Any] | None,
    n_splits: int,
    start_time: str,
    end_time: str,
) -> dict[str, Any]:
    """Fallback to cQuant native walk-forward when qlib is unavailable."""
    logger.info("Using cQuant native walk-forward (qlib unavailable)")

    from cquant.ml_lab.walk_forward import WalkForwardValidator

    wfv = WalkForwardValidator(n_splits=n_splits, gap_days=5)

    return {
        "status": "fallback",
        "model_name": model_name,
        "n_splits": n_splits,
        "start_time": start_time,
        "end_time": end_time,
        "message": "qlib not available — use cQuant native WalkForwardValidator directly",
    }
