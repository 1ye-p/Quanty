"""Tests for graduated DrawdownBreakerPolicy."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from cquant.core.enums import RiskDecisionType
from cquant.core.types import OrderIntent, RiskSnapshot
from cquant.riskguard.models import RiskContext
from cquant.riskguard.policies.drawdown_breaker import DrawdownBreakerPolicy

_TS = datetime(2025, 6, 1, tzinfo=timezone.utc)


def _snapshot(drawdown: float) -> RiskSnapshot:
    return RiskSnapshot(
        snapshot_ts=_TS,
        strategy_id="test",
        gross_leverage=1.0,
        net_leverage=1.0,
        beta=None,
        drawdown=drawdown,
        var_95=None,
        cvar_95=None,
        sector_exposure={},
        factor_exposure={},
    )


def _buy_intent(qty: int = 1000) -> OrderIntent:
    return OrderIntent(
        asset_id="SSE:600036",
        side="buy",
        requested_qty=Decimal(qty),
        limit_price=None,
        strategy_id="test",
    )


def _ctx() -> RiskContext:
    import polars as pl
    from datetime import date
    return RiskContext(
        as_of_date=date(2025, 6, 1),
        portfolio_nav=Decimal("1000000"),
        current_positions=pl.DataFrame(),
    )


class TestBackwardCompatibility:
    def test_single_threshold_rejects_below_max_drawdown(self) -> None:
        policy = DrawdownBreakerPolicy(max_drawdown=-0.10)
        decision = policy.evaluate(_buy_intent(), _snapshot(-0.15), _ctx())
        assert decision.decision == RiskDecisionType.REJECTED
        assert decision.approved_qty == Decimal("0")

    def test_single_threshold_approves_above_max_drawdown(self) -> None:
        policy = DrawdownBreakerPolicy(max_drawdown=-0.10)
        decision = policy.evaluate(_buy_intent(), _snapshot(-0.05), _ctx())
        assert decision.decision == RiskDecisionType.APPROVED

    def test_sells_always_approved(self) -> None:
        policy = DrawdownBreakerPolicy(max_drawdown=-0.10)
        sell = OrderIntent(
            asset_id="SSE:600036",
            side="sell",
            requested_qty=Decimal("1000"),
            limit_price=None,
            strategy_id="test",
        )
        decision = policy.evaluate(sell, _snapshot(-0.20), _ctx())
        assert decision.decision == RiskDecisionType.APPROVED


class TestGraduatedLevels:
    def test_graduated_levels_construction(self) -> None:
        policy = DrawdownBreakerPolicy(levels=[(-0.05, 0.5), (-0.10, 0.0)])
        assert policy.name == "drawdown_breaker"

    def test_no_threshold_breached_approves_full_qty(self) -> None:
        policy = DrawdownBreakerPolicy(levels=[(-0.05, 0.5), (-0.10, 0.0)])
        decision = policy.evaluate(_buy_intent(1000), _snapshot(-0.02), _ctx())
        assert decision.decision == RiskDecisionType.APPROVED
        assert decision.approved_qty == Decimal("1000")

    def test_first_threshold_clips_to_half(self) -> None:
        policy = DrawdownBreakerPolicy(levels=[(-0.05, 0.5), (-0.10, 0.0)])
        decision = policy.evaluate(_buy_intent(1000), _snapshot(-0.07), _ctx())
        assert decision.decision == RiskDecisionType.CLIPPED
        assert decision.approved_qty == Decimal("500")

    def test_second_threshold_rejects(self) -> None:
        policy = DrawdownBreakerPolicy(levels=[(-0.05, 0.5), (-0.10, 0.0)])
        decision = policy.evaluate(_buy_intent(1000), _snapshot(-0.12), _ctx())
        assert decision.decision == RiskDecisionType.REJECTED
        assert decision.approved_qty == Decimal("0")

    def test_levels_override_max_drawdown_when_both_provided(self) -> None:
        policy = DrawdownBreakerPolicy(
            max_drawdown=-0.20,
            levels=[(-0.05, 0.5), (-0.10, 0.0)],
        )
        decision = policy.evaluate(_buy_intent(1000), _snapshot(-0.07), _ctx())
        assert decision.decision == RiskDecisionType.CLIPPED

    def test_sells_still_approved_with_graduated_levels(self) -> None:
        policy = DrawdownBreakerPolicy(levels=[(-0.05, 0.5), (-0.10, 0.0)])
        sell = OrderIntent(
            asset_id="SSE:600036",
            side="sell",
            requested_qty=Decimal("1000"),
            limit_price=None,
            strategy_id="test",
        )
        decision = policy.evaluate(sell, _snapshot(-0.20), _ctx())
        assert decision.decision == RiskDecisionType.APPROVED
