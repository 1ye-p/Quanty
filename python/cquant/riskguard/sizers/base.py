"""cquant.riskguard.sizers.base — PositionSizer ABC."""

from __future__ import annotations

from abc import ABC, abstractmethod

from cquant.core.types import SignalFrame, TargetWeights
from cquant.riskguard.models import SizingContext


class PositionSizer(ABC):
    """Converts a signal DataFrame into target portfolio weights.

    Implementations should be stateless pure functions: given signals and
    context, return target weights.  All sizing is in weight space (0..1 for
    long-only, -1..1 for long-short).
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique stable identifier for this sizer."""

    @abstractmethod
    def target_weights(
        self,
        signals: SignalFrame,
        ctx: SizingContext,
    ) -> TargetWeights:
        """Compute target weights from *signals*.

        *signals* must have columns: [asset_id, signal_date, direction, strength].
        Returns a TargetWeights with weights summing to ≤1.0 for long-only.
        """
