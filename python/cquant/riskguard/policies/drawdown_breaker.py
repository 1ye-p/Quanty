"""Drawdown circuit breaker -- rejects new buys when portfolio drawdown exceeds threshold."""
from __future__ import annotations

from decimal import Decimal

from cquant.core.enums import RiskDecisionType
from cquant.core.types import OrderIntent, RiskDecision, RiskSnapshot
from cquant.riskguard.models import RiskContext
from cquant.riskguard.policies.base import RiskPolicy


class DrawdownBreakerPolicy(RiskPolicy):
    """Rejects new buy orders when portfolio drawdown exceeds the configured threshold.

    Sell orders are always allowed -- reducing positions during drawdown is risk-reducing.
    """

    def __init__(self, max_drawdown: float = -0.10) -> None:
        """
        Args:
            max_drawdown: Maximum allowed drawdown as a negative float (e.g. -0.10 = -10%).
                          When drawdown exceeds this, new buys are rejected.
        """
        self._max_dd = max_drawdown

    @property
    def name(self) -> str:
        return "drawdown_breaker"

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

        current_dd = snapshot.drawdown
        if current_dd < self._max_dd:
            return RiskDecision(
                decision=RiskDecisionType.REJECTED,
                original_qty=candidate.requested_qty,
                approved_qty=Decimal("0"),
                reasons=[
                    f"Drawdown {current_dd:.1%} exceeds threshold {self._max_dd:.1%}. "
                    f"Buy orders suspended until drawdown recovers."
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
