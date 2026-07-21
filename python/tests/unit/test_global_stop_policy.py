"""Tests for GlobalStopPolicy."""
from __future__ import annotations

import pytest

from cquant.riskguard.policies.global_stop import GlobalStopPolicy


def _positions(*asset_ids: str) -> dict:
    """Return a minimal positions dict for the given asset IDs."""
    return {aid: {"quantity": 100} for aid in asset_ids}


class TestGlobalStopLoss:
    """Stop-loss leg tests."""

    def test_triggers_when_loss_exceeds_threshold(self):
        policy = GlobalStopPolicy(stop_loss_pct=-0.05)
        exits = policy.check_exits(
            positions=_positions("SH600000"),
            current_prices={"SH600000": 9.0},
            entry_prices={"SH600000": 10.0},
        )
        assert len(exits) == 1
        assert exits[0].asset_id == "SH600000"
        assert "global_stop_loss" in exits[0].reason
        assert exits[0].urgency == "high"

    def test_no_trigger_when_loss_within_threshold(self):
        policy = GlobalStopPolicy(stop_loss_pct=-0.05)
        exits = policy.check_exits(
            positions=_positions("SH600000"),
            current_prices={"SH600000": 9.6},
            entry_prices={"SH600000": 10.0},
        )
        assert len(exits) == 0

    def test_boundary_at_exact_threshold(self):
        """P&L exactly at the threshold should trigger."""
        policy = GlobalStopPolicy(stop_loss_pct=-0.05)
        exits = policy.check_exits(
            positions=_positions("SH600000"),
            current_prices={"SH600000": 9.5},
            entry_prices={"SH600000": 10.0},
        )
        assert len(exits) == 1
        assert "global_stop_loss" in exits[0].reason


class TestGlobalTakeProfit:
    """Take-profit leg tests."""

    def test_triggers_when_profit_exceeds_threshold(self):
        policy = GlobalStopPolicy(take_profit_pct=0.20)
        exits = policy.check_exits(
            positions=_positions("SH600000"),
            current_prices={"SH600000": 12.5},
            entry_prices={"SH600000": 10.0},
        )
        assert len(exits) == 1
        assert exits[0].asset_id == "SH600000"
        assert "global_take_profit" in exits[0].reason

    def test_no_trigger_when_profit_below_threshold(self):
        policy = GlobalStopPolicy(take_profit_pct=0.20)
        exits = policy.check_exits(
            positions=_positions("SH600000"),
            current_prices={"SH600000": 11.0},
            entry_prices={"SH600000": 10.0},
        )
        assert len(exits) == 0

    def test_boundary_at_exact_threshold(self):
        """P&L exactly at the threshold should trigger."""
        policy = GlobalStopPolicy(take_profit_pct=0.20)
        exits = policy.check_exits(
            positions=_positions("SH600000"),
            current_prices={"SH600000": 12.0},
            entry_prices={"SH600000": 10.0},
        )
        assert len(exits) == 1
        assert "global_take_profit" in exits[0].reason


class TestBothLegs:
    """Combined stop-loss + take-profit tests."""

    def test_multiple_positions_mixed(self):
        policy = GlobalStopPolicy(stop_loss_pct=-0.05, take_profit_pct=0.20)
        exits = policy.check_exits(
            positions=_positions("SH600000", "SZ000001", "SH601318"),
            current_prices={
                "SH600000": 9.0,   # -10% -> stop loss
                "SZ000001": 11.0,  # +10% -> neither
                "SH601318": 13.0,  # +30% -> take profit
            },
            entry_prices={
                "SH600000": 10.0,
                "SZ000001": 10.0,
                "SH601318": 10.0,
            },
        )
        assert len(exits) == 2
        reasons = {e.asset_id: e.reason for e in exits}
        assert "global_stop_loss" in reasons["SH600000"]
        assert "global_take_profit" in reasons["SH601318"]

    def test_no_legs_configured(self):
        """When neither leg is configured, nothing triggers."""
        policy = GlobalStopPolicy()
        exits = policy.check_exits(
            positions=_positions("SH600000"),
            current_prices={"SH600000": 5.0},
            entry_prices={"SH600000": 10.0},
        )
        assert len(exits) == 0


class TestMissingData:
    """Edge cases with missing / invalid data."""

    def test_missing_current_price(self):
        policy = GlobalStopPolicy(stop_loss_pct=-0.05)
        exits = policy.check_exits(
            positions=_positions("SH600000"),
            current_prices={},
            entry_prices={"SH600000": 10.0},
        )
        assert len(exits) == 0

    def test_missing_entry_price(self):
        policy = GlobalStopPolicy(stop_loss_pct=-0.05)
        exits = policy.check_exits(
            positions=_positions("SH600000"),
            current_prices={"SH600000": 9.0},
            entry_prices={},
        )
        assert len(exits) == 0

    def test_zero_entry_price_skipped(self):
        policy = GlobalStopPolicy(stop_loss_pct=-0.05)
        exits = policy.check_exits(
            positions=_positions("SH600000"),
            current_prices={"SH600000": 9.0},
            entry_prices={"SH600000": 0.0},
        )
        assert len(exits) == 0

    def test_negative_entry_price_skipped(self):
        policy = GlobalStopPolicy(stop_loss_pct=-0.05)
        exits = policy.check_exits(
            positions=_positions("SH600000"),
            current_prices={"SH600000": 9.0},
            entry_prices={"SH600000": -5.0},
        )
        assert len(exits) == 0

    def test_empty_positions(self):
        policy = GlobalStopPolicy(stop_loss_pct=-0.05, take_profit_pct=0.20)
        exits = policy.check_exits(
            positions={},
            current_prices={"SH600000": 9.0},
            entry_prices={"SH600000": 10.0},
        )
        assert len(exits) == 0
