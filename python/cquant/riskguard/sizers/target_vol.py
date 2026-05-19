"""cquant.riskguard.sizers.target_vol — Target volatility position sizer.

Scales position sizes to achieve a target portfolio volatility.
Uses asset volatility and correlation to calculate weights that
produce the desired portfolio risk level.
"""

from __future__ import annotations

import logging
import math
from typing import Any

import polars as pl

from cquant.core.types import SignalFrame
from cquant.riskguard.models import SizingContext
from cquant.riskguard.sizers.base import PositionSizer, TargetWeights

logger = logging.getLogger(__name__)


class TargetVolSizer(PositionSizer):
    """Target volatility position sizer.

    Scales positions to achieve a target annualized volatility.
    Assets with lower volatility get larger positions, and vice versa.

    Usage::

        sizer = TargetVolSizer(target_volatility=0.15)  # 15% annualized vol
        weights = sizer.target_weights(signals, ctx)
    """

    def __init__(
        self,
        target_volatility: float = 0.15,
        max_position_pct: float = 0.25,
        min_position_pct: float = 0.0,
        vol_lookback: int = 60,
        vol_scaling_factor: float = 1.0,
    ) -> None:
        """Initialize target vol sizer.

        Args:
            target_volatility: Target annualized portfolio volatility (e.g., 0.15 = 15%)
            max_position_pct: Maximum position weight
            min_position_pct: Minimum position weight
            vol_lookback: Periods to estimate volatility
            vol_scaling_factor: Additional scaling factor for vol estimation
        """
        self._target_vol = target_volatility
        self._max_position_pct = max_position_pct
        self._min_position_pct = min_position_pct
        self._vol_lookback = vol_lookback
        self._vol_scaling = vol_scaling_factor

    @property
    def name(self) -> str:
        return "target_vol"

    def target_weights(
        self,
        signals: SignalFrame,
        ctx: SizingContext,
    ) -> TargetWeights:
        """Calculate weights to achieve target volatility.

        For each asset with positive signal:
        1. Estimate asset volatility (from signal strength as proxy)
        2. Calculate inverse-volatility weights
        3. Scale to achieve target portfolio volatility
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
        vol_estimates = {}

        for row in active.iter_rows(named=True):
            asset_id = row["asset_id"]
            strength = row.get("strength", 1.0)

            # Use real volatility when available, fallback to proxy
            if asset_id in vol_lookup:
                vol = max(1e-6, vol_lookup[asset_id] * self._vol_scaling)
            else:
                # Fallback: assume base volatility of 20% with signal-based adjustment
                base_vol = 0.20
                vol = max(1e-6, base_vol * (1.0 + (1.0 - strength) * 0.5) * self._vol_scaling)
            vol_estimates[asset_id] = vol

        # Inverse volatility weighting
        inv_vol_sum = sum(1.0 / v for v in vol_estimates.values() if v > 0)

        for asset_id, vol in vol_estimates.items():
            if vol > 0:
                inv_vol_weight = (1.0 / vol) / inv_vol_sum

                # Scale by signal strength
                signal_row = active.filter(pl.col("asset_id") == asset_id)
                strength = signal_row["strength"][0] if not signal_row.is_empty() else 1.0
                weight = inv_vol_weight * strength

                # Apply bounds
                weight = max(self._min_position_pct, min(weight, self._max_position_pct))
                weights[asset_id] = weight

        # Scale to target volatility
        # Simplified: assume portfolio vol is weighted average of asset vols
        if weights:
            estimated_port_vol = sum(
                weights[a] * vol_estimates.get(a, 0.20)
                for a in weights
            )

            if estimated_port_vol > 0:
                scale_factor = self._target_vol / estimated_port_vol
                # Don't scale up too aggressively
                scale_factor = min(scale_factor, 2.0)

                weights = {k: v * scale_factor for k, v in weights.items()}

                # Re-normalize if sum > 1
                total = sum(weights.values())
                if total > 1.0:
                    weights = {k: v / total for k, v in weights.items()}

        return TargetWeights(
            strategy_id="",
            rebalance_date=ctx.as_of_date,
            weights=weights,
            sizer_name=self.name,
        )
