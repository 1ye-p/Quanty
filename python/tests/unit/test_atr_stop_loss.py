"""Tests for ATRStopLossPolicy."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import numpy as np
import polars as pl
import pytest

from cquant.core.enums import RiskDecisionType
from cquant.core.types import OrderIntent, RiskSnapshot
from cquant.riskguard.models import RiskContext
from cquant.riskguard.policies.atr_stop_loss import ATRStopLossPolicy, compute_atr


def _make_ohlcv(n_days: int = 30, seed: int = 42) -> pl.DataFrame:
    rng = np.random.default_rng(seed)
    dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(n_days)]
    rows = []
    close = 100.0
    for d in dates:
        open_ = close * (1 + rng.normal(0, 0.005))
        high = open_ * (1 + abs(rng.normal(0, 0.01)))
        low = open_ * (1 - abs(rng.normal(0, 0.01)))
        close = (open_ + high + low) / 3
        rows.append({
            "asset_id": "SSE:600036",
            "trade_date": d,
            "open": open_, "high": high, "low": low, "close": close,
        })
    return pl.DataFrame(rows)


class TestComputeATR:
    def test_returns_dict_with_asset_keys(self) -> None:
        prices = _make_ohlcv()
        atr = compute_atr(prices, n=14)
        assert "SSE:600036" in atr

    def test_atr_is_positive(self) -> None:
        prices = _make_ohlcv()
        atr = compute_atr(prices, n=14)
        assert atr["SSE:600036"] > 0

    def test_smaller_n_gives_valid_atr(self) -> None:
        prices = _make_ohlcv(n_days=30)
        atr_5 = compute_atr(prices, n=5)
        atr_14 = compute_atr(prices, n=14)
        assert atr_5["SSE:600036"] > 0
        assert atr_14["SSE:600036"] > 0


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


def _ctx(positions_data=None, atr=None):
    pos_df = pl.DataFrame(positions_data) if positions_data else pl.DataFrame()
    return RiskContext(
        as_of_date=date(2025, 6, 1),
        portfolio_nav=Decimal("1000000"),
        current_positions=pos_df,
        extra={"atr": atr} if atr else {},
    )


def _buy(asset: str, price: float, qty: int = 1000) -> OrderIntent:
    return OrderIntent(
        asset_id=asset, side="buy",
        requested_qty=Decimal(qty),
        limit_price=Decimal(str(price)),
        strategy_id="test",
    )


class TestATRStopLossPolicy:
    def test_name(self) -> None:
        assert ATRStopLossPolicy().name == "atr_stop_loss"

    def test_approves_when_no_position(self) -> None:
        policy = ATRStopLossPolicy(n_atr=2.0)
        ctx = _ctx(atr={"SSE:600036": 1.0})
        decision = policy.evaluate(_buy("SSE:600036", 50.0), _snapshot(), ctx)
        assert decision.decision == RiskDecisionType.APPROVED

    def test_approves_when_no_atr_data(self) -> None:
        policy = ATRStopLossPolicy(n_atr=2.0)
        ctx = _ctx(
            positions_data=[{"asset_id": "SSE:600036", "quantity": 1000, "market_value": 50_000.0, "weight": 0.05}],
        )
        decision = policy.evaluate(_buy("SSE:600036", 48.0), _snapshot(), ctx)
        assert decision.decision == RiskDecisionType.APPROVED

    def test_rejects_when_price_below_atr_stop(self) -> None:
        """Avg entry=50, ATR=2, n=2 → stop=46. Price=45 < 46 → REJECTED."""
        policy = ATRStopLossPolicy(n_atr=2.0)
        ctx = _ctx(
            positions_data=[{"asset_id": "SSE:600036", "quantity": 1000, "market_value": 50_000.0, "weight": 0.05}],
            atr={"SSE:600036": 2.0},
        )
        decision = policy.evaluate(_buy("SSE:600036", 45.0), _snapshot(), ctx)
        assert decision.decision == RiskDecisionType.REJECTED

    def test_approves_when_price_above_atr_stop(self) -> None:
        """Avg entry=50, ATR=2, n=2 → stop=46. Price=48 > 46 → APPROVED."""
        policy = ATRStopLossPolicy(n_atr=2.0)
        ctx = _ctx(
            positions_data=[{"asset_id": "SSE:600036", "quantity": 1000, "market_value": 50_000.0, "weight": 0.05}],
            atr={"SSE:600036": 2.0},
        )
        decision = policy.evaluate(_buy("SSE:600036", 48.0), _snapshot(), ctx)
        assert decision.decision == RiskDecisionType.APPROVED

    def test_sells_always_approved(self) -> None:
        policy = ATRStopLossPolicy(n_atr=2.0)
        sell = OrderIntent(
            asset_id="SSE:600036", side="sell",
            requested_qty=Decimal("1000"), limit_price=Decimal("40.0"),
            strategy_id="test",
        )
        ctx = _ctx(
            positions_data=[{"asset_id": "SSE:600036", "quantity": 1000, "market_value": 50_000.0, "weight": 0.05}],
            atr={"SSE:600036": 2.0},
        )
        decision = policy.evaluate(sell, _snapshot(), ctx)
        assert decision.decision == RiskDecisionType.APPROVED
