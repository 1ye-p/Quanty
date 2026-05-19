"""cquant.riskguard.policies.position_limits — Position size limit policy."""

from __future__ import annotations

from decimal import Decimal

from cquant.core.enums import RiskDecisionType
from cquant.core.types import OrderIntent, RiskDecision, RiskSnapshot
from cquant.riskguard.models import RiskContext
from cquant.riskguard.policies.base import RiskPolicy


class PositionLimitPolicy(RiskPolicy):
    """Enforces per-asset position size limits.

    Parameters:
        max_position_pct: Maximum weight of any single asset in the portfolio (default 10%).
        max_notional: Maximum notional value per position in local currency (None = unlimited).
    """

    def __init__(
        self,
        max_position_pct: float = 0.10,
        max_notional: Decimal | None = None,
    ) -> None:
        self._max_pct = max_position_pct
        self._max_notional = max_notional

    @property
    def name(self) -> str:
        return "position_limit"

    def evaluate(
        self,
        candidate: OrderIntent,
        snapshot: RiskSnapshot,
        ctx: RiskContext,
        price: float = 0.0,
    ) -> RiskDecision:
        original_qty = candidate.requested_qty
        approved_qty = original_qty
        reasons: list[str] = []

        # Notional check
        if self._max_notional is not None and price > 0:
            notional = float(candidate.requested_qty) * price
            if notional > float(self._max_notional):
                # Clip quantity to max notional
                max_qty = int(float(self._max_notional) / price)
                if max_qty <= 0:
                    return RiskDecision(
                        decision=RiskDecisionType.REJECTED,
                        original_qty=original_qty,
                        approved_qty=Decimal("0"),
                        reasons=[f"Notional {notional:,.0f} exceeds limit {float(self._max_notional):,.0f}"],
                        policy_names=[self.name],
                    )
                approved_qty = Decimal(str(max_qty))
                reasons.append(f"Clipped from {original_qty} to {approved_qty} (notional limit)")

        # Portfolio weight check
        if ctx.portfolio_nav > 0 and self._max_pct < 1.0 and price > 0:
            # Calculate target notional after this order
            target_notional = float(candidate.requested_qty) * price
            current_weight = 0.0

            if not ctx.current_positions.is_empty() and "asset_id" in ctx.current_positions.columns:
                pos_row = ctx.current_positions.filter(
                    ctx.current_positions["asset_id"] == candidate.asset_id
                )
                if not pos_row.is_empty():
                    if "market_value" in pos_row.columns:
                        current_mv = float(pos_row["market_value"].item())
                        current_weight = current_mv / float(ctx.portfolio_nav)

            # Projected weight after fill
            projected_weight = current_weight + (target_notional / float(ctx.portfolio_nav))

            if projected_weight > self._max_pct:
                # Clip to max weight
                allowed_notional = (self._max_pct - current_weight) * float(ctx.portfolio_nav)
                max_qty = int(allowed_notional / price) if price > 0 else 0
                if max_qty <= 0:
                    return RiskDecision(
                        decision=RiskDecisionType.REJECTED,
                        original_qty=original_qty,
                        approved_qty=Decimal("0"),
                        reasons=[f"Position weight {current_weight:.1%} already at limit {self._max_pct:.1%}"],
                        policy_names=[self.name],
                    )
                # Round to lot size
                max_qty = (max_qty // 100) * 100
                if max_qty <= 0:
                    return RiskDecision(
                        decision=RiskDecisionType.REJECTED,
                        original_qty=original_qty,
                        approved_qty=Decimal("0"),
                        reasons=[f"Projected weight {projected_weight:.1%} exceeds limit {self._max_pct:.1%}"],
                        policy_names=[self.name],
                    )
                approved_qty = Decimal(str(max_qty))
                reasons.append(f"Clipped from {original_qty} to {approved_qty} (weight limit)")

        decision_type = RiskDecisionType.APPROVED if approved_qty == original_qty else RiskDecisionType.CLIPPED
        if approved_qty == Decimal("0"):
            decision_type = RiskDecisionType.REJECTED

        return RiskDecision(
            decision=decision_type,
            original_qty=original_qty,
            approved_qty=approved_qty,
            reasons=reasons,
            policy_names=[self.name],
        )
