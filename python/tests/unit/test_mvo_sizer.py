"""Tests for MVO sizer."""
import polars as pl
import pytest
from datetime import date
from decimal import Decimal
from cquant.core.types import TargetWeights
from cquant.riskguard.models import SizingContext
from cquant.riskguard.sizers.mvo import MVOSizer


def _make_signals(assets: list[str]) -> pl.DataFrame:
    return pl.DataFrame({
        "asset_id": assets,
        "signal_date": [date(2025, 6, 1)] * len(assets),
        "direction": ["long"] * len(assets),
        "strength": [1.0] * len(assets),
        "confidence": [1.0] * len(assets),
    })


def _make_ctx(
    assets: list[str],
    expected_returns: list[float] | None = None,
    cov_matrix: list[list[float]] | None = None,
) -> SizingContext:
    n = len(assets)
    if expected_returns is None:
        expected_returns = [0.10 / 252] * n  # ~10% annualized
    if cov_matrix is None:
        # Simple diagonal covariance
        cov_matrix = [[0.0] * n for _ in range(n)]
        for i in range(n):
            cov_matrix[i][i] = (0.20 / 252) ** 2  # ~20% annualized vol

    er_df = pl.DataFrame({"asset_id": assets, "expected_return": expected_returns})
    vol_df = pl.DataFrame({
        "asset_id": assets,
        "volatility": [cov_matrix[i][i] ** 0.5 for i in range(n)],
    })
    # Build covariance DataFrame: asset_id + one column per asset
    cov_data = {"asset_id": assets}
    for j, a in enumerate(assets):
        cov_data[a] = [cov_matrix[i][j] for i in range(n)]
    cov_df = pl.DataFrame(cov_data)

    return SizingContext(
        as_of_date=date(2025, 6, 1),
        portfolio_nav=Decimal("1000000"),
        universe_ids=assets,
        expected_returns=er_df,
        return_covariance=cov_df,
        volatility=vol_df,
    )


class TestMVOSizer:
    def test_name(self):
        sizer = MVOSizer()
        assert sizer.name == "mvo"

    def test_weights_sum_near_one(self):
        assets = ["A", "B", "C"]
        signals = _make_signals(assets)
        ctx = _make_ctx(assets)
        sizer = MVOSizer()
        result = sizer.target_weights(signals, ctx)
        assert isinstance(result, TargetWeights)
        total = sum(result.weights.values())
        assert total == pytest.approx(1.0, abs=0.05)

    def test_all_weights_non_negative(self):
        assets = ["A", "B", "C"]
        signals = _make_signals(assets)
        ctx = _make_ctx(assets)
        sizer = MVOSizer()
        result = sizer.target_weights(signals, ctx)
        for w in result.weights.values():
            assert w >= -1e-9

    def test_higher_return_gets_higher_weight(self):
        assets = ["A", "B"]
        signals = _make_signals(assets)
        # Use large, clearly differentiated expected returns with equal vol
        ctx = _make_ctx(assets, expected_returns=[0.5, 0.01])
        sizer = MVOSizer(risk_aversion=0.1)
        result = sizer.target_weights(signals, ctx)
        assert result.weights.get("A", 0) > result.weights.get("B", 0)

    def test_fallback_when_no_covariance(self):
        """Should fall back to equal weight when covariance is missing."""
        assets = ["A", "B", "C"]
        signals = _make_signals(assets)
        ctx = SizingContext(
            as_of_date=date(2025, 6, 1),
            portfolio_nav=Decimal("1000000"),
            universe_ids=assets,
        )
        sizer = MVOSizer()
        result = sizer.target_weights(signals, ctx)
        # Should be approximately equal weight
        for w in result.weights.values():
            assert w == pytest.approx(1.0 / 3, abs=0.05)

    def test_empty_signals_returns_empty(self):
        sizer = MVOSizer()
        signals = pl.DataFrame({
            "asset_id": [],
            "signal_date": [],
            "direction": [],
            "strength": [],
            "confidence": [],
        })
        ctx = SizingContext(
            as_of_date=date(2025, 6, 1),
            portfolio_nav=Decimal("1000000"),
            universe_ids=[],
        )
        result = sizer.target_weights(signals, ctx)
        assert result.weights == {}
