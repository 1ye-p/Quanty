"""Drawdown circuit breaker — graduated position reduction when drawdown exceeds thresholds."""
from __future__ import annotations

from decimal import Decimal

from cquant.core.enums import RiskDecisionType
from cquant.core.types import OrderIntent, RiskDecision, RiskSnapshot
from cquant.riskguard.models import RiskContext
from cquant.riskguard.policies.base import RiskPolicy


class DrawdownBreakerPolicy(RiskPolicy):
    """Rejects or clips buy orders based on portfolio drawdown level.

    Supports both single-threshold (backward-compatible) and graduated multi-level mode.

    Parameters
    ----------
    max_drawdown:
        Single threshold (negative float). All buys rejected when drawdown <= this.
        Ignored when ``levels`` is provided.
    levels:
        Graduated levels as a list of ``(drawdown_threshold, allowed_fraction)`` tuples.
        - ``drawdown_threshold``: negative float (e.g., ``-0.05`` = 5% drawdown)
        - ``allowed_fraction``: fraction of requested qty to approve (0.0 = reject, 1.0 = full)
        Thresholds are checked from most severe (lowest value) to least severe.
        Example: ``[(-0.10, 0.0), (-0.05, 0.5)]``
            - At -10%+ drawdown: reject all buys
            - At -5% to -10% drawdown: allow 50%
            - Below -5%: allow 100%

    Sell orders are always approved.
    """

    def __init__(
        self,
        max_drawdown: float = -0.10,
        levels: list[tuple[float, float]] | None = None,
    ) -> None:
        if levels is not None:
            # Sort by threshold ascending (most severe first)
            self._levels: list[tuple[float, float]] = sorted(levels, key=lambda x: x[0])
        else:
            # Backward-compatible single threshold
            self._levels = [(max_drawdown, 0.0)]
        self._max_dd = max_drawdown

    @property
    def name(self) -> str:
        return "drawdown_breaker"

    def evaluate(
        self, candidate: OrderIntent, snapshot: RiskSnapshot, ctx: RiskContext,
        price: float = 0.0,
    ) -> RiskDecision:
        # Always allow sells
        if candidate.side == "sell":
            return RiskDecision(
                decision=RiskDecisionType.APPROVED,
                original_qty=candidate.requested_qty,
                approved_qty=candidate.requested_qty,
                reasons=[],
                policy_names=[self.name],
            )

        current_dd = snapshot.drawdown
        original_qty = candidate.requested_qty

        # Find the most severe threshold that is breached
        applicable_fraction = 1.0
        applicable_threshold = None
        for threshold, fraction in self._levels:
            if current_dd <= threshold:
                applicable_fraction = fraction
                applicable_threshold = threshold
                break  # levels are sorted most-severe-first; stop at first match

        if applicable_fraction >= 1.0:
            return RiskDecision(
                decision=RiskDecisionType.APPROVED,
                original_qty=original_qty,
                approved_qty=original_qty,
                reasons=[],
                policy_names=[self.name],
            )

        if applicable_fraction <= 0.0:
            return RiskDecision(
                decision=RiskDecisionType.REJECTED,
                original_qty=original_qty,
                approved_qty=Decimal("0"),
                reasons=[
                    f"Drawdown {current_dd:.1%} exceeds threshold "
                    f"{applicable_threshold:.1%}. All buys suspended."
                ],
                policy_names=[self.name],
            )

        # Clip to allowed fraction (round down to lot of 100)
        clipped_qty = int(int(original_qty) * applicable_fraction)
        clipped_qty = (clipped_qty // 100) * 100
        if clipped_qty <= 0:
            return RiskDecision(
                decision=RiskDecisionType.REJECTED,
                original_qty=original_qty,
                approved_qty=Decimal("0"),
                reasons=[
                    f"Drawdown {current_dd:.1%}: clipped qty rounds to 0 "
                    f"(fraction {applicable_fraction:.0%})"
                ],
                policy_names=[self.name],
            )

        return RiskDecision(
            decision=RiskDecisionType.CLIPPED,
            original_qty=original_qty,
            approved_qty=Decimal(str(clipped_qty)),
            reasons=[
                f"Drawdown {current_dd:.1%} at level {applicable_threshold:.1%}: "
                f"qty reduced to {applicable_fraction:.0%}"
            ],
            policy_names=[self.name],
        )
