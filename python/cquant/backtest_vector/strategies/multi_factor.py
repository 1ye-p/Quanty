"""Multi-factor weighted strategy — z-scored composite ranking."""

from __future__ import annotations

import polars as pl

from cquant.backtest_vector.strategy import Strategy, StrategyContext
from cquant.core.types import SignalFrame


class MultiFactorStrategy(Strategy):
    """Combine z-scored factors with configurable weights into a composite score.

    Parameters
    ----------
    strategy_id : str
        Unique identifier for this strategy instance.
    factor_weights : dict[str, float]
        Mapping of factor name to weight.  Positive weight = higher factor
        value produces a higher composite score; negative weight inverts.
    top_n : int
        Number of top-ranked assets to emit signals for.
    """

    def __init__(
        self,
        strategy_id: str,
        factor_weights: dict[str, float],
        top_n: int = 10,
    ) -> None:
        self._strategy_id = strategy_id
        self._factor_weights = factor_weights
        self._top_n = top_n

    @property
    def strategy_id(self) -> str:
        return self._strategy_id

    # ------------------------------------------------------------------
    def generate_signals(self, ctx: StrategyContext) -> SignalFrame:
        empty = _empty_frame()

        if ctx.features is None or ctx.features.is_empty():
            return empty

        day_features = ctx.features.filter(pl.col("trade_date") == ctx.as_of_date)
        if day_features.is_empty():
            return empty

        # Keep only factors present in the features
        available = {k: w for k, w in self._factor_weights.items() if k in day_features.columns}
        if not available:
            return empty

        # Z-score each factor column and accumulate weighted scores
        score_exprs: list[pl.Expr] = []
        for col, weight in available.items():
            z = ((pl.col(col) - pl.col(col).mean()) / pl.col(col).std()).fill_nan(0.0)
            score_exprs.append((z * weight).alias(f"_w_{col}"))

        scored = (
            day_features
            .drop_nulls(list(available.keys()))
            .with_columns(score_exprs)
        )

        if scored.is_empty():
            return empty

        # Sum weighted z-scores into composite
        composite = pl.sum_horizontal([f"_w_{c}" for c in available]).alias("_composite")
        scored = scored.with_columns(composite).sort("_composite", descending=True).head(self._top_n)

        if scored.is_empty():
            return empty

        return scored.select([
            pl.col("asset_id"),
            pl.lit(ctx.as_of_date).alias("signal_date"),
            pl.lit("long").alias("direction"),
            pl.col("_composite").alias("strength"),
            pl.lit(1.0).alias("confidence"),
        ])


def _empty_frame() -> pl.DataFrame:
    return pl.DataFrame(
        schema={
            "asset_id": pl.Utf8,
            "signal_date": pl.Date,
            "direction": pl.Utf8,
            "strength": pl.Float64,
            "confidence": pl.Float64,
        }
    )
