"""测试 BacktestResult.to_summary_dict() 方法。"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import polars as pl
import pytest

from cquant.backtest_vector.engine import BacktestSpec, VectorBacktestEngine
from cquant.backtest_vector.strategy import Strategy, StrategyContext


class _FixedStrategy(Strategy):
    @property
    def strategy_id(self) -> str:
        return "fixed"

    def generate_signals(self, ctx: StrategyContext) -> pl.DataFrame:
        return pl.DataFrame({
            "asset_id": ["SSE:600036"],
            "signal_date": [ctx.as_of_date],
            "direction": ["long"],
            "strength": [1.0],
            "confidence": [1.0],
        })


def _make_prices(n: int = 20) -> pl.DataFrame:
    rng = np.random.default_rng(42)
    dates = [date(2025, 1, 2) + timedelta(days=i) for i in range(n)]
    rows = []
    p = 50.0
    for d in dates:
        p *= 1 + rng.normal(0.001, 0.01)
        rows.append({
            "asset_id": "SSE:600036", "trade_date": d,
            "open": p, "high": p*1.01, "low": p*0.99,
            "close": p, "volume": 1e6, "amount": p*1e6,
            "adj_factor": 1.0, "adj_close": p, "is_suspended": False,
        })
    return pl.DataFrame(rows)


class TestBacktestResultSummary:
    def test_to_summary_dict_returns_dict(self) -> None:
        engine = VectorBacktestEngine()
        spec = BacktestSpec(
            strategy=_FixedStrategy(),
            prices=_make_prices(20),
            start_date=date(2025, 1, 5),
            end_date=date(2025, 1, 20),
        )
        result = engine.run(spec)
        summary = result.to_summary_dict()
        assert isinstance(summary, dict)

    def test_summary_contains_required_keys(self) -> None:
        engine = VectorBacktestEngine()
        spec = BacktestSpec(
            strategy=_FixedStrategy(),
            prices=_make_prices(20),
            start_date=date(2025, 1, 5),
            end_date=date(2025, 1, 20),
        )
        result = engine.run(spec)
        summary = result.to_summary_dict()
        required = ["run_id", "strategy_id", "total_return", "sharpe_ratio",
                    "max_drawdown", "trading_days"]
        for key in required:
            assert key in summary, f"'{key}' 缺失"

    def test_summary_run_id_matches(self) -> None:
        engine = VectorBacktestEngine()
        spec = BacktestSpec(
            strategy=_FixedStrategy(),
            prices=_make_prices(20),
            start_date=date(2025, 1, 5),
            end_date=date(2025, 1, 20),
        )
        result = engine.run(spec)
        summary = result.to_summary_dict()
        assert summary["run_id"] == result.run_id
