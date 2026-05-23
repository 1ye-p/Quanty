"""ATR-based dynamic stop loss policy."""
from __future__ import annotations

import logging
from decimal import Decimal

import polars as pl

from cquant.core.enums import RiskDecisionType
from cquant.core.types import OrderIntent, RiskDecision, RiskSnapshot
from cquant.riskguard.models import RiskContext
from cquant.riskguard.policies.base import RiskPolicy

logger = logging.getLogger(__name__)


def compute_atr(prices: pl.DataFrame, n: int = 14) -> dict[str, float]:
    """Compute N-day Average True Range per asset.

    Parameters
    ----------
    prices:
        DataFrame with columns ``[asset_id, trade_date, open, high, low, close]``.
    n:
        ATR window in trading days.

    Returns
    -------
    ``dict[asset_id, atr_value]`` — most recent N-day ATR per asset.
    """
    if prices.is_empty() or "high" not in prices.columns:
        return {}

    df = (
        prices.sort(["asset_id", "trade_date"])
        .with_columns([
            pl.col("close").shift(1).over("asset_id").alias("_prev_close"),
        ])
        .with_columns([
            (pl.col("high") - pl.col("low")).alias("_hl"),
            (pl.col("high") - pl.col("_prev_close")).abs().alias("_hc"),
            (pl.col("low") - pl.col("_prev_close")).abs().alias("_lc"),
        ])
        .with_columns(
            pl.max_horizontal(["_hl", "_hc", "_lc"]).alias("_tr")
        )
        .with_columns(
            pl.col("_tr").rolling_mean(window_size=n).over("asset_id").alias("_atr")
        )
    )

    result: dict[str, float] = {}
    for keys, group in df.group_by("asset_id"):
        # polars group_by yields keys as a tuple even for a single group-by column
        asset_id = keys[0] if isinstance(keys, tuple) else keys
        last_atr = group.sort("trade_date").tail(1)["_atr"][0]
        if last_atr is not None and last_atr > 0:
            result[str(asset_id)] = float(last_atr)

    return result


class ATRStopLossPolicy(RiskPolicy):
    """Reject buy orders when current price falls more than n_atr * ATR below entry price.

    Requires ``ctx.extra["atr"]`` to be a ``dict[str, float]`` mapping asset_id to its
    current ATR value. If the asset is not in the dict, the policy approves (no data).

    Parameters
    ----------
    n_atr:
        Number of ATR multiples below entry before triggering stop (default 2.0).
    """

    def __init__(self, n_atr: float = 2.0) -> None:
        self._n_atr = n_atr

    @property
    def name(self) -> str:
        return "atr_stop_loss"

    def evaluate(
        self, candidate: OrderIntent, snapshot: RiskSnapshot, ctx: RiskContext
    ) -> RiskDecision:
        if candidate.side == "sell":
            return self._approve(candidate)

        # Look up ATR for this asset
        atr_map: dict[str, float] = getattr(ctx, "extra", {}).get("atr", {})
        atr = atr_map.get(candidate.asset_id)
        if atr is None or atr <= 0:
            return self._approve(candidate)

        # Get current price from order
        if not candidate.limit_price:
            return self._approve(candidate)
        current_price = float(candidate.limit_price)

        # Get average entry price from current positions
        if ctx.current_positions.is_empty():
            return self._approve(candidate)
        pos = ctx.current_positions.filter(pl.col("asset_id") == candidate.asset_id)
        if pos.is_empty():
            return self._approve(candidate)
        qty = float(pos["quantity"][0])
        if qty <= 0:
            return self._approve(candidate)
        avg_entry = float(pos["market_value"][0]) / qty

        # ATR stop: reject if price < avg_entry - n_atr * atr
        stop_price = avg_entry - self._n_atr * atr
        if current_price < stop_price:
            return RiskDecision(
                decision=RiskDecisionType.REJECTED,
                original_qty=candidate.requested_qty,
                approved_qty=Decimal("0"),
                reasons=[
                    f"ATR stop triggered: {candidate.asset_id} at {current_price:.2f} "
                    f"< stop {stop_price:.2f} (entry={avg_entry:.2f}, ATR={atr:.2f}, "
                    f"n={self._n_atr})"
                ],
                policy_names=[self.name],
            )

        return self._approve(candidate)

    def _approve(self, candidate: OrderIntent) -> RiskDecision:
        return RiskDecision(
            decision=RiskDecisionType.APPROVED,
            original_qty=candidate.requested_qty,
            approved_qty=candidate.requested_qty,
            reasons=[],
            policy_names=[self.name],
        )
