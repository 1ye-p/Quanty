"""Tests for LeverageLimitPolicy and SectorLimitPolicy."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import polars as pl
import pytest

from cquant.core.enums import OrderSide, RiskDecisionType
from cquant.core.types import OrderIntent, RiskSnapshot
from cquant.riskguard.models import RiskContext
from cquant.riskguard.policies.leverage_limit import LeverageLimitPolicy
from cquant.riskguard.policies.sector_limit import SectorLimitPolicy


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_snapshot(gross_leverage: float = 0.0) -> RiskSnapshot:
    return RiskSnapshot(
        snapshot_ts=datetime(2025, 6, 30, tzinfo=None),
        strategy_id="test",
        gross_leverage=gross_leverage,
    )


def _make_ctx(
    nav: Decimal = Decimal("1000000"),
    sector_exposure: dict[str, float] | None = None,
) -> RiskContext:
    return RiskContext(
        as_of_date=date(2025, 6, 30),
        portfolio_nav=nav,
        current_positions=pl.DataFrame(
            {"asset_id": [], "quantity": [], "market_value": [], "weight": []},
            schema={
                "asset_id": pl.Utf8,
                "quantity": pl.Float64,
                "market_value": pl.Float64,
                "weight": pl.Float64,
            },
        ),
        sector_exposure=sector_exposure or {},
    )


def _make_order(
    asset_id: str = "SSE:600036",
    side: OrderSide = OrderSide.BUY,
    qty: int = 500,
) -> OrderIntent:
    return OrderIntent(
        asset_id=asset_id,
        side=side,
        requested_qty=Decimal(str(qty)),
    )


# ── LeverageLimitPolicy tests ────────────────────────────────────────────────

class TestLeverageLimitPolicy:
    def test_within_limit_approved(self) -> None:
        """Leverage well below max should return APPROVED."""
        policy = LeverageLimitPolicy(max_gross_leverage=1.0)
        snapshot = _make_snapshot(gross_leverage=0.3)
        ctx = _make_ctx(nav=Decimal("1000000"))
        # 500 shares * ~10 price = 5000 notional = 0.005 of NAV
        order = _make_order(qty=500)

        decision = policy.evaluate(order, snapshot, ctx, price=10.0)
        assert decision.decision == RiskDecisionType.APPROVED
        assert decision.approved_qty == order.requested_qty

    def test_exceeds_limit_rejected(self) -> None:
        """Gross leverage already at max should return REJECTED."""
        policy = LeverageLimitPolicy(max_gross_leverage=1.0)
        snapshot = _make_snapshot(gross_leverage=1.0)
        ctx = _make_ctx(nav=Decimal("1000000"))
        order = _make_order(qty=100)

        decision = policy.evaluate(order, snapshot, ctx, price=10.0)
        assert decision.decision == RiskDecisionType.REJECTED
        assert decision.approved_qty == Decimal("0")

    def test_clipped_when_would_exceed(self) -> None:
        """Order that would push over limit should be CLIPPED."""
        policy = LeverageLimitPolicy(max_gross_leverage=1.0)
        # Current leverage 0.95, NAV 1000000, buying 10000 shares at 10 = 100000 notional
        # Would push to 0.95 + 0.10 = 1.05 > 1.0
        snapshot = _make_snapshot(gross_leverage=0.95)
        ctx = _make_ctx(nav=Decimal("1000000"))
        order = _make_order(qty=10000)

        decision = policy.evaluate(order, snapshot, ctx, price=10.0)
        assert decision.decision == RiskDecisionType.CLIPPED
        assert decision.approved_qty < order.requested_qty
        # Allowed additional notional = (1.0 - 0.95) * 1000000 = 50000
        # Max shares = 50000 / 10 = 5000, rounded to lot 100 = 5000
        assert decision.approved_qty == Decimal("5000")

    def test_name(self) -> None:
        policy = LeverageLimitPolicy()
        assert policy.name == "leverage_limit"


# ── SectorLimitPolicy tests ──────────────────────────────────────────────────

class TestSectorLimitPolicy:
    def test_within_sector_limit_approved(self) -> None:
        """Sector exposure below max should return APPROVED."""
        sector_map = {"SSE:600036": "finance"}
        policy = SectorLimitPolicy(max_sector_pct=0.30, sector_map=sector_map)
        snapshot = _make_snapshot()
        ctx = _make_ctx(
            nav=Decimal("1000000"),
            sector_exposure={"finance": 0.10},
        )
        order = _make_order(qty=100)

        decision = policy.evaluate(order, snapshot, ctx, price=10.0)
        assert decision.decision == RiskDecisionType.APPROVED
        assert decision.approved_qty == order.requested_qty

    def test_sector_exposure_lookup(self) -> None:
        """Policy uses ctx.sector_exposure for current exposure."""
        sector_map = {"SSE:600036": "technology"}
        policy = SectorLimitPolicy(max_sector_pct=0.20, sector_map=sector_map)
        snapshot = _make_snapshot()
        ctx = _make_ctx(
            nav=Decimal("1000000"),
            sector_exposure={"technology": 0.18},
        )
        # 500 * 10 = 5000 notional = 0.005 of NAV → sector would become 0.185
        order = _make_order(qty=500)

        decision = policy.evaluate(order, snapshot, ctx, price=10.0)
        assert decision.decision == RiskDecisionType.APPROVED

    def test_sector_at_limit_rejected(self) -> None:
        """Sector already at max should return REJECTED."""
        sector_map = {"SSE:600036": "finance"}
        policy = SectorLimitPolicy(max_sector_pct=0.30, sector_map=sector_map)
        snapshot = _make_snapshot()
        ctx = _make_ctx(
            nav=Decimal("1000000"),
            sector_exposure={"finance": 0.30},
        )
        order = _make_order(qty=100)

        decision = policy.evaluate(order, snapshot, ctx, price=10.0)
        assert decision.decision == RiskDecisionType.REJECTED

    def test_sector_clipped(self) -> None:
        """Order pushing sector over limit should be CLIPPED."""
        sector_map = {"SSE:600036": "finance"}
        policy = SectorLimitPolicy(max_sector_pct=0.30, sector_map=sector_map)
        snapshot = _make_snapshot()
        ctx = _make_ctx(
            nav=Decimal("1000000"),
            sector_exposure={"finance": 0.25},
        )
        # 10000 shares * 10 = 100000 notional = 0.10 → would be 0.35 > 0.30
        order = _make_order(qty=10000)

        decision = policy.evaluate(order, snapshot, ctx, price=10.0)
        assert decision.decision == RiskDecisionType.CLIPPED
        # Allowed additional = (0.30 - 0.25) * 1000000 = 50000
        # Max shares = 50000 / 10 = 5000
        assert decision.approved_qty == Decimal("5000")

    def test_unknown_sector_approved(self) -> None:
        """Asset not in sector_map should be APPROVED (no info)."""
        policy = SectorLimitPolicy(max_sector_pct=0.30, sector_map={})
        snapshot = _make_snapshot()
        ctx = _make_ctx(nav=Decimal("1000000"))
        order = _make_order(qty=10000)

        decision = policy.evaluate(order, snapshot, ctx, price=10.0)
        assert decision.decision == RiskDecisionType.APPROVED

    def test_name(self) -> None:
        policy = SectorLimitPolicy()
        assert policy.name == "sector_limit"
