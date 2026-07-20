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
    missing_factor_strategy : str
        Strategy for handling missing factor values. Options:
        - "fill_0": Fill missing values with 0 (default)
        - "fill_median": Fill missing values with daily median
        - "exclude": Drop assets with missing factors
    """

    def __init__(
        self,
        strategy_id: str,
        factor_weights: dict[str, float],
        top_n: int = 10,
        missing_factor_strategy: str = "fill_0",
    ) -> None:
        self._strategy_id = strategy_id
        self._factor_weights = factor_weights
        self._top_n = top_n
        self._missing_factor_strategy = missing_factor_strategy

    @property
    def strategy_id(self) -> str:
        return self._strategy_id

    # ------------------------------------------------------------------
    def _handle_missing_factors(self, day_features: pl.DataFrame, available: dict) -> pl.DataFrame:
        """Handle missing factor values based on configured strategy.

        Parameters
        ----------
        day_features : pl.DataFrame
            DataFrame containing factor values for a single day.
        available : dict
            Dictionary of available factor names and their weights.

        Returns
        -------
        pl.DataFrame
            DataFrame with missing values handled according to strategy.
        """
        if self._missing_factor_strategy == "exclude":
            return day_features.drop_nulls(list(available.keys()))

        elif self._missing_factor_strategy == "fill_median":
            for col in available:
                if col in day_features.columns:
                    median_val = day_features[col].median()
                    day_features = day_features.with_columns(
                        pl.when(pl.col(col).is_null())
                        .then(median_val)
                        .otherwise(pl.col(col))
                        .alias(col)
                    )
            return day_features

        else:  # fill_0
            for col in available:
                if col not in day_features.columns:
                    day_features = day_features.with_columns(pl.lit(0.0).alias(col))
                else:
                    day_features = day_features.with_columns(
                        pl.when(pl.col(col).is_null())
                        .then(0.0)
                        .otherwise(pl.col(col))
                        .alias(col)
                    )
            return day_features

    # ------------------------------------------------------------------
    def generate_signals(self, ctx: StrategyContext) -> SignalFrame:
        empty = _empty_frame()

        if ctx.features is None or ctx.features.is_empty():
            return empty

        day_features = ctx.features.filter(pl.col("trade_date") == ctx.as_of_date)
        if day_features.is_empty():
            return empty

        # Handle missing factors (fill_0 may add missing columns)
        day_features = self._handle_missing_factors(day_features, self._factor_weights)

        # Keep only factors present in the features
        available = {k: w for k, w in self._factor_weights.items() if k in day_features.columns}
        if not available:
            return empty

        # Z-score each factor column and accumulate weighted scores
        score_exprs: list[pl.Expr] = []
        for col, weight in available.items():
            z = ((pl.col(col) - pl.col(col).mean()) / pl.col(col).std()).fill_nan(0.0)
            score_exprs.append((z * weight).alias(f"_w_{col}"))
        scored = day_features.with_columns(score_exprs)

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
