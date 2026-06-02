"""Unit tests for VectorBacktestEngine optimizer input computation."""
from __future__ import annotations

from datetime import date, timedelta

import polars as pl
import pytest

from cquant.backtest_vector.engine import VectorBacktestEngine


class TestComputeExpectedReturns:
    """Tests for _compute_expected_returns helper."""

    def setup_method(self):
        self.engine = VectorBacktestEngine()

    def _make_signals(self, asset_ids: list[str], strengths: list[float] | None = None) -> pl.DataFrame:
        if strengths is None:
            strengths = [1.0] * len(asset_ids)
        return pl.DataFrame({
            "asset_id": asset_ids,
            "signal_date": [date(2025, 6, 1)] * len(asset_ids),
            "direction": [1] * len(asset_ids),
            "strength": strengths,
            "confidence": [0.8] * len(asset_ids),
        })

    def _make_prices(self, assets: list[str], n_days: int = 100, base_price: float = 10.0) -> pl.DataFrame:
        rows = []
        for aid in assets:
            for d in range(n_days):
                trade_date = date(2025, 1, 1) + timedelta(days=d)
                price = base_price * (1 + 0.001 * d)
                rows.append({"asset_id": aid, "trade_date": trade_date, "close": price})
        return pl.DataFrame(rows)

    def test_ml_predictions_priority(self):
        signals = self._make_signals(["SSE:600036", "SZSE:000858"])
        prices = self._make_prices(["SSE:600036", "SZSE:000858"])
        ml_preds = {"SSE:600036": 0.15, "SZSE:000858": 0.20}
        result = self.engine._compute_expected_returns(signals, prices, date(2025, 4, 1), ml_predictions=ml_preds)
        assert result["SSE:600036"] == pytest.approx(0.15)
        assert result["SZSE:000858"] == pytest.approx(0.20)

    def test_ml_partial_coverage_uses_history_for_rest(self):
        signals = self._make_signals(["SSE:600036", "SZSE:000858"])
        prices = self._make_prices(["SSE:600036", "SZSE:000858"])
        ml_preds = {"SSE:600036": 0.15}
        result = self.engine._compute_expected_returns(signals, prices, date(2025, 4, 1), ml_predictions=ml_preds)
        assert result["SSE:600036"] == pytest.approx(0.15)
        assert "SZSE:000858" in result
        assert result["SZSE:000858"] != 0.15

    def test_historical_returns_computed(self):
        signals = self._make_signals(["SSE:600036"])
        prices = self._make_prices(["SSE:600036"], n_days=100, base_price=10.0)
        result = self.engine._compute_expected_returns(signals, prices, date(2025, 4, 1))
        assert "SSE:600036" in result
        assert result["SSE:600036"] > 0

    def test_short_history_fallback_to_strength(self):
        signals = self._make_signals(["SSE:600036"], strengths=[0.8])
        prices = self._make_prices(["SSE:600036"], n_days=5)
        result = self.engine._compute_expected_returns(signals, prices, date(2025, 1, 6))
        assert result["SSE:600036"] == pytest.approx(0.8 * 0.05)

    def test_missing_asset_in_prices_uses_strength(self):
        signals = self._make_signals(["SSE:600036", "UNKNOWN:999999"], strengths=[1.0, 0.6])
        prices = self._make_prices(["SSE:600036"], n_days=100)
        result = self.engine._compute_expected_returns(signals, prices, date(2025, 4, 1))
        assert "SSE:600036" in result
        assert result["UNKNOWN:999999"] == pytest.approx(0.6 * 0.05)


class TestComputeCovariance:
    """Tests for _compute_covariance helper."""

    def setup_method(self):
        self.engine = VectorBacktestEngine()

    def _make_prices(self, assets: list[str], n_days: int = 200) -> pl.DataFrame:
        import random
        random.seed(42)
        rows = []
        for aid in assets:
            price = 10.0
            for d in range(n_days):
                trade_date = date(2025, 1, 1) + timedelta(days=d)
                price *= (1 + random.gauss(0.0005, 0.02))
                rows.append({"asset_id": aid, "trade_date": trade_date, "close": price})
        return pl.DataFrame(rows)

    def test_covariance_matrix_structure(self):
        prices = self._make_prices(["SSE:600036", "SZSE:000858", "SZSE:000001"])
        cov = self.engine._compute_covariance(["SSE:600036", "SZSE:000858", "SZSE:000001"], prices, date(2025, 7, 1))
        assert len(cov) == 3
        for a in ["SSE:600036", "SZSE:000858", "SZSE:000001"]:
            assert a in cov
            assert len(cov[a]) == 3
            assert cov[a][a] > 0

    def test_covariance_symmetric(self):
        prices = self._make_prices(["SSE:600036", "SZSE:000858"])
        cov = self.engine._compute_covariance(["SSE:600036", "SZSE:000858"], prices, date(2025, 7, 1))
        assert cov["SSE:600036"]["SZSE:000858"] == pytest.approx(cov["SZSE:000858"]["SSE:600036"], rel=1e-10)

    def test_covariance_subset_filtering(self):
        prices = self._make_prices(["SSE:600036", "SZSE:000858", "SZSE:000001"])
        cov = self.engine._compute_covariance(["SSE:600036", "SZSE:000858"], prices, date(2025, 7, 1))
        assert len(cov) == 2
        assert "SZSE:000001" not in cov

    def test_covariance_insufficient_data_returns_diagonal(self):
        prices = self._make_prices(["SSE:600036"], n_days=5)
        cov = self.engine._compute_covariance(["SSE:600036"], prices, date(2025, 1, 6))
        assert "SSE:600036" in cov
        assert cov["SSE:600036"]["SSE:600036"] > 0
