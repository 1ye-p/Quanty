"""Tests for BrinsonAttribution integration in AnalysisEngine."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

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
                "open": v, "high": v*1.01, "low": v*0.99,
                "close": v, "volume": 1e6, "amount": v*1e6,
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


class TestAnalysisReportAttributionField:
    def test_analysis_report_has_brinson_attribution_field(self) -> None:
        result = _run_backtest()
        ae = AnalysisEngine()
        report = ae.run(result)
        assert hasattr(report, "brinson_attribution")

    def test_brinson_attribution_is_none_or_brinson_result(self) -> None:
        result = _run_backtest()
        ae = AnalysisEngine()
        report = ae.run(result)
        assert report.brinson_attribution is None or isinstance(report.brinson_attribution, BrinsonResult)

    def test_brinson_result_has_expected_fields_when_present(self) -> None:
        result = _run_backtest()
        ae = AnalysisEngine()
        report = ae.run(result)
        if report.brinson_attribution is not None:
            b = report.brinson_attribution
            assert isinstance(b.total_return, float)
            assert isinstance(b.allocation_effect, float)
            assert isinstance(b.selection_effect, float)
            assert isinstance(b.interaction_effect, float)
