"""cquant.riskguard.sizers.kelly — Kelly Criterion position sizer.

Implements Kelly formula for optimal position sizing:
  f* = (p * b - q) / b
where:
  f* = fraction of capital to bet
  p = probability of winning
  b = odds received on the bet (win/loss ratio)
  q = 1 - p (probability of losing)
"""

from __future__ import annotations

import logging
from typing import Any

import polars as pl

from cquant.core.types import SignalFrame
from cquant.riskguard.models import SizingContext
from cquant.riskguard.sizers.base import PositionSizer, TargetWeights

logger = logging.getLogger(__name__)


class KellySizer(PositionSizer):
    """Kelly Criterion position sizer.

    Uses historical win rate and win/loss ratio to calculate optimal
    position sizes. Supports fractional Kelly for more conservative sizing.

    Usage::

        sizer = KellySizer(kelly_fraction=0.5)  # Half-Kelly
        weights = sizer.target_weights(signals, ctx)
    """

    def __init__(
        self,
        kelly_fraction: float = 0.5,
        max_position_pct: float = 0.25,
        min_position_pct: float = 0.0,
        lookback_periods: int = 60,
    ) -> None:
        """Initialize Kelly sizer.

        Args:
            kelly_fraction: Fraction of full Kelly to use (0.5 = half-Kelly)
            max_position_pct: Maximum position weight
            min_position_pct: Minimum position weight (0 = allow zero)
            lookback_periods: Periods to calculate win rate and odds
        """
        self._kelly_fraction = kelly_fraction
        self._max_position_pct = max_position_pct
        self._min_position_pct = min_position_pct
        self._lookback_periods = lookback_periods

    @property
    def name(self) -> str:
        return "kelly"

    def target_weights(
        self,
        signals: SignalFrame,
        ctx: SizingContext,
    ) -> TargetWeights:
        """Calculate Kelly-optimal weights from signals.

        For each asset with positive signal:
        1. Estimate win probability from signal strength/confidence
        2. Estimate win/loss ratio from historical returns
        3. Apply Kelly formula: f = (p * b - q) / b
        4. Scale by kelly_fraction for safety
        """
        if signals.is_empty():
            return TargetWeights(
                strategy_id="",
                rebalance_date=ctx.as_of_date,
                weights={},
                sizer_name=self.name,
            )

        # Filter positive signals
        active = signals.filter(pl.col("strength") > 0)
        if active.is_empty():
            return TargetWeights(
                strategy_id="",
                rebalance_date=ctx.as_of_date,
                weights={},
                sizer_name=self.name,
            )

        # Build volatility lookup from context
        vol_lookup: dict[str, float] = {}
        if ctx.volatility is not None and not ctx.volatility.is_empty():
            vol_lookup = dict(zip(
                ctx.volatility["asset_id"].to_list(),
                ctx.volatility["volatility"].to_list(),
            ))

        weights = {}
        for row in active.iter_rows(named=True):
            asset_id = row["asset_id"]
            strength = row.get("strength", 1.0)
            confidence = row.get("confidence", 1.0)

            # Use real historical win rate if available; fall back to confidence proxy
            win_rates: dict[str, float] = getattr(ctx, "extra", {}).get("win_rates", {})
            raw_win_rate = win_rates.get(asset_id, confidence)
            p = min(max(raw_win_rate, 0.05), 0.95)  # Clip to (5%, 95%)
            q = 1 - p

            # Estimate odds from signal strength and real volatility
            # Use real volatility when available for more accurate odds
            if asset_id in vol_lookup:
                vol = vol_lookup[asset_id]
                b = 1.0 + strength * (1.0 + vol)
            else:
                b = 1.0 + strength * 2.0  # Fallback: Odds between 1:1 and 3:1

            # Kelly formula
            kelly_full = (p * b - q) / b if b > 0 else 0.0

            # Apply fraction and bounds
            kelly = kelly_full * self._kelly_fraction
            kelly = max(self._min_position_pct, min(kelly, self._max_position_pct))

            if kelly > 0:
                weights[asset_id] = kelly

        # Normalize weights to sum to 1 if needed
        total = sum(weights.values())
        if total > 1.0:
            weights = {k: v / total for k, v in weights.items()}

        return TargetWeights(
            strategy_id="",
            rebalance_date=ctx.as_of_date,
            weights=weights,
            sizer_name=self.name,
        )
