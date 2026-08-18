"""GlobalStopPolicy — portfolio-wide take-profit / stop-loss with optional tiers."""
from __future__ import annotations

from cquant.riskguard.policies.forced_exit import ForcedExit, ForcedExitPolicy

MAX_TIERS_PER_SIDE = 3


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
        Mutually exclusive with ``stop_loss_tiers``.
    take_profit_pct:
        Minimum acceptable gain as a positive fraction (e.g. ``0.20``
        means 20 % profit).  ``None`` disables the take-profit leg.
        Mutually exclusive with ``take_profit_tiers``.
    stop_loss_tiers:
        Optional tiered stop-loss ladder (each tier ``{"threshold": <=0,
        "fraction": (0, 1]}``, at most 3 tiers).  Each breached tier
        force-exits ``fraction`` of the position (ratchet semantics:
        a tier fires at most once per armed cycle).
    take_profit_tiers:
        Optional tiered take-profit ladder (each tier ``{"threshold": >=0,
        "fraction": (0, 1]}``, at most 3 tiers).  Same ratchet/rearm
        semantics as the stop-loss side.
    tier_rearm_buffer:
        Hysteresis buffer (positive fraction).  A fired stop-loss tier
        re-arms after P&L recovers above ``threshold + buffer``; a fired
        take-profit tier re-arms after P&L falls below
        ``threshold - buffer``.
    tiers:
        Legacy alias for ``stop_loss_tiers`` (bit-for-bit compatible).
        Providing both raises ``ValueError`` (ambiguous).
    """

    def __init__(
        self,
        stop_loss_pct: float | None = None,
        take_profit_pct: float | None = None,
        stop_loss_tiers: list[dict] | None = None,
        take_profit_tiers: list[dict] | None = None,
        tier_rearm_buffer: float = 0.005,
        tiers: list[dict] | None = None,
    ) -> None:
        if tiers is not None and stop_loss_tiers is not None:
            raise ValueError(
                "Specify either 'tiers' (legacy alias) or "
                "'stop_loss_tiers', not both"
            )
        if tiers is not None:
            stop_loss_tiers = tiers

        # Input validation — single thresholds
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

        # Same-side tiers / pct mutex (hard error — tiers would silently
        # shadow the single threshold otherwise)
        if stop_loss_pct is not None and stop_loss_tiers is not None:
            raise ValueError(
                "stop_loss_pct and stop_loss_tiers are mutually exclusive"
            )
        if take_profit_pct is not None and take_profit_tiers is not None:
            raise ValueError(
                "take_profit_pct and take_profit_tiers are mutually exclusive"
            )

        self._stop_loss_tiers = self._validate_tiers(
            stop_loss_tiers, side="sl", sign=-1
        )
        self._take_profit_tiers = self._validate_tiers(
            take_profit_tiers, side="tp", sign=+1
        )

        self._stop_loss_pct = stop_loss_pct
        self._take_profit_pct = take_profit_pct
        self._tier_rearm_buffer = tier_rearm_buffer
        # Fallback state when engine doesn't supply one
        self._own_state: dict = {"fired_tiers": {}}

    @staticmethod
    def _validate_tiers(
        tiers: list[dict] | None, side: str, sign: int
    ) -> list[dict] | None:
        if tiers is None:
            return None
        if not tiers:
            raise ValueError(f"{side} tiers must be a non-empty list or None")
        if len(tiers) > MAX_TIERS_PER_SIDE:
            raise ValueError(
                f"{side} tiers exceed max of {MAX_TIERS_PER_SIDE}, "
                f"got {len(tiers)}"
            )
        for t in tiers:
            if "threshold" not in t or "fraction" not in t:
                raise ValueError(
                    f"each tier needs 'threshold' and 'fraction', got {t}"
                )
            if sign < 0 and t["threshold"] > 0:
                raise ValueError(
                    f"{side} tier threshold must be <= 0, got {t['threshold']}"
                )
            if sign > 0 and t["threshold"] < 0:
                raise ValueError(
                    f"{side} tier threshold must be >= 0, got {t['threshold']}"
                )
            if not (0.0 < t["fraction"] <= 1.0):
                raise ValueError(
                    f"tier fraction must be in (0, 1], got {t['fraction']}"
                )
        # Sort shallowest-first: sl side → descending (closest to 0 first);
        # tp side → ascending (closest to 0 first). Index order = severity.
        return sorted(tiers, key=lambda t: t["threshold"], reverse=(sign < 0))

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

            if self._stop_loss_tiers is not None:
                exits.extend(
                    self._check_tiers_one_side(
                        asset_id, pnl_pct, state["fired_tiers"],
                        self._stop_loss_tiers, side="sl",
                        breach=lambda p, t: p <= t,
                        rearm_ok=lambda p, t: p > t + self._tier_rearm_buffer,
                    )
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
                        exit_fraction=1.0,
                    )
                )

            if self._take_profit_tiers is not None:
                exits.extend(
                    self._check_tiers_one_side(
                        asset_id, pnl_pct, state["fired_tiers"],
                        self._take_profit_tiers, side="tp",
                        breach=lambda p, t: p >= t,
                        rearm_ok=lambda p, t: p < t - self._tier_rearm_buffer,
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
                        exit_fraction=1.0,
                    )
                )

        return exits

    @staticmethod
    def _sides(fired_tiers: dict, asset_id: str) -> dict[str, set]:
        """Two-sided fired state for one asset, migrating legacy formats.

        Legacy: ``fired_tiers[asset]`` was a plain ``set`` of tier indices
        (stop-loss side only). New: ``{"sl": set(), "tp": set()}``.
        """
        entry = fired_tiers.get(asset_id)
        if isinstance(entry, dict) and "sl" in entry:
            return entry
        migrated = {"sl": set(), "tp": set()}
        if isinstance(entry, set):
            migrated["sl"] = entry
        fired_tiers[asset_id] = migrated
        return migrated

    def _check_tiers_one_side(
        self,
        asset_id: str,
        pnl_pct: float,
        fired_tiers: dict,
        tiers: list[dict],
        side: str,
        breach,
        rearm_ok,
    ) -> list[ForcedExit]:
        """Evaluate one side's tier ladder (ratchet + rearm)."""
        sides = self._sides(fired_tiers, asset_id)
        fired = sides[side]

        # Rearm: recovery past threshold ± buffer disarms the tier again
        for idx, tier in enumerate(tiers):
            if idx in fired and rearm_ok(pnl_pct, tier["threshold"]):
                fired.discard(idx)

        # Fire the deepest breached tier that hasn't fired yet (ratchet:
        # at most one tier event per check; deeper tiers fire on later
        # checks as the move extends)
        for idx, tier in enumerate(tiers):
            if breach(pnl_pct, tier["threshold"]) and idx not in fired:
                fired.add(idx)
                return [
                    ForcedExit(
                        asset_id=asset_id,
                        reason=(
                            f"global_{'stop' if side == 'sl' else 'take_profit'}_tier{idx}: "
                            f"P&L {pnl_pct:.2%} "
                            f"{'<=' if side == 'sl' else '>='} "
                            f"threshold {tier['threshold']:.2%}, "
                            f"exit fraction {tier['fraction']:.0%}"
                        ),
                        urgency="high",
                        exit_fraction=tier["fraction"],
                    )
                ]

        return []
