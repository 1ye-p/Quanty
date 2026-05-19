"""cquant.riskguard.policies.leverage_limit — Gross leverage limit policy."""

from __future__ import annotations

from decimal import Decimal

from cquant.core.enums import RiskDecisionType
from cquant.core.types import OrderIntent, RiskDecision, RiskSnapshot
from cquant.riskguard.models import RiskContext
from cquant.riskguard.policies.base import RiskPolicy


class LeverageLimitPolicy(RiskPolicy):
    """Enforces a maximum gross leverage constraint.

    Parameters:
        max_gross_leverage: Maximum allowed gross leverage (default 1.0 = 100%).
    """

    def __init__(self, max_gross_leverage: float = 1.0) -> None:
        self._max_leverage = max_gross_leverage

    @property
    def name(self) -> str:
        return "leverage_limit"

    def evaluate(
        self,
        candidate: OrderIntent,
        snapshot: RiskSnapshot,
        ctx: RiskContext,
        price: float = 0.0,
    ) -> RiskDecision:
        original_qty = candidate.requested_qty

        # Already at or over the limit — reject immediately
        if snapshot.gross_leverage >= self._max_leverage:
            return RiskDecision(
                decision=RiskDecisionType.REJECTED,
                original_qty=original_qty,
                approved_qty=Decimal("0"),
                reasons=[
                    f"Gross leverage {snapshot.gross_leverage:.4f} "
                    f">= limit {self._max_leverage:.4f}"
                ],
                policy_names=[self.name],
            )

        # No price available — cannot compute notional; approve as-is
        if price <= 0:
            return RiskDecision(
                decision=RiskDecisionType.APPROVED,
                original_qty=original_qty,
                approved_qty=original_qty,
                reasons=[],
                policy_names=[self.name],
            )

        nav = float(ctx.portfolio_nav)
        if nav <= 0:
            return RiskDecision(
                decision=RiskDecisionType.APPROVED,
                original_qty=original_qty,
                approved_qty=original_qty,
                reasons=[],
                policy_names=[self.name],
            )

        order_notional = float(original_qty) * price
        order_leverage = order_notional / nav
        projected_leverage = snapshot.gross_leverage + order_leverage

        if projected_leverage <= self._max_leverage:
            return RiskDecision(
                decision=RiskDecisionType.APPROVED,
                original_qty=original_qty,
                approved_qty=original_qty,
                reasons=[],
                policy_names=[self.name],
            )

        # Clip to stay within the leverage limit
        allowed_additional_leverage = self._max_leverage - snapshot.gross_leverage
        allowed_notional = allowed_additional_leverage * nav
        max_qty = int(allowed_notional / price)
        # Round down to lot size (100)
        max_qty = (max_qty // 100) * 100

        if max_qty <= 0:
            return RiskDecision(
                decision=RiskDecisionType.REJECTED,
                original_qty=original_qty,
                approved_qty=Decimal("0"),
                reasons=[
                    f"Projected leverage {projected_leverage:.4f} "
                    f"exceeds limit {self._max_leverage:.4f}"
                ],
                policy_names=[self.name],
            )

        approved_qty = Decimal(str(max_qty))
        return RiskDecision(
            decision=RiskDecisionType.CLIPPED,
            original_qty=original_qty,
            approved_qty=approved_qty,
            reasons=[
                f"Clipped from {original_qty} to {approved_qty} "
                f"(leverage limit {self._max_leverage:.4f})"
            ],
            policy_names=[self.name],
        )
