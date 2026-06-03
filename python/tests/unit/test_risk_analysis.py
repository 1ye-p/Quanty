"""Tests for advanced risk analysis functions."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from cquant.backtest_vector.risk_analysis import (
    compute_correlation_matrix,
    compute_factor_exposures,
    run_stress_test,
    compute_risk_contribution,
)


class TestCorrelationMatrix:
    """Test compute_correlation_matrix."""

    def _make_price_df(self, n_days: int = 100, n_assets: int = 3) -> pd.DataFrame:
        """Create synthetic price data."""
        np.random.seed(42)
        dates = pd.date_range("2024-01-01", periods=n_days, freq="B")
        assets = [f"SH{600000 + i}" for i in range(n_assets)]

        rows = []
        for asset in assets:
            prices = 100 * np.cumprod(1 + np.random.normal(0.001, 0.02, n_days))
            for date, price in zip(dates, prices):
                rows.append({"trade_date": date, "asset_id": asset, "close": price})

        return pd.DataFrame(rows)

    def test_basic_correlation(self):
        df = self._make_price_df(100, 3)
        result = compute_correlation_matrix(df, window=60)

        assert "matrix" in result
        assert "assets" in result
        assert len(result["assets"]) == 3

        # Diagonal should be 1.0
        for asset in result["assets"]:
            assert abs(result["matrix"][asset][asset] - 1.0) < 1e-10

    def test_symmetry(self):
        df = self._make_price_df(100, 3)
        result = compute_correlation_matrix(df, window=60)

        assets = result["assets"]
        for a in assets:
            for b in assets:
                assert result["matrix"][a][b] == pytest.approx(result["matrix"][b][a], abs=1e-10)

    def test_range(self):
        df = self._make_price_df(100, 5)
        result = compute_correlation_matrix(df, window=60)

        for a in result["assets"]:
            for b in result["assets"]:
                val = result["matrix"][a][b]
                if val is not None:
                    assert -1.0 <= val <= 1.0

    def test_insufficient_data(self):
        df = self._make_price_df(2, 2)
        result = compute_correlation_matrix(df, window=60)

        assert result["assets"] == []
        assert result["matrix"] == {}

    def test_window_parameter(self):
        df = self._make_price_df(100, 3)
        result = compute_correlation_matrix(df, window=20)
        assert result["window"] == 20


class TestStressTest:
    """Test run_stress_test."""

    def test_basic_stress_test(self):
        np.random.seed(42)
        returns = np.random.normal(0.001, 0.02, 252)
        result = run_stress_test(returns)

        assert "scenarios" in result
        assert len(result["scenarios"]) == 6

        # Check scenario names
        names = [s["name"] for s in result["scenarios"]]
        assert "市场崩盘 (-20%)" in names
        assert "波动率飙升 (3x)" in names
        assert "流动性危机" in names

    def test_empty_returns(self):
        result = run_stress_test(np.array([]))
        assert result["scenarios"] == []

    def test_with_nav_series(self):
        np.random.seed(42)
        returns = np.random.normal(0.001, 0.02, 252)
        nav = np.cumprod(1 + returns)
        result = run_stress_test(returns, nav_series=nav)

        # Last scenario should be historical max drawdown
        dd_scenario = result["scenarios"][-1]
        assert dd_scenario["name"] == "历史最大回撤"
        assert dd_scenario["impact"] < 0

    def test_impact_values(self):
        np.random.seed(42)
        returns = np.random.normal(0.001, 0.02, 252)
        result = run_stress_test(returns)

        # Market crash should be -20%
        assert result["scenarios"][0]["impact"] == pytest.approx(-0.20, abs=1e-10)

        # Volatility spike should be negative
        assert result["scenarios"][1]["impact"] < 0


class TestRiskContribution:
    """Test compute_risk_contribution."""

    def _make_price_df(self, n_days: int = 100, n_assets: int = 3) -> pd.DataFrame:
        """Create synthetic price data."""
        np.random.seed(42)
        dates = pd.date_range("2024-01-01", periods=n_days, freq="B")
        assets = [f"SH{600000 + i}" for i in range(n_assets)]

        rows = []
        for asset in assets:
            prices = 100 * np.cumprod(1 + np.random.normal(0.001, 0.02, n_days))
            for date, price in zip(dates, prices):
                rows.append({"trade_date": date, "asset_id": asset, "close": price})

        return pd.DataFrame(rows)

    def test_basic_risk_contribution(self):
        df = self._make_price_df(100, 3)
        weights = {"SH600000": 0.4, "SH600001": 0.3, "SH600002": 0.3}
        result = compute_risk_contribution(weights, df, window=60)

        assert "contributions" in result
        assert len(result["contributions"]) == 3

        # Check that pct_of_risk sums to ~1
        total_pct = sum(c["pct_of_risk"] for c in result["contributions"])
        assert total_pct == pytest.approx(1.0, abs=0.01)

    def test_contribution_fields(self):
        df = self._make_price_df(100, 3)
        weights = {"SH600000": 0.5, "SH600001": 0.3, "SH600002": 0.2}
        result = compute_risk_contribution(weights, df, window=60)

        for contrib in result["contributions"]:
            assert "asset_id" in contrib
            assert "weight" in contrib
            assert "marginal_risk" in contrib
            assert "risk_contribution" in contrib
            assert "pct_of_risk" in contrib

    def test_portfolio_volatility(self):
        df = self._make_price_df(100, 3)
        weights = {"SH600000": 0.4, "SH600001": 0.3, "SH600002": 0.3}
        result = compute_risk_contribution(weights, df, window=60)

        assert "portfolio_volatility" in result
        assert result["portfolio_volatility"] > 0

    def test_empty_weights(self):
        df = self._make_price_df(100, 3)
        result = compute_risk_contribution({}, df, window=60)
        assert result["contributions"] == []

    def test_sorted_by_risk(self):
        df = self._make_price_df(100, 3)
        weights = {"SH600000": 0.4, "SH600001": 0.3, "SH600002": 0.3}
        result = compute_risk_contribution(weights, df, window=60)

        # Should be sorted by pct_of_risk descending
        pcts = [c["pct_of_risk"] for c in result["contributions"]]
        assert pcts == sorted(pcts, reverse=True)


class TestComputeFactorExposures:
    """Test compute_factor_exposures function."""

    def _make_price_df(self, days: int, n_assets: int) -> pd.DataFrame:
        np.random.seed(42)
        dates = pd.bdate_range("2024-01-01", periods=days)
        rows = []
        for i in range(n_assets):
            prices = 100 * np.cumprod(1 + np.random.normal(0.0005, 0.02, days))
            for d, p in zip(dates, prices):
                rows.append({"trade_date": d, "asset_id": f"SH60000{i}", "close": float(p)})
        return pd.DataFrame(rows)

    def test_basic_exposures(self):
        df = self._make_price_df(100, 3)
        result = compute_factor_exposures(df, window=20)
        assert "data" in result
        assert "window" in result
        assert "keys" in result
        assert result["window"] == 20
        assert len(result["data"]) > 0
        # Each row should have trade_date and the dynamic keys
        row = result["data"][0]
        assert "trade_date" in row
        for key in result["keys"]:
            assert key in row

    def test_dynamic_key_names(self):
        df = self._make_price_df(100, 3)
        result = compute_factor_exposures(df, window=60)
        assert result["keys"] == ["momentum_60d", "volatility_60d"]
        row = result["data"][0]
        assert "momentum_60d" in row
        assert "volatility_60d" in row

    def test_insufficient_data(self):
        df = self._make_price_df(5, 2)
        result = compute_factor_exposures(df, window=20)
        assert result["data"] == []

    def test_single_asset(self):
        df = self._make_price_df(100, 1)
        result = compute_factor_exposures(df, window=20)
        assert len(result["data"]) > 0
