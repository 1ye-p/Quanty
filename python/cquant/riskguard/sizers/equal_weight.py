"""Equal-weight position sizer."""

from __future__ import annotations

from cquant.core.types import SignalFrame, TargetWeights
from cquant.riskguard.models import SizingContext
from cquant.riskguard.sizers.base import PositionSizer


class EqualWeightSizer(PositionSizer):
    """Assigns equal weight to all assets with a non-zero signal strength.

    Long assets (direction='long') receive +1/n weight.
    Short assets (direction='short') receive -1/n weight (if allow_short=True).
    """

    def __init__(self, allow_short: bool = False) -> None:
        self._allow_short = allow_short

    @property
    def name(self) -> str:
        return "equal_weight"

    def target_weights(self, signals: SignalFrame, ctx: SizingContext) -> TargetWeights:
        import polars as pl

        active = signals.filter(pl.col("strength").abs() > 1e-9)
        if active.is_empty():
            return TargetWeights(
                strategy_id="",
                rebalance_date=ctx.as_of_date,
                weights={},
                sizer_name=self.name,
            )

        if self._allow_short:
            long_assets = active.filter(pl.col("direction") == "long")["asset_id"].to_list()
            short_assets = active.filter(pl.col("direction") == "short")["asset_id"].to_list()
            n_long = len(long_assets)
            n_short = len(short_assets)
            weights: dict[str, float] = {}
            if n_long:
                w = 1.0 / n_long
                weights.update({aid: w for aid in long_assets})
            if n_short:
                w = -1.0 / n_short
                weights.update({aid: w for aid in short_assets})
        else:
            longs = active.filter(pl.col("direction") != "short")["asset_id"].to_list()
            n = len(longs)
            weights = {aid: 1.0 / n for aid in longs} if n else {}

        return TargetWeights(
            strategy_id="",
            rebalance_date=ctx.as_of_date,
            weights=weights,
            sizer_name=self.name,
        )
