"""GlobalStopPolicy — portfolio-wide take-profit / stop-loss with optional tiers."""
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
    tiers:
        Optional tiered stop-loss ladder, e.g.
        ``[{"threshold": -0.03, "fraction": 0.3},
           {"threshold": -0.05, "fraction": 0.4}]``.  When provided,
        each breached tier force-exits ``fraction`` of the position
        (ratchet semantics: a tier fires at most once per armed cycle).
        When ``None``, the single ``stop_loss_pct`` threshold exits the
        full position (legacy behavior).
    tier_rearm_buffer:
        Hysteresis buffer (positive fraction).  A fired tier re-arms only
        after P&L recovers above ``threshold + tier_rearm_buffer``.
    """

    def __init__(
        self,
        stop_loss_pct: float | None = None,
        take_profit_pct: float | None = None,
        tiers: list[dict] | None = None,
        tier_rearm_buffer: float = 0.005,
    ) -> None:
        # Input validation
        if stop_loss_pct is not None and stop_loss_pct > 0:
            raise ValueError(f"stop_loss_pct must be negative or None, got {stop_loss_pct}")
        if take_profit_pct is not None and take_profit_pct < 0:
            raise ValueError(f"take_profit_pct must be positive or None, got {take_profit_pct}")
        if stop_loss_pct is not None and take_profit_pct is not None:
            if stop_loss_pct >= take_profit_pct:
                raise ValueError(
                    f"stop_loss_pct ({stop_loss_pct}) must be less than "
                    f"take_profit_pct ({take_profit_pct})"
                )
        if tier_rearm_buffer < 0:
            raise ValueError(
                f"tier_rearm_buffer must be non-negative, got {tier_rearm_buffer}"
            )

        if tiers is not None:
            if not tiers:
                raise ValueError("tiers must be a non-empty list or None")
            for t in tiers:
                if "threshold" not in t or "fraction" not in t:
                    raise ValueError(
                        f"each tier needs 'threshold' and 'fraction', got {t}"
                    )
                if t["threshold"] >= 0:
                    raise ValueError(
                        f"tier threshold must be negative, got {t['threshold']}"
                    )
                if not (0.0 < t["fraction"] <= 1.0):
                    raise ValueError(
                        f"tier fraction must be in (0, 1], got {t['fraction']}"
                    )
            # Sort by threshold descending (shallowest first)
            self._tiers = sorted(tiers, key=lambda t: t["threshold"], reverse=True)
        else:
            self._tiers = None

        self._stop_loss_pct = stop_loss_pct
        self._take_profit_pct = take_profit_pct
        self._tier_rearm_buffer = tier_rearm_buffer
        # Fallback state when engine doesn't supply one
        self._own_state: dict = {"fired_tiers": {}}

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
        if state is None:
            state = self._own_state
        state.setdefault("fired_tiers", {})

        exits: list[ForcedExit] = []
        for asset_id in positions:
            ep = entry_prices.get(asset_id)
            cp = current_prices.get(asset_id)
            if ep is None or cp is None or ep <= 0:
                continue

            pnl_pct = (cp - ep) / ep

            if self._tiers is not None:
                exits.extend(
                    self._check_tiers(asset_id, pnl_pct, state["fired_tiers"])
                )
            elif self._stop_loss_pct is not None and pnl_pct <= self._stop_loss_pct:
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

            if self._take_profit_pct is not None and pnl_pct >= self._take_profit_pct:
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

    def _check_tiers(
        self,
        asset_id: str,
        pnl_pct: float,
        fired_tiers: dict[str, set],
    ) -> list[ForcedExit]:
        """Evaluate the tier ladder for one asset (ratchet + rearm)."""
        fired = fired_tiers.setdefault(asset_id, set())

        # Rearm: recovery above threshold + buffer disarms the tier again
        for idx, tier in enumerate(self._tiers):
            if idx in fired and pnl_pct > tier["threshold"] + self._tier_rearm_buffer:
                fired.discard(idx)

        # Fire the deepest breached tier that hasn't fired yet (ratchet:
        # at most one tier event per check; deeper tiers fire on later
        # checks as drawdown deepens)
        for idx, tier in enumerate(self._tiers):
            if pnl_pct <= tier["threshold"] and idx not in fired:
                fired.add(idx)
                return [
                    ForcedExit(
                        asset_id=asset_id,
                        reason=(
                            f"global_stop_tier{idx}: P&L {pnl_pct:.2%} "
                            f"<= threshold {tier['threshold']:.2%}, "
                            f"exit fraction {tier['fraction']:.0%}"
                        ),
                        urgency="high",
                        exit_fraction=tier["fraction"],
                    )
                ]

        return []
