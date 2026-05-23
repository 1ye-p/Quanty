"""Tests for FactorExposureLimitPolicy."""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import polars as pl
import pytest

from cquant.core.enums import RiskDecisionType
from cquant.core.types import OrderIntent, RiskSnapshot
from cquant.riskguard.models import RiskContext
from cquant.riskguard.policies.factor_exposure_limit import FactorExposureLimitPolicy


def _snapshot() -> RiskSnapshot:
    return RiskSnapshot(
        strategy_id="test",
        snapshot_ts=datetime.now(tz=timezone.utc),
        gross_leverage=1.0,
        net_leverage=1.0,
        beta=None,
        drawdown=0.0,
        var_95=None,
        cvar_95=None,
        sector_exposure={},
        factor_exposure={},
    )


def _ctx(factor_exposure: dict[str, float] | None = None) -> RiskContext:
    return RiskContext(
        as_of_date=date(2025, 6, 1),
        portfolio_nav=Decimal("1000000"),
        current_positions=pl.DataFrame(),
        factor_exposure=factor_exposure or {},
    )


def _buy(asset: str = "SSE:600036") -> OrderIntent:
    return OrderIntent(
        asset_id=asset,
        side="buy",
        requested_qty=Decimal("1000"),
        limit_price=Decimal("50.0"),
        strategy_id="test",
    )


class TestFactorExposureLimitPolicy:
    def test_name(self) -> None:
        policy = FactorExposureLimitPolicy(factor_limits={"beta": 0.8})
        assert policy.name == "factor_exposure_limit"

    def test_approves_when_below_limit(self) -> None:
        policy = FactorExposureLimitPolicy(factor_limits={"beta": 0.8})
        ctx = _ctx(factor_exposure={"beta": 0.5})
        decision = policy.evaluate(_buy(), _snapshot(), ctx)
        assert decision.decision == RiskDecisionType.APPROVED

    def test_rejects_when_at_or_above_limit(self) -> None:
        policy = FactorExposureLimitPolicy(factor_limits={"beta": 0.8})
        ctx = _ctx(factor_exposure={"beta": 0.85})
        decision = policy.evaluate(_buy(), _snapshot(), ctx)
        assert decision.decision == RiskDecisionType.REJECTED

    def test_approves_when_factor_not_in_exposure(self) -> None:
        policy = FactorExposureLimitPolicy(factor_limits={"size": 0.5})
        ctx = _ctx(factor_exposure={})
        decision = policy.evaluate(_buy(), _snapshot(), ctx)
        assert decision.decision == RiskDecisionType.APPROVED

    def test_sells_always_approved(self) -> None:
        policy = FactorExposureLimitPolicy(factor_limits={"beta": 0.1})
        sell = OrderIntent(
            asset_id="SSE:600036",
            side="sell",
            requested_qty=Decimal("1000"),
            limit_price=Decimal("50.0"),
            strategy_id="test",
        )
        ctx = _ctx(factor_exposure={"beta": 0.9})
        decision = policy.evaluate(sell, _snapshot(), ctx)
        assert decision.decision == RiskDecisionType.APPROVED

    def test_multiple_factors_any_exceeding_rejects(self) -> None:
        policy = FactorExposureLimitPolicy(factor_limits={"beta": 0.8, "size": 0.3})
        ctx = _ctx(factor_exposure={"beta": 0.5, "size": 0.4})
        decision = policy.evaluate(_buy(), _snapshot(), ctx)
        assert decision.decision == RiskDecisionType.REJECTED
