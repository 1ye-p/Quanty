"""Volatility parity (risk parity) position sizer."""

from __future__ import annotations

import logging

import polars as pl

from cquant.core.types import SignalFrame, TargetWeights
from cquant.riskguard.models import SizingContext
from cquant.riskguard.sizers.base import PositionSizer

logger = logging.getLogger(__name__)


class VolParitySizer(PositionSizer):
    """Assigns weights inversely proportional to each asset's volatility.

    Weight_i = (1 / vol_i) / sum(1 / vol_j)

    Requires ctx.volatility to be set (DataFrame with [asset_id, volatility] columns).
    Falls back to equal-weight if volatility data is unavailable.
    """

    def __init__(self, target_vol: float = 0.15, allow_short: bool = False) -> None:
        self._target_vol = target_vol
        self._allow_short = allow_short

    @property
    def name(self) -> str:
        return "vol_parity"

    def target_weights(self, signals: SignalFrame, ctx: SizingContext) -> TargetWeights:
        active = signals.filter(pl.col("strength").abs() > 1e-9)

        if active.is_empty():
            return TargetWeights(
                strategy_id="",
                rebalance_date=ctx.as_of_date,
                weights={},
                sizer_name=self.name,
            )

        if ctx.volatility is None or ctx.volatility.is_empty():
            logger.warning(
                "VolParitySizer: no volatility data in SizingContext; falling back to equal weight."
            )
            from cquant.riskguard.sizers.equal_weight import EqualWeightSizer
            return EqualWeightSizer(allow_short=self._allow_short).target_weights(signals, ctx)

        # Join volatility onto active signals
        merged = active.join(ctx.volatility, on="asset_id", how="left")
        merged = merged.with_columns(
            pl.col("volatility").fill_null(pl.col("volatility").mean()).clip(lower_bound=1e-9)
        )

        longs = merged.filter(pl.col("direction") != "short") if not self._allow_short \
            else merged.filter(pl.col("direction") == "long")

        total_inv_vol = (1.0 / longs["volatility"]).sum()
        weights: dict[str, float] = {}
        if total_inv_vol > 0:
            for row in longs.iter_rows(named=True):
                weights[row["asset_id"]] = (1.0 / row["volatility"]) / total_inv_vol

        return TargetWeights(
            strategy_id="",
            rebalance_date=ctx.as_of_date,
            weights=weights,
            sizer_name=self.name,
        )
