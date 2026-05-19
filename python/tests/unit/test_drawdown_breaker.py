"""Tests for drawdown circuit breaker policy."""
from datetime import date, datetime
from decimal import Decimal

import polars as pl
import pytest

from cquant.core.enums import RiskDecisionType
from cquant.core.types import OrderIntent, RiskSnapshot
from cquant.riskguard.models import RiskContext
from cquant.riskguard.policies.drawdown_breaker import DrawdownBreakerPolicy


def _make_intent(side: str = "buy", qty: int = 100) -> OrderIntent:
    return OrderIntent(
        asset_id="SSE:600000",
        side=side,
        requested_qty=Decimal(str(qty)),
    )


def _make_snapshot(drawdown: float) -> RiskSnapshot:
    return RiskSnapshot(
        snapshot_ts=datetime(2025, 6, 1),
        strategy_id="test",
        drawdown=drawdown,
    )


def _make_ctx(nav: float = 1_000_000) -> RiskContext:
    return RiskContext(
        as_of_date=date(2025, 6, 1),
        portfolio_nav=Decimal(str(nav)),
        current_positions=pl.DataFrame(),
    )


class TestDrawdownBreaker:
    def test_approves_when_no_drawdown(self):
        policy = DrawdownBreakerPolicy(max_drawdown=-0.10)
        snap = _make_snapshot(0.0)
        decision = policy.evaluate(_make_intent(), snap, _make_ctx())
        assert decision.decision == RiskDecisionType.APPROVED

    def test_approves_when_drawdown_within_limit(self):
        policy = DrawdownBreakerPolicy(max_drawdown=-0.10)
        snap = _make_snapshot(-0.05)
        decision = policy.evaluate(_make_intent(), snap, _make_ctx())
        assert decision.decision == RiskDecisionType.APPROVED

    def test_rejects_buy_when_drawdown_exceeded(self):
        policy = DrawdownBreakerPolicy(max_drawdown=-0.10)
        snap = _make_snapshot(-0.15)
        decision = policy.evaluate(_make_intent(side="buy"), snap, _make_ctx())
        assert decision.decision == RiskDecisionType.REJECTED
        assert any("drawdown" in r.lower() for r in decision.reasons)

    def test_allows_sell_when_drawdown_exceeded(self):
        policy = DrawdownBreakerPolicy(max_drawdown=-0.10)
        snap = _make_snapshot(-0.15)
        decision = policy.evaluate(_make_intent(side="sell"), snap, _make_ctx())
        assert decision.decision == RiskDecisionType.APPROVED

    def test_custom_threshold(self):
        policy = DrawdownBreakerPolicy(max_drawdown=-0.20)
        snap = _make_snapshot(-0.15)
        decision = policy.evaluate(_make_intent(), snap, _make_ctx())
        assert decision.decision == RiskDecisionType.APPROVED

        snap2 = _make_snapshot(-0.25)
        decision2 = policy.evaluate(_make_intent(), snap2, _make_ctx())
        assert decision2.decision == RiskDecisionType.REJECTED
