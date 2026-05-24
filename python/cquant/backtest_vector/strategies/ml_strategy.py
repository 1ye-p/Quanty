"""MLModelStrategy — generate signals from ML model predictions in gold_predictions."""
from __future__ import annotations

import logging

import polars as pl

from cquant.backtest_vector.strategy import Strategy, StrategyContext
from cquant.core.types import SignalFrame

logger = logging.getLogger(__name__)


class MLModelStrategy(Strategy):
    """Generate trading signals by reading predictions from gold_predictions table.

    Queries gold_predictions for the given as_of_date and model_version,
    selects the top-N assets by predicted return (filtering out negatives),
    and returns them as long signals with equal strength.

    Requires a Catalog instance in ``ctx.extra['catalog']``. Returns empty
    signals if no catalog is provided or no predictions exist for the date.

    Parameters
    ----------
    strategy_id:
        Unique identifier for this strategy.
    model_version:
        The ``model_version`` key in gold_predictions (i.e., ModelArtifact.model_id).
    top_n:
        Number of assets to select.
    label_name:
        Which prediction label to use (e.g. ``'ret_5d'``).
    min_prediction:
        Minimum prediction value to include (default 0.0 — long-only, positive expected return).
    """

    def __init__(
        self,
        strategy_id: str,
        model_version: str,
        top_n: int = 10,
        label_name: str = "ret_5d",
        min_prediction: float = 0.0,
    ) -> None:
        self._strategy_id = strategy_id
        self._model_version = model_version
        self._top_n = top_n
        self._label_name = label_name
        self._min_prediction = min_prediction

    @property
    def strategy_id(self) -> str:
        return self._strategy_id

    def generate_signals(self, ctx: StrategyContext) -> SignalFrame:
        catalog = ctx.extra.get("catalog")
        if catalog is None:
            logger.debug(
                "MLModelStrategy '%s': no catalog in ctx.extra — returning empty signals",
                self._strategy_id,
            )
            return _empty_frame()

        # Use LIKE for composite model_id (walk-forward folds: model_id_fold0, model_id_fold1, ...)
        # Also works for single model_id (backward compatible)
        model_pattern = f"{self._model_version}%"

        try:
            preds = catalog.query(
                """
                SELECT asset_id, prediction
                FROM gold_predictions
                WHERE model_version LIKE ?
                  AND trade_date = ?
                  AND label_name = ?
                  AND prediction > ?
                ORDER BY prediction DESC
                LIMIT ?
                """,
                [
                    model_pattern,
                    ctx.as_of_date.isoformat(),
                    self._label_name,
                    self._min_prediction,
                    self._top_n,
                ],
            )
        except Exception as exc:
            logger.warning("MLModelStrategy '%s': query failed: %s", self._strategy_id, exc)
            return _empty_frame()

        if preds.is_empty():
            return _empty_frame()

        n = len(preds)
        return preds.select([
            pl.col("asset_id"),
            pl.lit(ctx.as_of_date).alias("signal_date"),
            pl.lit("long").alias("direction"),
            pl.lit(1.0 / n).alias("strength"),
            pl.lit(1.0).alias("confidence"),
        ])


def _empty_frame() -> SignalFrame:
    return pl.DataFrame(
        schema={
            "asset_id": pl.Utf8,
            "signal_date": pl.Date,
            "direction": pl.Utf8,
            "strength": pl.Float64,
            "confidence": pl.Float64,
        }
    )
