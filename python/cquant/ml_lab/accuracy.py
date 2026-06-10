"""cquant.ml_lab.accuracy — Prediction accuracy tracking.

Computes IC, Rank IC, and Hit Rate by comparing predictions to realized
returns.  Results are persisted to the ``gold_prediction_accuracy`` table.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import numpy as np
import polars as pl

if TYPE_CHECKING:
    from cquant.datahub.catalog import Catalog

logger = logging.getLogger(__name__)

_DDL = """
CREATE TABLE IF NOT EXISTS gold_prediction_accuracy (
    model_version   VARCHAR NOT NULL,
    eval_date       VARCHAR NOT NULL,
    metric_name     VARCHAR NOT NULL,
    metric_value    DOUBLE NOT NULL,
    sample_count    INTEGER NOT NULL DEFAULT 0,
    computed_at     TIMESTAMP NOT NULL,
    PRIMARY KEY (model_version, eval_date, metric_name)
);
"""


def _pearson_correlation(x: np.ndarray, y: np.ndarray) -> float:
    """Compute Pearson correlation coefficient (IC)."""
    if x.size < 2:
        return 0.0
    xm = x - x.mean()
    ym = y - y.mean()
    denom = math.sqrt(float((xm * xm).sum() * (ym * ym).sum()))
    if denom == 0:
        return 0.0
    return float((xm * ym).sum() / denom)


def _rank_ic(pred: np.ndarray, actual: np.ndarray) -> float:
    """Compute Spearman rank correlation (Rank IC)."""
    from scipy.stats import spearmanr

    if pred.size < 2:
        return 0.0
    corr, _ = spearmanr(pred, actual)
    return float(corr) if not np.isnan(corr) else 0.0


def _hit_rate(pred: np.ndarray, actual: np.ndarray) -> float:
    """Fraction of predictions where the sign matches the actual return."""
    if pred.size == 0:
        return 0.0
    return float((np.sign(pred) == np.sign(actual)).mean())


class AccuracyTracker:
    """Tracks prediction accuracy by comparing predictions to realized returns.

    Parameters
    ----------
    catalog
        An initialised ``Catalog`` (DuckDB) instance.
    """

    def __init__(self, catalog: Catalog) -> None:
        self._catalog = catalog
        # Ensure table exists
        self._catalog.execute(_DDL)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compute_accuracy(
        self,
        model_version: str,
        eval_date: str,
        predictions: pl.DataFrame,
        realized_returns: pl.DataFrame,
    ) -> dict[str, float]:
        """Compute accuracy metrics for a given model and evaluation date.

        Parameters
        ----------
        model_version
            The model version identifier.
        eval_date
            The evaluation date (YYYY-MM-DD).
        predictions
            DataFrame with columns ``[asset_id, prediction]``.
        realized_returns
            DataFrame with columns ``[asset_id, return]``.

        Returns
        -------
        dict with keys ``ic``, ``rank_ic``, ``hit_rate``, ``sample_count``.
        """
        # Join predictions with realized returns on asset_id
        joined = predictions.join(realized_returns, on="asset_id", how="inner")
        if joined.is_empty():
            logger.warning(
                "No matching assets between predictions and realized returns for %s on %s",
                model_version, eval_date,
            )
            return {"ic": 0.0, "rank_ic": 0.0, "hit_rate": 0.0, "sample_count": 0}

        pred_arr = joined["prediction"].to_numpy().astype(np.float64)
        actual_arr = joined["return"].to_numpy().astype(np.float64)

        # Drop NaN pairs
        mask = ~(np.isnan(pred_arr) | np.isnan(actual_arr))
        pred_arr = pred_arr[mask]
        actual_arr = actual_arr[mask]
        n = int(pred_arr.size)

        ic = _pearson_correlation(pred_arr, actual_arr)
        rank_ic = _rank_ic(pred_arr, actual_arr)
        hr = _hit_rate(pred_arr, actual_arr)

        # Persist
        now = datetime.now(tz=timezone.utc).isoformat()
        metrics = {"ic": ic, "rank_ic": rank_ic, "hit_rate": hr}
        rows = [
            (model_version, eval_date, name, value, n, now)
            for name, value in metrics.items()
        ]
        self._catalog.upsert(
            "gold_prediction_accuracy",
            ["model_version", "eval_date", "metric_name", "metric_value", "sample_count", "computed_at"],
            rows,
            ["model_version", "eval_date", "metric_name"],
        )

        logger.info(
            "Accuracy for %s on %s: IC=%.4f, RankIC=%.4f, HitRate=%.4f (n=%d)",
            model_version, eval_date, ic, rank_ic, hr, n,
        )
        return {"ic": ic, "rank_ic": rank_ic, "hit_rate": hr, "sample_count": n}

    def get_accuracy_history(
        self,
        model_version: str,
        metric_name: str | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve accuracy history for a model.

        Parameters
        ----------
        model_version
            The model version identifier.
        metric_name
            Filter by metric (e.g. ``'ic'``).  ``None`` returns all metrics.
        """
        params: list[Any] = [model_version]
        clause = "WHERE model_version = ?"
        if metric_name:
            clause += " AND metric_name = ?"
            params.append(metric_name)

        df = self._catalog.query(
            f"SELECT * FROM gold_prediction_accuracy {clause} ORDER BY eval_date DESC",
            params,
        )
        return df.to_dicts() if not df.is_empty() else []

    def get_latest_accuracy(self, model_version: str) -> dict[str, float] | None:
        """Return the latest accuracy metrics for a model (most recent eval_date)."""
        df = self._catalog.query(
            """SELECT metric_name, metric_value, eval_date
               FROM gold_prediction_accuracy
               WHERE model_version = ?
               ORDER BY eval_date DESC
               LIMIT 3""",
            [model_version],
        )
        if df.is_empty():
            return None
        result: dict[str, float] = {}
        for row in df.to_dicts():
            result[row["metric_name"]] = row["metric_value"]
        result["eval_date"] = df.to_dicts()[0]["eval_date"]
        return result
