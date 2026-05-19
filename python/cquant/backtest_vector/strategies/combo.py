"""Strategy combination framework: run multiple strategies and merge signals."""
from __future__ import annotations

import polars as pl

from cquant.backtest_vector.strategy import Strategy, StrategyContext
from cquant.core.types import SignalFrame


class CompositeStrategy(Strategy):
    """Combine signals from multiple sub-strategies.

    Parameters:
        strategy_id: Identifier for this composite.
        strategies: List of sub-strategies to run.
        method: Combination method:
            - "equal_weight": average signals across strategies
            - "custom": use strategy_weights dict for weighted average
        strategy_weights: Required when method="custom". Maps strategy_id -> weight.
    """

    def __init__(
        self,
        strategy_id: str,
        strategies: list[Strategy],
        method: str = "equal_weight",
        strategy_weights: dict[str, float] | None = None,
    ) -> None:
        self._strategy_id = strategy_id
        self._strategies = strategies
        self._method = method
        self._strategy_weights = strategy_weights or {}

    @property
    def strategy_id(self) -> str:
        return self._strategy_id

    def generate_signals(self, ctx: StrategyContext) -> SignalFrame:
        if not self._strategies:
            return _empty_frame()

        all_signals: list[pl.DataFrame] = []
        for strat in self._strategies:
            sig = strat.generate_signals(ctx)
            if not sig.is_empty():
                sig = sig.with_columns(pl.lit(strat.strategy_id).alias("_source"))
                all_signals.append(sig)

        if not all_signals:
            return _empty_frame()

        combined = pl.concat(all_signals)

        # Compute weights per source strategy
        if self._method == "custom":
            weights = self._strategy_weights
        else:
            sources = combined["_source"].unique().to_list()
            weights = {s: 1.0 / len(sources) for s in sources}

        # Add weight column
        combined = combined.with_columns(
            pl.col("_source").map_elements(
                lambda s: weights.get(s, 0.0), return_dtype=pl.Float64
            ).alias("_weight")
        )

        # Weighted strength
        combined = combined.with_columns(
            (pl.col("strength") * pl.col("_weight")).alias("_weighted_strength")
        )

        # Group by asset_id, sum weighted strengths
        result = (
            combined
            .group_by("asset_id")
            .agg([
                pl.col("_weighted_strength").sum().alias("strength"),
                pl.col("signal_date").first().alias("signal_date"),
                pl.col("direction").first().alias("direction"),
                pl.col("confidence").mean().alias("confidence"),
            ])
            .with_columns(pl.lit("long").alias("direction"))
            .select(["asset_id", "signal_date", "direction", "strength", "confidence"])
        )

        return result


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
