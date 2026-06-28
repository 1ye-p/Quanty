"""cquant.riskguard.policies.base — RiskPolicy ABC."""

from __future__ import annotations

from abc import ABC, abstractmethod

from cquant.core.types import OrderIntent, RiskDecision, RiskSnapshot
from cquant.riskguard.models import RiskContext


class RiskPolicy(ABC):
    """Abstract pre-trade risk check policy.

    Each policy receives a candidate order intent and the current portfolio
    risk context, and returns an approval/clip/reject decision.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique stable identifier for this policy."""

    @abstractmethod
    def evaluate(
        self,
        candidate: OrderIntent,
        snapshot: RiskSnapshot,
        ctx: RiskContext,
        price: float = 0.0,
    ) -> RiskDecision:
        """Evaluate *candidate* against this policy.

        Returns:
            RiskDecision with decision=APPROVED, CLIPPED, or REJECTED.
        """
