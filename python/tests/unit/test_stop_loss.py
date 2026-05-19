"""Tests for stop-loss policies."""
import polars as pl
import pytest
from decimal import Decimal
from datetime import date, datetime

from cquant.riskguard.policies.stop_loss import (
    FixedStopLossPolicy,
    TrailingStopLossPolicy,
)
from cquant.riskguard.models import RiskContext
from cquant.core.types import RiskSnapshot, OrderIntent
from cquant.core.enums import RiskDecisionType


def _make_intent(qty: int = 100, side: str = "buy", price: float = 10.0) -> OrderIntent:
    return OrderIntent(
        asset_id="SH600000",
        side=side,
        requested_qty=Decimal(str(qty)),
        limit_price=price,
    )


def _make_ctx_with_position(
    asset_id: str, qty: int, avg_cost: float, current_price: float, nav: float = 1000000
) -> RiskContext:
    # market_value uses avg_cost (cost basis) so the policy can derive entry price
    cost_basis = qty * avg_cost
    return RiskContext(
        as_of_date=date(2025, 6, 1),
        portfolio_nav=Decimal(str(nav)),
        current_positions=pl.DataFrame({
            "asset_id": [asset_id],
            "quantity": [qty],
            "market_value": [cost_basis],
            "weight": [qty * current_price / nav],
        }),
    )


class TestFixedStopLoss:
    def test_approves_buy_without_position(self):
        policy = FixedStopLossPolicy(stop_pct=-0.05)
        ctx = RiskContext(
            as_of_date=date(2025, 6, 1),
            portfolio_nav=Decimal("1000000"),
            current_positions=pl.DataFrame(),
        )
        snap = RiskSnapshot(snapshot_ts=datetime(2025, 6, 1), strategy_id="test")
        decision = policy.evaluate(_make_intent(), snap, ctx)
        assert decision.decision == RiskDecisionType.APPROVED

    def test_approves_buy_when_within_stop(self):
        policy = FixedStopLossPolicy(stop_pct=-0.05)
        # Bought at 10.0, now at 9.8 → -2% loss, within -5% stop
        ctx = _make_ctx_with_position("SH600000", 100, 10.0, 9.8)
        snap = RiskSnapshot(snapshot_ts=datetime(2025, 6, 1), strategy_id="test")
        decision = policy.evaluate(_make_intent(price=9.8), snap, ctx)
        assert decision.decision == RiskDecisionType.APPROVED

    def test_rejects_buy_when_loss_exceeds_stop(self):
        policy = FixedStopLossPolicy(stop_pct=-0.05)
        # Bought at 10.0, now at 9.0 → -10% loss, beyond -5% stop
        ctx = _make_ctx_with_position("SH600000", 100, 10.0, 9.0)
        snap = RiskSnapshot(snapshot_ts=datetime(2025, 6, 1), strategy_id="test")
        decision = policy.evaluate(_make_intent(price=9.0), snap, ctx)
        assert decision.decision == RiskDecisionType.REJECTED

    def test_allows_sell_even_when_stopped(self):
        policy = FixedStopLossPolicy(stop_pct=-0.05)
        ctx = _make_ctx_with_position("SH600000", 100, 10.0, 9.0)
        snap = RiskSnapshot(snapshot_ts=datetime(2025, 6, 1), strategy_id="test")
        decision = policy.evaluate(_make_intent(side="sell", price=9.0), snap, ctx)
        assert decision.decision == RiskDecisionType.APPROVED


class TestTrailingStopLoss:
    def test_triggers_from_peak(self):
        policy = TrailingStopLossPolicy(trail_pct=-0.08)
        ctx = _make_ctx_with_position("SH600000", 100, 10.0, 11.0)
        snap = RiskSnapshot(snapshot_ts=datetime(2025, 6, 1), strategy_id="test")
        # First buy updates peak to 11.0
        policy.evaluate(_make_intent(price=11.0), snap, ctx)
        # Now price drops to 10.0 (9.1% from peak of 11.0)
        decision = policy.evaluate(_make_intent(price=10.0), snap, ctx)
        assert decision.decision == RiskDecisionType.REJECTED

    def test_no_trigger_when_near_peak(self):
        policy = TrailingStopLossPolicy(trail_pct=-0.08)
        ctx = _make_ctx_with_position("SH600000", 100, 10.0, 11.5)
        snap = RiskSnapshot(snapshot_ts=datetime(2025, 6, 1), strategy_id="test")
        policy.evaluate(_make_intent(price=11.5), snap, ctx)
        # Price at 11.0 is 4.3% below peak 11.5 → within 8% trailing stop
        decision = policy.evaluate(_make_intent(price=11.0), snap, ctx)
        assert decision.decision == RiskDecisionType.APPROVED

    def test_allows_sell_when_trailing_stopped(self):
        policy = TrailingStopLossPolicy(trail_pct=-0.08)
        ctx = _make_ctx_with_position("SH600000", 100, 10.0, 11.0)
        snap = RiskSnapshot(snapshot_ts=datetime(2025, 6, 1), strategy_id="test")
        policy.evaluate(_make_intent(price=11.0), snap, ctx)
        decision = policy.evaluate(_make_intent(side="sell", price=10.0), snap, ctx)
        assert decision.decision == RiskDecisionType.APPROVED
