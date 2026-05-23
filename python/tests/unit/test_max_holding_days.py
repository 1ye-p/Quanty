"""Tests for MaxHoldingDaysPolicy."""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import polars as pl
import pytest

from cquant.core.enums import RiskDecisionType
from cquant.core.types import OrderIntent, RiskSnapshot
from cquant.riskguard.models import RiskContext
from cquant.riskguard.policies.max_holding_days import MaxHoldingDaysPolicy


def _snapshot() -> RiskSnapshot:
    return RiskSnapshot(
        strategy_id="test",
        snapshot_ts=datetime.now(tz=timezone.utc),
        gross_leverage=1.0, net_leverage=1.0, beta=None,
        drawdown=0.0, var_95=None, cvar_95=None,
        sector_exposure={}, factor_exposure={},
    )


def _ctx(positions=None, entry_dates=None, as_of=date(2025, 6, 1)):
    pos_df = pl.DataFrame(positions) if positions else pl.DataFrame()
    return RiskContext(
        as_of_date=as_of,
        portfolio_nav=Decimal("1000000"),
        current_positions=pos_df,
        extra={"entry_dates": entry_dates or {}},
    )


def _buy(asset="SSE:600036", price=45.0):
    return OrderIntent(
        asset_id=asset, side="buy",
        requested_qty=Decimal("1000"),
        limit_price=Decimal(str(price)),
        strategy_id="test",
    )


class TestMaxHoldingDaysPolicy:
    def test_name(self) -> None:
        assert MaxHoldingDaysPolicy().name == "max_holding_days"

    def test_approves_when_no_entry_date(self) -> None:
        policy = MaxHoldingDaysPolicy(max_days=30)
        ctx = _ctx()
        decision = policy.evaluate(_buy(), _snapshot(), ctx)
        assert decision.decision == RiskDecisionType.APPROVED

    def test_approves_when_holding_within_limit(self) -> None:
        """Held 20 days, limit 30 → approve."""
        policy = MaxHoldingDaysPolicy(max_days=30)
        ctx = _ctx(
            positions=[{"asset_id": "SSE:600036", "quantity": 1000, "market_value": 45_000.0, "weight": 0.05}],
            entry_dates={"SSE:600036": date(2025, 5, 12)},  # 20 days before 2025-06-01
        )
        decision = policy.evaluate(_buy(price=45.0), _snapshot(), ctx)
        assert decision.decision == RiskDecisionType.APPROVED

    def test_rejects_when_over_limit_and_losing(self) -> None:
        """Held 40 days (>30), market_value=50k, avg_entry=50, price=45 → reject."""
        policy = MaxHoldingDaysPolicy(max_days=30)
        ctx = _ctx(
            positions=[{"asset_id": "SSE:600036", "quantity": 1000, "market_value": 50_000.0, "weight": 0.050}],
            entry_dates={"SSE:600036": date(2025, 4, 22)},  # 40 days before 2025-06-01
        )
        decision = policy.evaluate(_buy(price=45.0), _snapshot(), ctx)
        assert decision.decision == RiskDecisionType.REJECTED

    def test_approves_when_over_limit_but_profitable(self) -> None:
        """Held 40 days but position profitable → allow."""
        policy = MaxHoldingDaysPolicy(max_days=30)
        ctx = _ctx(
            positions=[{"asset_id": "SSE:600036", "quantity": 1000, "market_value": 55_000.0, "weight": 0.055}],
            entry_dates={"SSE:600036": date(2025, 4, 22)},
        )
        decision = policy.evaluate(_buy(price=55.0), _snapshot(), ctx)
        assert decision.decision == RiskDecisionType.APPROVED

    def test_sells_always_approved(self) -> None:
        policy = MaxHoldingDaysPolicy(max_days=1)
        sell = OrderIntent(
            asset_id="SSE:600036", side="sell",
            requested_qty=Decimal("1000"), limit_price=Decimal("45.0"),
            strategy_id="test",
        )
        ctx = _ctx(
            positions=[{"asset_id": "SSE:600036", "quantity": 1000, "market_value": 45_000.0, "weight": 0.045}],
            entry_dates={"SSE:600036": date(2025, 1, 1)},
        )
        decision = policy.evaluate(sell, _snapshot(), ctx)
        assert decision.decision == RiskDecisionType.APPROVED
