"""Sector rotation strategy — picks top sectors by average factor, then top assets per sector."""
from __future__ import annotations

import polars as pl

from cquant.backtest_vector.strategy import Strategy, StrategyContext
from cquant.core.types import SignalFrame


class SectorRotationStrategy(Strategy):
    """Rank sectors by mean factor value; pick top assets within the top sectors.

    Parameters
    ----------
    strategy_id
        Unique identifier for this strategy instance.
    factor_col
        Factor column in ``ctx.features`` used for ranking (default ``"ret_20d"``).
    sector_map
        Optional mapping of ``asset_id → sector_name``. Falls back to
        ``ctx.extra["sector_map"]`` if not provided.
    top_sectors
        Number of top sectors to trade.
    top_n_per_sector
        Maximum assets selected per sector.
    """

    def __init__(
        self,
        strategy_id: str,
        factor_col: str = "ret_20d",
        sector_map: dict[str, str] | None = None,
        top_sectors: int = 3,
        top_n_per_sector: int = 3,
    ) -> None:
        self._strategy_id = strategy_id
        self._factor_col = factor_col
        self._sector_map = sector_map
        self._top_sectors = top_sectors
        self._top_n_per_sector = top_n_per_sector

    @property
    def strategy_id(self) -> str:
        return self._strategy_id

    def generate_signals(self, ctx: StrategyContext) -> SignalFrame:
        if ctx.features is None or ctx.features.is_empty():
            return _empty_frame()

        day = ctx.features.filter(pl.col("trade_date") == ctx.as_of_date)
        if day.is_empty() or self._factor_col not in day.columns:
            return _empty_frame()

        # Resolve sector map
        sector_map: dict[str, str] = self._sector_map or ctx.extra.get("sector_map", {})

        if not sector_map:
            # Fallback: global top-N selection
            top = (
                day.drop_nulls([self._factor_col])
                .sort(self._factor_col, descending=True)
                .head(self._top_sectors * self._top_n_per_sector)
            )
            return _to_signals(top["asset_id"].to_list(), ctx.as_of_date)

        # Add sector column
        day = day.with_columns(
            pl.col("asset_id")
            .map_elements(lambda x: sector_map.get(x, ""), return_dtype=pl.Utf8)
            .alias("_sector")
        ).filter(pl.col("_sector") != "")

        if day.is_empty():
            return _empty_frame()

        # Rank sectors by mean factor
        sector_scores = (
            day.drop_nulls([self._factor_col])
            .group_by("_sector")
            .agg(pl.col(self._factor_col).mean().alias("_sector_score"))
            .sort("_sector_score", descending=True)
            .head(self._top_sectors)
        )
        top_sector_names = set(sector_scores["_sector"].to_list())

        # Pick top assets within each top sector
        selected: list[str] = []
        for sector_name in top_sector_names:
            sector_assets = (
                day.filter(pl.col("_sector") == sector_name)
                .drop_nulls([self._factor_col])
                .sort(self._factor_col, descending=True)
                .head(self._top_n_per_sector)
            )
            selected.extend(sector_assets["asset_id"].to_list())

        return _to_signals(selected, ctx.as_of_date) if selected else _empty_frame()


def _to_signals(asset_ids: list[str], signal_date) -> SignalFrame:
    n = len(asset_ids)
    return pl.DataFrame({
        "asset_id": asset_ids,
        "signal_date": [signal_date] * n,
        "direction": ["long"] * n,
        "strength": [1.0 / n] * n,
        "confidence": [1.0] * n,
    })


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
