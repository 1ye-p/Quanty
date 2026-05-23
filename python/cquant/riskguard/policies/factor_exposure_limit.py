"""因子暴露限制 Policy — 当组合因子暴露超过阈值时拒绝买单。"""
from __future__ import annotations

from decimal import Decimal

from cquant.core.enums import RiskDecisionType
from cquant.core.types import OrderIntent, RiskDecision, RiskSnapshot
from cquant.riskguard.models import RiskContext
from cquant.riskguard.policies.base import RiskPolicy


class FactorExposureLimitPolicy(RiskPolicy):
    """当组合对特定风险因子的暴露超过上限时，拒绝增加该方向的买单。

    Parameters
    ----------
    factor_limits:
        dict[factor_name, max_abs_exposure]。例如：
        ``{"beta": 0.8, "size": 0.3}``
    """

    def __init__(self, factor_limits: dict[str, float]) -> None:
        self._limits = factor_limits

    @property
    def name(self) -> str:
        return "factor_exposure_limit"

    def evaluate(
        self, candidate: OrderIntent, snapshot: RiskSnapshot, ctx: RiskContext
    ) -> RiskDecision:
        if candidate.side == "sell":
            return self._approve(candidate)

        factor_exp: dict[str, float] = ctx.factor_exposure or {}
        if not factor_exp:
            factor_exp = ctx.extra.get("factor_exposures", {}) if hasattr(ctx, "extra") else {}

        for factor, limit in self._limits.items():
            current = abs(factor_exp.get(factor, 0.0))
            if current >= limit:
                return RiskDecision(
                    decision=RiskDecisionType.REJECTED,
                    original_qty=candidate.requested_qty,
                    approved_qty=Decimal("0"),
                    reasons=[
                        f"因子 '{factor}' 当前暴露 {current:.4f} >= 上限 {limit:.4f}，"
                        f"拒绝买单以避免因子过度集中。"
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
