"""Tests for Black-Litterman sizer."""
import polars as pl
import pytest
from datetime import date
from decimal import Decimal
from cquant.core.types import TargetWeights
from cquant.riskguard.models import SizingContext
from cquant.riskguard.sizers.black_litterman import BlackLittermanSizer


def _make_signals(assets: list[str]) -> pl.DataFrame:
    return pl.DataFrame({
        "asset_id": assets,
        "signal_date": [date(2025, 6, 1)] * len(assets),
        "direction": ["long"] * len(assets),
        "strength": [1.0] * len(assets),
        "confidence": [1.0] * len(assets),
    })


def _make_ctx(assets: list[str], cap_weights: list[float] | None = None) -> SizingContext:
    n = len(assets)
    if cap_weights is None:
        cap_weights = [1.0 / n] * n

    vol_df = pl.DataFrame({
        "asset_id": assets,
        "volatility": [0.20 / 252**0.5] * n,
    })
    cov_data = {"asset_id": assets}
    for j, a in enumerate(assets):
        cov_data[a] = [0.0] * n
        cov_data[a][j] = (0.20 / 252) ** 2
    cov_df = pl.DataFrame(cov_data)

    return SizingContext(
        as_of_date=date(2025, 6, 1),
        portfolio_nav=Decimal("1000000"),
        universe_ids=assets,
        return_covariance=cov_df,
        volatility=vol_df,
        constraints={"market_cap_weights": dict(zip(assets, cap_weights))},
    )


class TestBlackLittermanSizer:
    def test_name(self):
        sizer = BlackLittermanSizer()
        assert sizer.name == "black_litterman"

    def test_no_views_returns_market_weights(self):
        """With no views, BL should return market-cap weights."""
        assets = ["A", "B", "C"]
        cap_w = [0.5, 0.3, 0.2]
        signals = _make_signals(assets)
        ctx = _make_ctx(assets, cap_w)
        sizer = BlackLittermanSizer()
        result = sizer.target_weights(signals, ctx)
        for a, expected in zip(assets, cap_w):
            assert result.weights.get(a, 0) == pytest.approx(expected, abs=0.05)

    def test_with_view_shifts_weights(self):
        """A view that A outperforms B should increase A's weight."""
        assets = ["A", "B"]
        signals = _make_signals(assets)
        ctx = _make_ctx(assets, [0.5, 0.5])
        sizer = BlackLittermanSizer(
            views=[{"asset": "A", "relative_to": "B", "expected_excess": 0.10}],
        )
        result = sizer.target_weights(signals, ctx)
        assert result.weights.get("A", 0) > result.weights.get("B", 0)

    def test_empty_signals(self):
        sizer = BlackLittermanSizer()
        signals = pl.DataFrame({
            "asset_id": [], "signal_date": [], "direction": [],
            "strength": [], "confidence": [],
        })
        ctx = SizingContext(
            as_of_date=date(2025, 6, 1),
            portfolio_nav=Decimal("1000000"),
            universe_ids=[],
        )
        result = sizer.target_weights(signals, ctx)
        assert result.weights == {}

    def test_fallback_without_covariance(self):
        assets = ["A", "B"]
        signals = _make_signals(assets)
        ctx = SizingContext(
            as_of_date=date(2025, 6, 1),
            portfolio_nav=Decimal("1000000"),
            universe_ids=assets,
        )
        sizer = BlackLittermanSizer()
        result = sizer.target_weights(signals, ctx)
        # Should fall back to equal weight
        for w in result.weights.values():
            assert w == pytest.approx(0.5, abs=0.05)
