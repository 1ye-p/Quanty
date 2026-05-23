"""测试 Omega Ratio 和 Tail Ratio 新指标。"""
from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from cquant.backtest_vector.metrics import BacktestMetrics, compute_metrics


def _make_returns(seed: int = 42, n: int = 252) -> pl.Series:
    rng = np.random.default_rng(seed)
    return pl.Series("r", rng.normal(0.0005, 0.01, n))


class TestOmegaRatio:
    def test_omega_ratio_field_exists(self) -> None:
        m = compute_metrics(_make_returns())
        assert hasattr(m, "omega_ratio")

    def test_omega_ratio_positive_drift_strategy(self) -> None:
        r = pl.Series("r", np.full(100, 0.002))
        m = compute_metrics(r)
        assert m.omega_ratio is not None
        assert m.omega_ratio > 1.0

    def test_omega_ratio_negative_drift_strategy(self) -> None:
        r = pl.Series("r", np.full(100, -0.002))
        m = compute_metrics(r)
        assert m.omega_ratio is not None
        assert m.omega_ratio < 1.0


class TestTailRatio:
    def test_tail_ratio_field_exists(self) -> None:
        m = compute_metrics(_make_returns())
        assert hasattr(m, "tail_ratio")

    def test_tail_ratio_is_positive(self) -> None:
        m = compute_metrics(_make_returns())
        assert m.tail_ratio is not None
        assert m.tail_ratio > 0

    def test_tail_ratio_symmetric_normal_approx_one(self) -> None:
        rng = np.random.default_rng(99)
        r = pl.Series("r", rng.normal(0, 0.01, 10000))
        m = compute_metrics(r)
        assert m.tail_ratio == pytest.approx(1.0, abs=0.2)


from datetime import date as _date

from cquant.backtest_vector.metrics import compute_portfolio_turnover, compute_hhi


class TestPortfolioTurnover:
    def test_stable_portfolio_has_zero_turnover(self) -> None:
        positions = pl.DataFrame({
            "trade_date": [_date(2025, 1, 1), _date(2025, 1, 2), _date(2025, 1, 3)] * 2,
            "asset_id": ["A"] * 3 + ["B"] * 3,
            "target_weight": [0.5, 0.5, 0.5, 0.5, 0.5, 0.5],
        })
        t = compute_portfolio_turnover(positions)
        assert t == pytest.approx(0.0, abs=1e-6)

    def test_complete_replacement_has_high_turnover(self) -> None:
        positions = pl.DataFrame({
            "trade_date": [_date(2025, 1, 1), _date(2025, 1, 1),
                           _date(2025, 1, 2), _date(2025, 1, 2)],
            "asset_id": ["A", "B", "A", "B"],
            "target_weight": [1.0, 0.0, 0.0, 1.0],
        })
        t = compute_portfolio_turnover(positions)
        assert t == pytest.approx(1.0, abs=0.01)


class TestHHI:
    def test_equal_weight_10_stocks(self) -> None:
        positions = pl.DataFrame({
            "trade_date": [_date(2025, 1, 1)] * 10,
            "asset_id": [f"A{i}" for i in range(10)],
            "target_weight": [0.1] * 10,
        })
        h = compute_hhi(positions)
        assert h == pytest.approx(0.1, abs=0.001)

    def test_single_stock_hhi_is_one(self) -> None:
        positions = pl.DataFrame({
            "trade_date": [_date(2025, 1, 1)],
            "asset_id": ["A"],
            "target_weight": [1.0],
        })
        h = compute_hhi(positions)
        assert h == pytest.approx(1.0, abs=0.001)
