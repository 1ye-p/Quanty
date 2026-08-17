"""ForcedExitPolicy — base class for policies that force-close positions."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ForcedExit:
    """Represents a position that needs to be force-closed.

    Attributes:
        asset_id: Identifier of the asset to close.
        reason: Human-readable explanation for the forced exit.
        urgency: Priority level — ``normal``, ``high``, or ``critical``.
        exit_fraction: Fraction of the position to close — ``1.0`` = full
            exit (default, backward compatible), ``0 < f < 1`` = partial exit.
    """

    asset_id: str
    reason: str
    urgency: str = "normal"  # normal | high | critical
    exit_fraction: float = 1.0  # 1.0=全平（默认），0<f<1=部分平仓

    def __post_init__(self):
        if not (0.0 < self.exit_fraction <= 1.0):
            raise ValueError(
                f"exit_fraction must be in (0.0, 1.0], got {self.exit_fraction}"
            )


class ForcedExitPolicy(ABC):
    """Base class for policies that force-close positions.

    Unlike :class:`RiskPolicy` which acts as a pre-trade gate (approve / clip /
    reject incoming orders), a ``ForcedExitPolicy`` inspects *existing*
    positions and decides which ones should be liquidated.

    Subclasses must implement :meth:`check_exits`.
    """

    @abstractmethod
    def check_exits(
        self,
        positions: dict,
        current_prices: dict[str, float],
        entry_prices: dict[str, float],
        state: dict | None = None,
    ) -> list[ForcedExit]:
        """Check all positions and return those that need forced exit.

        Parameters
        ----------
        positions:
            ``{asset_id: position_info}`` — opaque position objects; each
            policy reads whatever attributes it needs (e.g. ``peak_price``,
            ``atr``).
        current_prices:
            ``{asset_id: current_market_price}``.
        entry_prices:
            ``{asset_id: average_entry_price}``.
        state:
            Optional mutable state dict managed by the engine (e.g. peak
            prices for trailing stops, ATR values).  When ``None`` the
            policy falls back to instance-level state.

        Returns
        -------
        List of :class:`ForcedExit` for positions that should be closed.
        """
