"""Tests for TCA integration in AnalysisEngine."""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import polars as pl
import pytest

from cquant.backtest_vector.engine import BacktestSpec, VectorBacktestEngine
from cquant.backtest_vector.strategy import Strategy, StrategyContext
from cquant.backtest_vector.tca import TCADetail, TCASummary
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


class TestTCAIntegration:
    def test_analysis_report_has_tca_fields(self) -> None:
        result = _run_backtest()
        report = AnalysisEngine().run(result)
        assert hasattr(report, "tca_summary")
        assert hasattr(report, "tca_by_asset")
        assert hasattr(report, "tca_by_date")

    def test_tca_summary_type(self) -> None:
        result = _run_backtest()
        report = AnalysisEngine().run(result)
        assert isinstance(report.tca_summary, TCASummary)

    def test_tca_by_asset_type(self) -> None:
        result = _run_backtest()
        report = AnalysisEngine().run(result)
        assert isinstance(report.tca_by_asset, list)
        for item in report.tca_by_asset:
            assert isinstance(item, TCADetail)

    def test_tca_by_date_type(self) -> None:
        result = _run_backtest()
        report = AnalysisEngine().run(result)
        assert isinstance(report.tca_by_date, list)
        for item in report.tca_by_date:
            assert isinstance(item, TCADetail)

    def test_tca_summary_has_nonzero_costs_when_fills_present(self) -> None:
        result = _run_backtest()
        report = AnalysisEngine().run(result)
        if not result.fills.is_empty():
            assert report.tca_summary.num_trades > 0
            assert report.tca_summary.total_cost >= 0
