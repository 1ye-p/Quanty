"""cquant.qlib_bridge.prediction_bridge — Prediction bridge for qlib integration.

Routes prediction requests through qlib_bridge when qlib is available,
or falls back to the native ``cquant.ml_lab.predict_service``.
"""

from __future__ import annotations

import logging
from typing import Any

from cquant.qlib_bridge._compat import QLIB_AVAILABLE, qlib_or_fallback

logger = logging.getLogger(__name__)


def predict(
    catalog: Any,
    model_version: str,
    target_date: str | None = None,
    top_n: int = 50,
) -> dict[str, Any]:
    """Run prediction using the best available backend.

    When qlib is available, this routes through the qlib bridge for
    prediction.  Otherwise, it falls back to the native
    ``cquant.ml_lab.predict_service.run_online_prediction``.

    Parameters
    ----------
    catalog
        An initialised ``Catalog`` (DuckDB) instance.
    model_version
        Model version identifier (job_id or mlflow_run_id).
    target_date
        Optional target date (YYYY-MM-DD).  ``None`` uses the latest
        available factor date.
    top_n
        Number of top predictions to return.

    Returns
    -------
    dict with keys ``date``, ``model_version``, ``trainer_name``,
    ``predictions``, ``total_assets``, ``top_n``.
    """

    def _qlib_predict() -> dict[str, Any]:
        logger.info("Using qlib bridge for prediction (model=%s)", model_version)
        try:
            from cquant.qlib_bridge.ml_bridge import train_model_qlib
            # qlib prediction is integrated through the ml_bridge;
            # fall back to native if qlib predict path is not yet wired.
            logger.warning(
                "qlib native prediction path not yet implemented, "
                "falling back to cQuant predict_service"
            )
            return _native_predict(catalog, model_version, target_date, top_n)
        except Exception as exc:
            logger.warning("qlib prediction failed (%s), falling back to native", exc)
            return _native_predict(catalog, model_version, target_date, top_n)

    def _native_predict_wrapper() -> dict[str, Any]:
        return _native_predict(catalog, model_version, target_date, top_n)

    return qlib_or_fallback(_qlib_predict, _native_predict_wrapper)


def _native_predict(
    catalog: Any,
    model_version: str,
    target_date: str | None,
    top_n: int,
) -> dict[str, Any]:
    """Run prediction using the native cQuant predict_service."""
    from cquant.ml_lab.predict_service import run_online_prediction

    return run_online_prediction(
        catalog=catalog,
        model_version=model_version,
        target_date=target_date,
        top_n=top_n,
    )
