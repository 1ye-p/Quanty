"""Tests for CovarianceEstimator."""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import polars as pl
import pytest

from cquant.portfolio_opt.covariance import CovarianceEstimator


def _make_prices(n_days: int = 100, n_assets: int = 3, seed: int = 42) -> pl.DataFrame:
    rng = np.random.default_rng(seed)
    dates = [date(2024, 1, 1) + timedelta(days=i) for i in range(n_days)]
    assets = [f"A{i}" for i in range(n_assets)]
    rows = []
    price = {a: 100.0 for a in assets}
    for d in dates:
        for a in assets:
            price[a] *= 1 + rng.normal(0, 0.01)
            rows.append({"asset_id": a, "trade_date": d, "close": price[a]})
    return pl.DataFrame(rows)


class TestHistoricalCovariance:
    def test_returns_dict_with_correct_assets(self) -> None:
        prices = _make_prices(n_assets=3)
        est = CovarianceEstimator(method="historical")
        cov = est.estimate(prices)
        assert set(cov.keys()) == {"A0", "A1", "A2"}
        for a in cov:
            assert set(cov[a].keys()) == {"A0", "A1", "A2"}

    def test_diagonal_is_positive(self) -> None:
        prices = _make_prices(n_assets=3)
        est = CovarianceEstimator(method="historical")
        cov = est.estimate(prices)
        for a in cov:
            assert cov[a][a] > 0

    def test_matrix_is_symmetric(self) -> None:
        prices = _make_prices(n_assets=3)
        est = CovarianceEstimator(method="historical")
        cov = est.estimate(prices)
        for a in cov:
            for b in cov:
                assert cov[a][b] == pytest.approx(cov[b][a], rel=1e-6)

    def test_as_of_date_filters_data(self) -> None:
        prices = _make_prices(n_days=100)
        est = CovarianceEstimator(method="historical")
        cov_all = est.estimate(prices)
        cov_early = est.estimate(prices, as_of_date=date(2024, 2, 1))
        assert cov_all["A0"]["A0"] != cov_early["A0"]["A0"]

    def test_single_asset_returns_scalar(self) -> None:
        prices = _make_prices(n_assets=1)
        est = CovarianceEstimator(method="historical")
        cov = est.estimate(prices)
        assert "A0" in cov
        assert cov["A0"]["A0"] > 0


class TestEWMACovariance:
    def test_returns_valid_matrix(self) -> None:
        prices = _make_prices(n_assets=2)
        est = CovarianceEstimator(method="ewma", halflife=21)
        cov = est.estimate(prices)
        assert set(cov.keys()) == {"A0", "A1"}
        assert cov["A0"]["A0"] > 0

    def test_symmetric(self) -> None:
        prices = _make_prices(n_assets=3)
        est = CovarianceEstimator(method="ewma")
        cov = est.estimate(prices)
        for a in cov:
            for b in cov:
                assert cov[a][b] == pytest.approx(cov[b][a], rel=1e-4)


class TestLedoitWolfCovariance:
    def test_returns_valid_matrix(self) -> None:
        prices = _make_prices(n_assets=3)
        est = CovarianceEstimator(method="ledoit_wolf")
        cov = est.estimate(prices)
        assert set(cov.keys()) == {"A0", "A1", "A2"}
        assert cov["A0"]["A0"] > 0

    def test_positive_definite(self) -> None:
        prices = _make_prices(n_assets=3)
        est = CovarianceEstimator(method="ledoit_wolf")
        cov = est.estimate(prices)
        assets = sorted(cov.keys())
        n = len(assets)
        sigma = np.array([[cov[a][b] for b in assets] for a in assets])
        eigenvalues = np.linalg.eigvalsh(sigma)
        assert all(e >= -1e-10 for e in eigenvalues)


class TestCovarianceUsableByMVO:
    def test_covariance_feeds_mvo(self) -> None:
        prices = _make_prices(n_assets=3)
        est = CovarianceEstimator(method="historical")
        cov = est.estimate(prices)

        from cquant.portfolio_opt.mean_variance import MeanVarianceOptimizer
        assets = sorted(cov.keys())
        expected_returns = {a: 0.10 for a in assets}
        optimizer = MeanVarianceOptimizer()
        result = optimizer.optimize(expected_returns=expected_returns, covariance=cov)
        assert sum(result.weights.values()) == pytest.approx(1.0, abs=0.05)
