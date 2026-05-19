"""Stop-loss policies: fixed percentage and trailing stop."""
from __future__ import annotations

from decimal import Decimal

import polars as pl

from cquant.core.enums import RiskDecisionType
from cquant.core.types import OrderIntent, RiskDecision, RiskSnapshot
from cquant.riskguard.models import RiskContext
from cquant.riskguard.policies.base import RiskPolicy


class FixedStopLossPolicy(RiskPolicy):
    """Rejects further buys when a position's loss exceeds the stop threshold.

    Does not reject sells -- the purpose is to prevent adding to losing positions.
    """

    def __init__(self, stop_pct: float = -0.05) -> None:
        """
        Args:
            stop_pct: Maximum allowed loss as a negative float (e.g. -0.05 = -5%).
                      When a position's P&L% falls below this, new buys are rejected.
        """
        self._stop_pct = stop_pct

    @property
    def name(self) -> str:
        return "fixed_stop_loss"

    def evaluate(
        self, candidate: OrderIntent, snapshot: RiskSnapshot, ctx: RiskContext
    ) -> RiskDecision:
        # Always allow sells -- they reduce risk
        if candidate.side == "sell":
            return RiskDecision(
                decision=RiskDecisionType.APPROVED,
                original_qty=candidate.requested_qty,
                approved_qty=candidate.requested_qty,
                reasons=[],
                policy_names=[self.name],
            )

        # No positions at all -- allow
        if ctx.current_positions.is_empty():
            return self._approve(candidate)

        # No position in this asset -- allow
        pos = ctx.current_positions.filter(pl.col("asset_id") == candidate.asset_id)
        if pos.is_empty():
            return self._approve(candidate)

        qty = pos["quantity"][0]
        if qty <= 0:
            return self._approve(candidate)

        market_value = pos["market_value"][0]
        avg_cost = market_value / qty if qty > 0 else 0.0
        current_price = float(candidate.limit_price) if candidate.limit_price else 0.0

        if avg_cost > 0 and current_price > 0:
            pnl_pct = (current_price - avg_cost) / avg_cost
            if pnl_pct < self._stop_pct:
                return RiskDecision(
                    decision=RiskDecisionType.REJECTED,
                    original_qty=candidate.requested_qty,
                    approved_qty=Decimal("0"),
                    reasons=[
                        f"Stop-loss triggered: {candidate.asset_id} P&L {pnl_pct:.1%} "
                        f"exceeds threshold {self._stop_pct:.1%}."
                    ],
                    policy_names=[self.name],
                )

        return self._approve(candidate)

    @staticmethod
    def _approve(candidate: OrderIntent) -> RiskDecision:
        return RiskDecision(
            decision=RiskDecisionType.APPROVED,
            original_qty=candidate.requested_qty,
            approved_qty=candidate.requested_qty,
            reasons=[],
            policy_names=["fixed_stop_loss"],
        )


class TrailingStopLossPolicy(RiskPolicy):
    """Trailing stop-loss: triggers when price drops a fixed % from its peak since tracking began.

    Maintains peak prices per asset in memory (resets each session).
    """

    def __init__(self, trail_pct: float = -0.08) -> None:
        """
        Args:
            trail_pct: Maximum allowed drop from peak as a negative float
                       (e.g. -0.08 = -8%).
        """
        self._trail_pct = trail_pct
        self._peak_prices: dict[str, float] = {}

    @property
    def name(self) -> str:
        return "trailing_stop_loss"

    def evaluate(
        self, candidate: OrderIntent, snapshot: RiskSnapshot, ctx: RiskContext
    ) -> RiskDecision:
        # Always allow sells -- they reduce risk
        if candidate.side == "sell":
            return RiskDecision(
                decision=RiskDecisionType.APPROVED,
                original_qty=candidate.requested_qty,
                approved_qty=candidate.requested_qty,
                reasons=[],
                policy_names=[self.name],
            )

        asset_id = candidate.asset_id
        current_price = float(candidate.limit_price) if candidate.limit_price else 0.0

        # Update peak price
        if asset_id not in self._peak_prices:
            self._peak_prices[asset_id] = current_price
        else:
            self._peak_prices[asset_id] = max(self._peak_prices[asset_id], current_price)

        peak = self._peak_prices[asset_id]
        if peak > 0 and current_price > 0:
            drawdown_from_peak = (current_price - peak) / peak
            if drawdown_from_peak < self._trail_pct:
                return RiskDecision(
                    decision=RiskDecisionType.REJECTED,
                    original_qty=candidate.requested_qty,
                    approved_qty=Decimal("0"),
                    reasons=[
                        f"Trailing stop triggered: {asset_id} at {current_price:.2f} "
                        f"is {drawdown_from_peak:.1%} from peak {peak:.2f} "
                        f"(threshold {self._trail_pct:.1%})."
                    ],
                    policy_names=[self.name],
                )

        return RiskDecision(
            decision=RiskDecisionType.APPROVED,
            original_qty=candidate.requested_qty,
            approved_qty=candidate.requested_qty,
            reasons=[],
            policy_names=[self.name],
        )
