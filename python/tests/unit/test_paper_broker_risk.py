"""Tests for Paper Broker RiskPolicy integration."""
from __future__ import annotations

from decimal import Decimal

import polars as pl
import pytest

from cquant.core.enums import RiskDecisionType
from cquant.core.types import OrderIntent, RiskDecision, RiskSnapshot
from cquant.execution.broker import Order, OrderStatus
from cquant.execution.paper_broker import PaperBroker
from cquant.riskguard.models import RiskContext
from cquant.riskguard.policies.base import RiskPolicy


class _AlwaysRejectBuysPolicy(RiskPolicy):
    @property
    def name(self) -> str:
        return "always_reject_buys"

    def evaluate(self, candidate: OrderIntent, snapshot: RiskSnapshot, ctx: RiskContext, price: float = 0.0) -> RiskDecision:
        if candidate.side == "buy":
            return RiskDecision(
                decision=RiskDecisionType.REJECTED,
                original_qty=candidate.requested_qty,
                approved_qty=Decimal("0"),
                reasons=["Test rejection"],
                policy_names=[self.name],
            )
        return RiskDecision(
            decision=RiskDecisionType.APPROVED,
            original_qty=candidate.requested_qty,
            approved_qty=candidate.requested_qty,
            reasons=[],
            policy_names=[self.name],
        )


class _AlwaysApprovePolicy(RiskPolicy):
    @property
    def name(self) -> str:
        return "always_approve"

    def evaluate(self, candidate: OrderIntent, snapshot: RiskSnapshot, ctx: RiskContext, price: float = 0.0) -> RiskDecision:
        return RiskDecision(
            decision=RiskDecisionType.APPROVED,
            original_qty=candidate.requested_qty,
            approved_qty=candidate.requested_qty,
            reasons=[],
            policy_names=[self.name],
        )


def _make_order(side: str = "buy", qty: int = 1000) -> Order:
    return Order(order_id="test_001", asset_id="SSE:600036", side=side, qty=qty)


class TestPaperBrokerWithoutPolicies:
    def test_broker_without_policies_fills_normally(self) -> None:
        broker = PaperBroker(initial_cash=1_000_000)
        broker.update_prices({"SSE:600036": 50.0})
        result = broker.submit_order(_make_order("buy", 1000))
        assert result.status == OrderStatus.FILLED

    def test_broker_has_risk_policies_attribute(self) -> None:
        broker = PaperBroker(initial_cash=1_000_000)
        assert hasattr(broker, "_risk_policies")
        assert broker._risk_policies == []


class TestPaperBrokerWithPolicies:
    def test_reject_policy_blocks_buy(self) -> None:
        broker = PaperBroker(
            initial_cash=1_000_000,
            risk_policies=[_AlwaysRejectBuysPolicy()],
        )
        broker.update_prices({"SSE:600036": 50.0})
        result = broker.submit_order(_make_order("buy", 1000))
        assert result.status == OrderStatus.REJECTED

    def test_approve_policy_allows_buy(self) -> None:
        broker = PaperBroker(
            initial_cash=1_000_000,
            risk_policies=[_AlwaysApprovePolicy()],
        )
        broker.update_prices({"SSE:600036": 50.0})
        result = broker.submit_order(_make_order("buy", 1000))
        assert result.status == OrderStatus.FILLED
