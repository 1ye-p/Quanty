"""Time-based holding period stop policy."""
from __future__ import annotations

from decimal import Decimal

import polars as pl

from cquant.core.enums import RiskDecisionType
from cquant.core.types import OrderIntent, RiskDecision, RiskSnapshot
from cquant.riskguard.models import RiskContext
from cquant.riskguard.policies.base import RiskPolicy


class MaxHoldingDaysPolicy(RiskPolicy):
    """Reject buy orders that would add to an old, losing position.

    If a position has been held longer than ``max_days`` calendar days
    AND is currently at a loss, further buys are rejected.

    Requires ``ctx.extra["entry_dates"]`` — a ``dict[str, date]`` mapping
    ``asset_id → position_entry_date``. If not present, the policy approves.

    Sell orders are always allowed.

    Parameters
    ----------
    max_days:
        Maximum calendar days to hold a losing position before blocking buys.
    """

    def __init__(self, max_days: int = 30) -> None:
        self._max_days = max_days

    @property
    def name(self) -> str:
        return "max_holding_days"

    def evaluate(
        self, candidate: OrderIntent, snapshot: RiskSnapshot, ctx: RiskContext
    ) -> RiskDecision:
        if candidate.side == "sell":
            return self._approve(candidate)

        # Look up entry date
        entry_dates: dict = getattr(ctx, "extra", {}).get("entry_dates", {})
        entry_date = entry_dates.get(candidate.asset_id)
        if entry_date is None:
            return self._approve(candidate)

        holding_days = (ctx.as_of_date - entry_date).days
        if holding_days <= self._max_days:
            return self._approve(candidate)

        # Over the limit — check if the position is losing
        if ctx.current_positions.is_empty():
            return self._approve(candidate)

        pos = ctx.current_positions.filter(pl.col("asset_id") == candidate.asset_id)
        if pos.is_empty():
            return self._approve(candidate)

        qty = float(pos["quantity"][0])
        if qty <= 0:
            return self._approve(candidate)

        market_value = float(pos["market_value"][0])
        current_price = float(candidate.limit_price) if candidate.limit_price else 0.0
        avg_entry = market_value / qty

        if avg_entry <= 0 or current_price <= 0:
            return self._approve(candidate)

        is_losing = current_price < avg_entry
        if not is_losing:
            return self._approve(candidate)

        return RiskDecision(
            decision=RiskDecisionType.REJECTED,
            original_qty=candidate.requested_qty,
            approved_qty=Decimal("0"),
            reasons=[
                f"Position {candidate.asset_id} held {holding_days} days "
                f"(max {self._max_days}) and is losing "
                f"({current_price:.2f} < entry {avg_entry:.2f}). Buys blocked."
            ],
            policy_names=[self.name],
        )

    def _approve(self, candidate: OrderIntent) -> RiskDecision:
        return RiskDecision(
            decision=RiskDecisionType.APPROVED,
            original_qty=candidate.requested_qty,
            approved_qty=candidate.requested_qty,
            reasons=[],
            policy_names=[self.name],
        )
