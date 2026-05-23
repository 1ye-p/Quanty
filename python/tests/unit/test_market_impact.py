"""Tests for volume participation market impact cost model."""
from __future__ import annotations

from decimal import Decimal

import pytest

from cquant.backtest_vector.costs import CostModel


class TestVolumeParticipationSlippage:
    def test_zero_market_impact_rate_gives_zero_impact(self) -> None:
        model = CostModel()
        impact = model.volume_participation_slippage(
            notional=Decimal("50000"),
            order_qty=1000,
            avg_daily_volume=100_000,
        )
        assert impact == Decimal("0")

    def test_impact_increases_with_larger_order(self) -> None:
        model = CostModel.with_market_impact(rate=Decimal("0.001"))
        small_impact = model.volume_participation_slippage(
            notional=Decimal("50000"), order_qty=1000, avg_daily_volume=100_000,
        )
        large_impact = model.volume_participation_slippage(
            notional=Decimal("50000"), order_qty=10_000, avg_daily_volume=100_000,
        )
        assert large_impact > small_impact

    def test_impact_increases_with_lower_adv(self) -> None:
        model = CostModel.with_market_impact(rate=Decimal("0.001"))
        liquid_impact = model.volume_participation_slippage(
            notional=Decimal("50000"), order_qty=1000, avg_daily_volume=1_000_000,
        )
        illiquid_impact = model.volume_participation_slippage(
            notional=Decimal("50000"), order_qty=1000, avg_daily_volume=10_000,
        )
        assert illiquid_impact > liquid_impact

    def test_zero_adv_returns_zero(self) -> None:
        model = CostModel.with_market_impact(rate=Decimal("0.001"))
        impact = model.volume_participation_slippage(
            notional=Decimal("50000"), order_qty=1000, avg_daily_volume=0,
        )
        assert impact == Decimal("0")

    def test_with_market_impact_factory_sets_rate(self) -> None:
        model = CostModel.with_market_impact(rate=Decimal("0.002"))
        assert model.market_impact_rate == Decimal("0.002")

    def test_default_model_has_zero_impact_rate(self) -> None:
        model = CostModel()
        assert model.market_impact_rate == Decimal("0")

    def test_impact_formula_is_sqrt_based(self) -> None:
        """Quadrupling participation → 2× impact (sqrt relationship)."""
        model = CostModel.with_market_impact(rate=Decimal("0.001"))
        impact_1pct = model.volume_participation_slippage(
            notional=Decimal("100000"), order_qty=1000, avg_daily_volume=100_000,
        )
        impact_4pct = model.volume_participation_slippage(
            notional=Decimal("100000"), order_qty=4000, avg_daily_volume=100_000,
        )
        ratio = float(impact_4pct) / float(impact_1pct)
        assert ratio == pytest.approx(2.0, rel=0.01)
