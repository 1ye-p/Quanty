import pytest

from cquant.riskguard.policies.forced_exit import ForcedExit


class TestExitFraction:
    def test_default_fraction_is_one(self):
        """默认 exit_fraction=1.0（全平，向后兼容）。"""
        fe = ForcedExit(asset_id="000001.SZ", reason="stop loss")
        assert fe.exit_fraction == 1.0

    def test_fraction_half_valid(self):
        """exit_fraction=0.5 合法（半仓平仓）。"""
        fe = ForcedExit(asset_id="000001.SZ", reason="partial take profit", exit_fraction=0.5)
        assert fe.exit_fraction == 0.5

    def test_fraction_zero_raises(self):
        """exit_fraction=0.0 → ValueError。"""
        with pytest.raises(ValueError):
            ForcedExit(asset_id="000001.SZ", reason="x", exit_fraction=0.0)

    def test_fraction_negative_raises(self):
        """exit_fraction=-0.1 → ValueError。"""
        with pytest.raises(ValueError):
            ForcedExit(asset_id="000001.SZ", reason="x", exit_fraction=-0.1)

    def test_fraction_above_one_raises(self):
        """exit_fraction=1.1 → ValueError。"""
        with pytest.raises(ValueError):
            ForcedExit(asset_id="000001.SZ", reason="x", exit_fraction=1.1)

    def test_fraction_one_valid(self):
        """exit_fraction=1.0 合法（边界）。"""
        fe = ForcedExit(asset_id="000001.SZ", reason="x", exit_fraction=1.0)
        assert fe.exit_fraction == 1.0
