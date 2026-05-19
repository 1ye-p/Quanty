"""Tests for Kelly and TargetVol sizers using real historical data."""
import polars as pl
import pytest
from decimal import Decimal
from datetime import date
from cquant.riskguard.sizers.kelly import KellySizer
from cquant.riskguard.sizers.target_vol import TargetVolSizer
from cquant.riskguard.models import SizingContext
from cquant.core.types import SignalFrame


def _make_signals(assets: list[str], strengths: list[float] | None = None) -> SignalFrame:
    n = len(assets)
    if strengths is None:
        strengths = [0.8] * n
    return pl.DataFrame({
        "asset_id": assets,
        "signal_date": [date(2025, 6, 1)] * n,
        "direction": ["long"] * n,
        "strength": strengths,
        "confidence": [0.6] * n,
        "strategy_id": ["test"] * n,
    })


def _make_vol_data(assets: list[str], vols: list[float]) -> pl.DataFrame:
    return pl.DataFrame({
        "asset_id": assets,
        "volatility": vols,
    })


class TestKellyWithRealData:
    def test_kelly_uses_volatility_from_context(self):
        """Kelly with real volatility uses different odds than fallback.

        With real vol, odds = 1 + strength * (1 + vol).
        Higher vol => higher odds => higher Kelly fraction.
        """
        sizer = KellySizer()
        signals = _make_signals(["SH600000", "SZ300001"])

        # With real volatility
        ctx_real = SizingContext(
            as_of_date=date(2025, 6, 1),
            portfolio_nav=Decimal("1000000"),
            universe_ids=["SH600000", "SZ300001"],
            volatility=_make_vol_data(["SH600000", "SZ300001"], [0.30, 0.50]),
        )
        result_real = sizer.target_weights(signals, ctx_real)

        # Without real volatility (fallback)
        ctx_fallback = SizingContext(
            as_of_date=date(2025, 6, 1),
            portfolio_nav=Decimal("1000000"),
            universe_ids=["SH600000", "SZ300001"],
        )
        result_fallback = sizer.target_weights(signals, ctx_fallback)

        # With real vol, odds differ per asset, so weights should differ
        w_real = result_real.weights
        w_fallback = result_fallback.weights

        # Both should have weights
        assert len(w_real) == 2
        assert len(w_fallback) == 2

        # With real vol, higher vol asset gets higher odds => higher Kelly weight
        assert w_real["SZ300001"] > w_real["SH600000"]

        # With fallback, both assets have same vol so weights are equal
        assert w_fallback["SH600000"] == w_fallback["SZ300001"]

        # Real data produces different weights than fallback
        assert w_real != w_fallback

    def test_kelly_fallback_without_volatility(self):
        sizer = KellySizer()
        signals = _make_signals(["SH600000", "SZ300001"])
        ctx = SizingContext(
            as_of_date=date(2025, 6, 1),
            portfolio_nav=Decimal("1000000"),
            universe_ids=["SH600000", "SZ300001"],
        )
        result = sizer.target_weights(signals, ctx)
        assert len(result.weights) == 2
        # Fallback uses same odds for both => equal weights
        assert result.weights["SH600000"] == result.weights["SZ300001"]


class TestTargetVolWithRealData:
    def test_target_vol_uses_real_volatility(self):
        """TargetVol with real volatility uses 1/vol weighting.

        Lower volatility assets get larger positions (inverse vol weighting).
        """
        # Use higher max_position_pct to avoid capping
        sizer = TargetVolSizer(target_volatility=0.15, max_position_pct=0.80)
        signals = _make_signals(["SH600000", "SZ300001"])

        # With real volatility: SH600000=0.30, SZ300001=0.50
        ctx_real = SizingContext(
            as_of_date=date(2025, 6, 1),
            portfolio_nav=Decimal("1000000"),
            universe_ids=["SH600000", "SZ300001"],
            volatility=_make_vol_data(["SH600000", "SZ300001"], [0.30, 0.50]),
        )
        result_real = sizer.target_weights(signals, ctx_real)
        w_real = result_real.weights

        # With fallback (no volatility data)
        ctx_fallback = SizingContext(
            as_of_date=date(2025, 6, 1),
            portfolio_nav=Decimal("1000000"),
            universe_ids=["SH600000", "SZ300001"],
        )
        result_fallback = sizer.target_weights(signals, ctx_fallback)
        w_fallback = result_fallback.weights

        # Both should produce weights
        assert len(w_real) == 2
        assert len(w_fallback) == 2

        # With real vol, lower vol (SH600000) gets more weight
        # inv_vol for SH600000 = 1/0.30 = 3.33
        # inv_vol for SZ300001 = 1/0.50 = 2.00
        # Ratio: SH600000 should get 5/3 the weight of SZ300001
        assert w_real["SH600000"] > w_real["SZ300001"]

        # Real data produces different weights than fallback
        assert w_real != w_fallback

    def test_target_vol_fallback_without_data(self):
        sizer = TargetVolSizer(target_volatility=0.15)
        signals = _make_signals(["SH600000", "SZ300001"])
        ctx = SizingContext(
            as_of_date=date(2025, 6, 1),
            portfolio_nav=Decimal("1000000"),
            universe_ids=["SH600000", "SZ300001"],
        )
        result = sizer.target_weights(signals, ctx)
        assert len(result.weights) == 2
        # Fallback: same strength => same proxy vol => equal weights
        assert result.weights["SH600000"] == result.weights["SZ300001"]
