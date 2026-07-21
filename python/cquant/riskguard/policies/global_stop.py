"""GlobalStopPolicy — portfolio-wide take-profit / stop-loss."""
from __future__ import annotations

from cquant.riskguard.policies.forced_exit import ForcedExit, ForcedExitPolicy


class GlobalStopPolicy(ForcedExitPolicy):
    """Portfolio-wide stop-loss and take-profit that covers all positions.

    Unlike per-asset stop-loss policies, this policy applies uniform
    percentage thresholds across every open position.  It is intended
    as a last-resort guard that triggers *after* strategy-level risk
    controls have already been evaluated.

    Parameters
    ----------
    stop_loss_pct:
        Maximum acceptable loss as a negative fraction (e.g. ``-0.05``
        means 5 % loss).  ``None`` disables the stop-loss leg.
    take_profit_pct:
        Minimum acceptable gain as a positive fraction (e.g. ``0.20``
        means 20 % profit).  ``None`` disables the take-profit leg.
    """

    def __init__(
        self,
        stop_loss_pct: float | None = None,
        take_profit_pct: float | None = None,
    ) -> None:
        self._stop_loss_pct = stop_loss_pct
        self._take_profit_pct = take_profit_pct

    def check_exits(
        self,
        positions: dict,
        current_prices: dict[str, float],
        entry_prices: dict[str, float],
        state: dict | None = None,
    ) -> list[ForcedExit]:
        """Evaluate every open position against global thresholds.

        Returns a :class:`ForcedExit` for each position whose P&L %
        breaches the configured stop-loss or take-profit boundary.
        """
        exits: list[ForcedExit] = []
        for asset_id in positions:
            ep = entry_prices.get(asset_id)
            cp = current_prices.get(asset_id)
            if ep is None or cp is None or ep <= 0:
                continue

            pnl_pct = (cp - ep) / ep

            if self._stop_loss_pct is not None and pnl_pct <= self._stop_loss_pct:
                exits.append(
                    ForcedExit(
                        asset_id=asset_id,
                        reason=(
                            f"global_stop_loss: P&L {pnl_pct:.2%} "
                            f"<= threshold {self._stop_loss_pct:.2%}"
                        ),
                        urgency="high",
                    )
                )
            elif self._take_profit_pct is not None and pnl_pct >= self._take_profit_pct:
                exits.append(
                    ForcedExit(
                        asset_id=asset_id,
                        reason=(
                            f"global_take_profit: P&L {pnl_pct:.2%} "
                            f">= threshold {self._take_profit_pct:.2%}"
                        ),
                        urgency="high",
                    )
                )

        return exits
