"""Tests for active management metrics: IR, Tracking Error, Alpha."""
from __future__ import annotations

import math

import numpy as np
import polars as pl
import pytest

from cquant.backtest_vector.metrics import BacktestMetrics, compute_metrics


def _make_returns(n: int = 252, seed: int = 42) -> pl.Series:
    rng = np.random.default_rng(seed)
    return pl.Series("r", rng.normal(0.0005, 0.01, n))


def _make_benchmark(n: int = 252, seed: int = 7) -> pl.Series:
    rng = np.random.default_rng(seed)
    return pl.Series("bm", rng.normal(0.0003, 0.008, n))


class TestBacktestMetricsHasNewFields:
    def test_information_ratio_field_exists(self) -> None:
        m = compute_metrics(_make_returns())
        assert hasattr(m, "information_ratio")
        assert m.information_ratio is None

    def test_tracking_error_field_exists(self) -> None:
        m = compute_metrics(_make_returns())
        assert hasattr(m, "tracking_error")
        assert m.tracking_error is None

    def test_alpha_field_exists(self) -> None:
        m = compute_metrics(_make_returns())
        assert hasattr(m, "alpha")
        assert m.alpha is None


class TestActiveMetricsWithBenchmark:
    def test_tracking_error_is_positive(self) -> None:
        r = _make_returns()
        bm = _make_benchmark()
        m = compute_metrics(r, benchmark_returns=bm)
        assert m.tracking_error is not None
        assert m.tracking_error > 0

    def test_tracking_error_formula(self) -> None:
        r = _make_returns()
        bm = _make_benchmark()
        m = compute_metrics(r, benchmark_returns=bm)
        expected_te = float(
            np.std(r.to_numpy() - bm.to_numpy(), ddof=1) * math.sqrt(252)
        )
        assert m.tracking_error == pytest.approx(expected_te, rel=1e-6)

    def test_information_ratio_is_computed(self) -> None:
        r = _make_returns()
        bm = _make_benchmark()
        m = compute_metrics(r, benchmark_returns=bm)
        assert m.information_ratio is not None
        assert math.isfinite(m.information_ratio)

    def test_alpha_is_computed_when_benchmark_present(self) -> None:
        r = _make_returns()
        bm = _make_benchmark()
        m = compute_metrics(r, benchmark_returns=bm)
        assert m.alpha is not None
        assert math.isfinite(m.alpha)

    def test_consistently_outperforming_strategy_has_positive_ir(self) -> None:
        # Strategy consistently beats benchmark: active returns have variability
        # but a positive mean, so IR should be positive.
        rng = np.random.default_rng(99)
        bm_arr = rng.normal(0.0003, 0.008, 252)
        # Strategy = benchmark + positive alpha + small noise
        r_arr = bm_arr + 0.0005 + rng.normal(0.0, 0.001, 252)
        m = compute_metrics(
            pl.Series("r", r_arr),
            benchmark_returns=pl.Series("bm", bm_arr),
        )
        assert m.information_ratio is not None
        assert m.information_ratio > 0

    def test_same_returns_as_benchmark_has_zero_tracking_error(self) -> None:
        r = _make_returns()
        m = compute_metrics(r, benchmark_returns=r)
        assert m.tracking_error == pytest.approx(0.0, abs=1e-10)
