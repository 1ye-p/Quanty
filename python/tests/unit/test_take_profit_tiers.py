"""Bidirectional tiered GlobalStopPolicy — take_profit_tiers (附录 B)."""
from __future__ import annotations

import pytest

from cquant.riskguard.policies.global_stop import GlobalStopPolicy


TP_TIERS = [
    {"threshold": 0.15, "fraction": 0.5},
    {"threshold": 0.30, "fraction": 1.0},
]


def _check(policy, pnl, state, asset="A", entry=100.0):
    return policy.check_exits(
        positions={asset: {"weight": 0.5}},
        current_prices={asset: entry * (1 + pnl)},
        entry_prices={asset: entry},
        state=state,
    )


class TestTakeProfitTiers:
    def test_tp_tier_partial_exit(self):
        """+16% breaches tp tier 0 (15%) → partial exit 50%."""
        policy = GlobalStopPolicy(take_profit_tiers=TP_TIERS)
        state = {"fired_tiers": {}}

        exits = _check(policy, 0.16, state)
        assert len(exits) == 1
        assert exits[0].exit_fraction == pytest.approx(0.5)
        assert "tp" in state["fired_tiers"]["A"]
        assert 0 in state["fired_tiers"]["A"]["tp"]

        # Deeper gain → tier 1 fires full exit
        exits = _check(policy, 0.31, state)
        assert len(exits) == 1
        assert exits[0].exit_fraction == pytest.approx(1.0)
        assert state["fired_tiers"]["A"]["tp"] == {0, 1}

    def test_tp_ratchet_no_refire(self):
        """After firing at +16%, pullback to +14% then +17% must NOT re-fire."""
        policy = GlobalStopPolicy(
            take_profit_tiers=TP_TIERS, tier_rearm_buffer=0.02
        )
        state = {"fired_tiers": {}}

        assert len(_check(policy, 0.16, state)) == 1

        # Pull back to +14% (above 15% - 2% = 13% rearm line → still fired)
        assert _check(policy, 0.14, state) == []
        assert 0 in state["fired_tiers"]["A"]["tp"]

        # Rise again to +17% — tier 0 already fired → no re-fire
        assert _check(policy, 0.17, state) == []

    def test_tp_rearm_after_pullback(self):
        """Pullback below threshold - buffer re-arms; fresh breach re-fires."""
        policy = GlobalStopPolicy(
            take_profit_tiers=TP_TIERS, tier_rearm_buffer=0.02
        )
        state = {"fired_tiers": {}}

        assert len(_check(policy, 0.16, state)) == 1

        # Pull back to +9% (< 15% - 2% = 13%) → tier re-armed
        assert _check(policy, 0.09, state) == []
        assert 0 not in state["fired_tiers"]["A"]["tp"]

        # Rise back to +16% → fires again
        exits = _check(policy, 0.16, state)
        assert len(exits) == 1
        assert exits[0].exit_fraction == pytest.approx(0.5)

    def test_both_sides_independent(self):
        """tp tiers + single stop_loss_pct coexist, each side fires on its own."""
        policy = GlobalStopPolicy(
            stop_loss_pct=-0.05, take_profit_tiers=TP_TIERS
        )
        state = {"fired_tiers": {}}

        # Gain side: tiered partial exit
        exits = _check(policy, 0.16, state)
        assert len(exits) == 1
        assert exits[0].exit_fraction == pytest.approx(0.5)

        # Loss side: single threshold full exit
        exits = _check(policy, -0.06, state)
        assert len(exits) == 1
        assert exits[0].exit_fraction == pytest.approx(1.0)
        assert "global_stop_loss" in exits[0].reason

    def test_threshold_sign_validation(self):
        with pytest.raises(ValueError):
            GlobalStopPolicy(
                take_profit_tiers=[{"threshold": -0.15, "fraction": 0.5}]
            )
        with pytest.raises(ValueError):
            GlobalStopPolicy(
                stop_loss_tiers=[{"threshold": 0.03, "fraction": 0.3}]
            )

    def test_max_three_tiers(self):
        four_sl = [
            {"threshold": -0.02, "fraction": 0.2},
            {"threshold": -0.03, "fraction": 0.2},
            {"threshold": -0.04, "fraction": 0.3},
            {"threshold": -0.05, "fraction": 0.3},
        ]
        with pytest.raises(ValueError):
            GlobalStopPolicy(stop_loss_tiers=four_sl)

        four_tp = [
            {"threshold": 0.10, "fraction": 0.2},
            {"threshold": 0.15, "fraction": 0.2},
            {"threshold": 0.20, "fraction": 0.3},
            {"threshold": 0.30, "fraction": 0.3},
        ]
        with pytest.raises(ValueError):
            GlobalStopPolicy(take_profit_tiers=four_tp)

        # 3 tiers per side is fine
        GlobalStopPolicy(stop_loss_tiers=four_sl[:3])
        GlobalStopPolicy(take_profit_tiers=four_tp[:3])

    def test_tiers_pct_mutex(self):
        sl_tiers = [{"threshold": -0.03, "fraction": 0.5}]
        tp_tiers = [{"threshold": 0.15, "fraction": 0.5}]
        with pytest.raises(ValueError):
            GlobalStopPolicy(stop_loss_pct=-0.05, stop_loss_tiers=sl_tiers)
        with pytest.raises(ValueError):
            GlobalStopPolicy(take_profit_pct=0.20, take_profit_tiers=tp_tiers)
        # Cross-side combos are fine
        GlobalStopPolicy(stop_loss_pct=-0.05, take_profit_tiers=tp_tiers)
        GlobalStopPolicy(take_profit_pct=0.20, stop_loss_tiers=sl_tiers)

    def test_legacy_tiers_alias(self):
        """Old `tiers=[...]` behaves identically to `stop_loss_tiers=[...]`."""
        legacy = GlobalStopPolicy(tiers=[
            {"threshold": -0.03, "fraction": 0.3},
            {"threshold": -0.05, "fraction": 0.4},
        ])
        named = GlobalStopPolicy(stop_loss_tiers=[
            {"threshold": -0.03, "fraction": 0.3},
            {"threshold": -0.05, "fraction": 0.4},
        ])

        state_l = {"fired_tiers": {}}
        state_n = {"fired_tiers": {}}
        for pnl in (-0.02, -0.035, -0.04, -0.055, -0.06, -0.02, -0.035):
            el = _check(legacy, pnl, state_l)
            en = _check(named, pnl, state_n)
            assert [(e.reason, e.exit_fraction, e.urgency) for e in el] == [
                (e.reason, e.exit_fraction, e.urgency) for e in en
            ]
        assert state_l["fired_tiers"]["A"]["sl"] == state_n["fired_tiers"]["A"]["sl"]

        # Ambiguity: both alias and named → hard error
        with pytest.raises(ValueError):
            GlobalStopPolicy(
                tiers=[{"threshold": -0.03, "fraction": 0.3}],
                stop_loss_tiers=[{"threshold": -0.03, "fraction": 0.3}],
            )

    def test_fired_tiers_legacy_set_migration(self):
        """Old single-layer set state is read as the sl side."""
        policy = GlobalStopPolicy(stop_loss_tiers=[
            {"threshold": -0.03, "fraction": 0.3},
        ])
        state = {"fired_tiers": {"A": {0}}}  # legacy format: tier 0 fired

        # -4% persists, tier 0 already fired (migrated) → no re-fire
        assert _check(policy, -0.04, state) == []
        # State migrated to two-sided structure
        assert state["fired_tiers"]["A"]["sl"] == {0}
        assert state["fired_tiers"]["A"]["tp"] == set()
