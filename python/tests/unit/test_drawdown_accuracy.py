"""测试回测引擎中 drawdown 计算准确性。"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import polars as pl
import pytest

from cquant.backtest_vector.engine import BacktestSpec, VectorBacktestEngine
from cquant.backtest_vector.strategy import Strategy, StrategyContext
from cquant.riskguard.policies.drawdown_breaker import DrawdownBreakerPolicy


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


def _make_prices(trend: float = 0.0, n: int = 20) -> pl.DataFrame:
    dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(n)]
    rows = []
    p = 100.0
    for i, d in enumerate(dates):
        p *= 1 + trend
        rows.append({
            "asset_id": "SSE:600036", "trade_date": d,
            "open": p, "high": p*1.01, "low": p*0.99,
            "close": p, "volume": 1e6, "amount": p*1e6,
            "adj_factor": 1.0, "adj_close": p, "is_suspended": False,
        })
    return pl.DataFrame(rows)


class TestRiskSnapshotDrawdown:
    def test_drawdown_breaker_with_declining_prices_no_crash(self) -> None:
        """价格持续下跌时，带 DrawdownBreakerPolicy 的回测不崩溃。"""
        policy = DrawdownBreakerPolicy(max_drawdown=-0.05)
        engine = VectorBacktestEngine()
        spec = BacktestSpec(
            strategy=_FixedStrategy(),
            prices=_make_prices(trend=-0.02, n=20),
            start_date=date(2025, 1, 3),
            end_date=date(2025, 1, 18),
            risk_policies=[policy],
        )
        result = engine.run(spec)
        assert result.error is None

    def test_engine_with_risk_policy_produces_result(self) -> None:
        """带风控策略的引擎正常产出结果。"""
        engine = VectorBacktestEngine()
        spec = BacktestSpec(
            strategy=_FixedStrategy(),
            prices=_make_prices(trend=0.005, n=20),
            start_date=date(2025, 1, 3),
            end_date=date(2025, 1, 15),
            risk_policies=[DrawdownBreakerPolicy(max_drawdown=-0.10)],
        )
        result = engine.run(spec)
        assert result.error is None
        assert result.metrics.max_drawdown <= 0
