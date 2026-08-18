"""Tiered GlobalStopPolicy — ratchet dedup + rearm semantics (附录 A)."""
from __future__ import annotations

import pytest

from cquant.riskguard.policies.global_stop import GlobalStopPolicy


TIERS = [
    {"threshold": -0.03, "fraction": 0.3},
    {"threshold": -0.05, "fraction": 0.4},
]


def _check(policy, pnl, state, asset="A", entry=100.0):
    return policy.check_exits(
        positions={asset: {"weight": 0.5}},
        current_prices={asset: entry * (1 + pnl)},
        entry_prices={asset: entry},
        state=state,
    )


class TestTieredGlobalStop:
    def test_tier_ratchet_no_refire(self):
        """-3.5% triggers tier 1 once; persistent -4% must NOT re-fire tier 1."""
        policy = GlobalStopPolicy(tiers=TIERS)
        state = {"fired_tiers": {}}

        # Day 1: -3.5% breaches tier 1 (-3%) but not tier 2 (-5%)
        exits = _check(policy, -0.035, state)
        assert len(exits) == 1
        assert exits[0].exit_fraction == pytest.approx(0.3)
        assert "A" in state["fired_tiers"]
        assert 0 in state["fired_tiers"]["A"]["sl"]  # tier index 0 fired

        # Days 2..N: -4% persists, tier 1 already fired → no re-fire
        for _ in range(5):
            exits = _check(policy, -0.04, state)
            assert exits == []

    def test_tier_deeper_breach_fires_next_tier(self):
        """Dropping to -5.5% fires tier 2 even though tier 1 already fired."""
        policy = GlobalStopPolicy(tiers=TIERS)
        state = {"fired_tiers": {}}

        exits = _check(policy, -0.035, state)
        assert len(exits) == 1 and exits[0].exit_fraction == pytest.approx(0.3)

        # Deeper breach → tier 2 fires with its own fraction
        exits = _check(policy, -0.055, state)
        assert len(exits) == 1
        assert exits[0].exit_fraction == pytest.approx(0.4)
        assert state["fired_tiers"]["A"]["sl"] == {0, 1}

        # Continued deep drawdown → nothing re-fires
        assert _check(policy, -0.06, state) == []

    def test_tier_rearm_on_recovery(self):
        """Recovery above threshold + buffer re-arms the tier."""
        policy = GlobalStopPolicy(tiers=TIERS, tier_rearm_buffer=0.005)
        state = {"fired_tiers": {}}

        assert len(_check(policy, -0.035, state)) == 1

        # Recover to -2.9% (above -3% + 0.5% buffer = -2.5%? No:
        # rearm needs pnl > threshold + buffer = -0.03 + 0.005 = -0.025)
        # -2.9% is above threshold but NOT above threshold+buffer → still armed-off
        assert _check(policy, -0.029, state) == []
        assert 0 in state["fired_tiers"]["A"]["sl"]

        # Recover beyond -2.5% → tier re-armed
        _check(policy, -0.02, state)
        assert 0 not in state["fired_tiers"]["A"]["sl"]

        # Now a fresh breach fires tier 1 again
        exits = _check(policy, -0.035, state)
        assert len(exits) == 1 and exits[0].exit_fraction == pytest.approx(0.3)

    def test_tier_state_none_fallback(self):
        """state=None → policy uses its own internal fired_tiers (still ratchets)."""
        policy = GlobalStopPolicy(tiers=TIERS)

        assert len(_check(policy, -0.035, None)) == 1
        assert _check(policy, -0.04, None) == []

    def test_tiers_validation(self):
        with pytest.raises(ValueError):
            GlobalStopPolicy(tiers=[{"threshold": -0.03}])  # missing fraction
        with pytest.raises(ValueError):
            GlobalStopPolicy(tiers=[{"threshold": 0.03, "fraction": 0.3}])  # positive threshold
        with pytest.raises(ValueError):
            GlobalStopPolicy(tiers=[{"threshold": -0.03, "fraction": 1.5}])  # bad fraction

    def test_single_threshold_backward_compat(self):
        """No tiers → identical behavior to legacy single-threshold policy."""
        legacy = GlobalStopPolicy(stop_loss_pct=-0.05)
        tiered = GlobalStopPolicy(stop_loss_pct=-0.05)

        state = {"fired_tiers": {}}
        for pnl in (-0.02, -0.049, -0.05, -0.06, -0.10, -0.05):
            exits_l = legacy.check_exits(
                {"A": {}}, {"A": 100 * (1 + pnl)}, {"A": 100.0}, state=state)
            exits_t = tiered.check_exits(
                {"A": {}}, {"A": 100 * (1 + pnl)}, {"A": 100.0}, state=state)
            assert len(exits_l) == len(exits_t)
            for el, et in zip(exits_l, exits_t):
                assert el.reason == et.reason
                assert el.exit_fraction == et.exit_fraction == 1.0
                assert el.urgency == et.urgency

        # Take-profit unaffected by state
        tp = GlobalStopPolicy(take_profit_pct=0.2, tiers=TIERS)
        exits = _check(tp, 0.25, {"fired_tiers": {}})
        assert len(exits) == 1 and exits[0].exit_fraction == 1.0
