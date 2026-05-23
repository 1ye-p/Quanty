"""测试 total_trades 使用真实成交笔数而非交易日数。"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import numpy as np
import polars as pl
import pytest

from cquant.backtest_vector.engine import BacktestSpec, VectorBacktestEngine
from cquant.backtest_vector.strategy import Strategy, StrategyContext


class _EmptyStrategy(Strategy):
    @property
    def strategy_id(self) -> str:
        return "empty"

    def generate_signals(self, ctx: StrategyContext) -> pl.DataFrame:
        return pl.DataFrame(
            schema={
                "asset_id": pl.Utf8, "signal_date": pl.Date,
                "direction": pl.Utf8, "strength": pl.Float64, "confidence": pl.Float64,
            }
        )


def _make_prices(n: int = 15) -> pl.DataFrame:
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


class TestTotalTradesFix:
    def test_empty_strategy_has_zero_total_trades(self) -> None:
        """无信号策略成交笔数应为 0，不应等于交易日数。"""
        engine = VectorBacktestEngine()
        spec = BacktestSpec(
            strategy=_EmptyStrategy(),
            prices=_make_prices(15),
            start_date=date(2025, 1, 3),
            end_date=date(2025, 1, 15),
        )
        result = engine.run(spec)
        assert result.metrics.total_trades == 0
