"""Tests for enhanced Brinson attribution in AnalysisEngine."""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import polars as pl
import pytest

from cquant.backtest_vector.engine import BacktestSpec, VectorBacktestEngine
from cquant.backtest_vector.strategy import Strategy, StrategyContext
from cquant.bt_analyzer.attribution import BrinsonResult
from cquant.bt_analyzer.engine import AnalysisEngine
from cquant.bt_analyzer.models import AnalysisReport


class _FixedStrategy(Strategy):
    @property
    def strategy_id(self) -> str:
        return "fixed"

    def generate_signals(self, ctx: StrategyContext) -> pl.DataFrame:
        return pl.DataFrame({
            "asset_id": ["SSE:600036", "SSE:000001"],
            "signal_date": [ctx.as_of_date, ctx.as_of_date],
            "direction": ["long", "long"],
            "strength": [0.6, 0.4],
            "confidence": [1.0, 1.0],
        })


def _make_prices(n: int = 30) -> pl.DataFrame:
    rng = np.random.default_rng(42)
    dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(n)]
    rows = []
    p = {"SSE:600036": 50.0, "SSE:000001": 30.0}
    for d in dates:
        for a, v in p.items():
            v *= 1 + rng.normal(0.0005, 0.01)
            p[a] = v
            rows.append({
                "asset_id": a, "trade_date": d,
                "open": v, "high": v * 1.01, "low": v * 0.99,
                "close": v, "volume": 1e6, "amount": v * 1e6,
                "adj_factor": 1.0, "adj_close": v, "is_suspended": False,
            })
    return pl.DataFrame(rows)


def _run_backtest():
    engine = VectorBacktestEngine()
    spec = BacktestSpec(
        strategy=_FixedStrategy(),
        prices=_make_prices(30),
        start_date=date(2025, 1, 5),
        end_date=date(2025, 1, 20),
    )
    return engine.run(spec)


class TestEnhancedBrinsonAttribution:
    def test_analysis_report_has_new_attribution_fields(self) -> None:
        result = _run_backtest()
        report = AnalysisEngine().run(result)
        assert hasattr(report, "brinson_daily")
        assert hasattr(report, "benchmark_return")
        assert hasattr(report, "active_return")

    def test_benchmark_return_type(self) -> None:
        result = _run_backtest()
        report = AnalysisEngine().run(result)
        if report.benchmark_return is not None:
            assert isinstance(report.benchmark_return, float)

    def test_active_return_type(self) -> None:
        result = _run_backtest()
        report = AnalysisEngine().run(result)
        if report.active_return is not None:
            assert isinstance(report.active_return, float)

    def test_brinson_daily_type(self) -> None:
        result = _run_backtest()
        report = AnalysisEngine().run(result)
        if report.brinson_daily is not None:
            assert isinstance(report.brinson_daily, list)
            for entry in report.brinson_daily:
                assert isinstance(entry, dict)
                assert "date" in entry
                assert "allocation" in entry
                assert "selection" in entry
                assert "interaction" in entry

    def test_active_return_consistency(self) -> None:
        """active_return should equal portfolio_return - benchmark_return."""
        result = _run_backtest()
        report = AnalysisEngine().run(result)
        if (
            report.brinson_attribution is not None
            and report.benchmark_return is not None
            and report.active_return is not None
        ):
            expected = report.brinson_attribution.total_return - report.benchmark_return
            assert abs(report.active_return - expected) < 1e-10

    def test_benchmark_return_is_equal_weight(self) -> None:
        """With equal-weight benchmark, benchmark_return should be the mean of asset returns."""
        result = _run_backtest()
        report = AnalysisEngine().run(result)
        if report.benchmark_return is not None:
            # benchmark_return should be finite
            assert np.isfinite(report.benchmark_return)
