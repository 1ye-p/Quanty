"""测试 BacktestRunner.run_engine() 自定义策略支持。"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from cquant.backtest_vector.run import BacktestRunner
from cquant.backtest_vector.strategy import Strategy, StrategyContext
from cquant.datahub.catalog import Catalog

_REPO_ROOT = Path(__file__).resolve().parents[3]


class _AlwaysBuyStrategy(Strategy):
    @property
    def strategy_id(self) -> str:
        return "always_buy_test"

    def generate_signals(self, ctx: StrategyContext) -> pl.DataFrame:
        return pl.DataFrame({
            "asset_id": ["SSE:600036"],
            "signal_date": [ctx.as_of_date],
            "direction": ["long"],
            "strength": [1.0],
            "confidence": [1.0],
        })


@pytest.fixture()
def catalog_with_prices(tmp_path):
    cat = Catalog(db_path=tmp_path / "test.duckdb", repo_root=_REPO_ROOT)
    cat.initialize()
    rng = np.random.default_rng(42)
    dates = [date(2025, 1, 2) + timedelta(days=i) for i in range(8)]
    rows = []
    p = 50.0
    for d in dates:
        p *= 1 + rng.normal(0.001, 0.01)
        rows.append({
            "asset_id": "SSE:600036", "trade_date": d,
            "open": p, "high": p*1.01, "low": p*0.99,
            "close": p, "volume": 1e6, "amount": p*1e6,
            "adj_factor": 1.0, "adj_close": p, "is_suspended": False, "source": "test",
        })
    df = pl.DataFrame(rows)
    conn = cat._get_conn()
    conn.register("_s", df.to_arrow())
    conn.execute("""
        INSERT OR REPLACE INTO silver_prices_1d
            (asset_id, trade_date, open, high, low, close, volume, amount,
             adj_factor, adj_close, is_suspended, source)
        SELECT asset_id, trade_date, open, high, low, close, volume, amount,
               adj_factor, adj_close, is_suspended, source
        FROM _s
    """)
    conn.unregister("_s")
    return cat


class TestRunEngineCustomStrategy:
    def test_run_engine_accepts_custom_strategy(self, catalog_with_prices) -> None:
        runner = BacktestRunner(catalog_with_prices)
        run_id = runner.run_engine(
            strategy=_AlwaysBuyStrategy(),
            start_date=date(2025, 1, 3),
            end_date=date(2025, 1, 8),
            initial_cash=Decimal("100000"),
        )
        assert run_id is not None
        assert len(run_id) > 0

    def test_run_engine_persists_to_catalog(self, catalog_with_prices) -> None:
        runner = BacktestRunner(catalog_with_prices)
        run_id = runner.run_engine(
            strategy=_AlwaysBuyStrategy(),
            start_date=date(2025, 1, 3),
            end_date=date(2025, 1, 8),
        )
        rows = catalog_with_prices.query(
            "SELECT status FROM gold_backtest_runs WHERE run_id = ?", [run_id]
        )
        assert not rows.is_empty()
        assert rows["status"][0] == "completed"

    def test_run_engine_strategy_id_from_strategy(self, catalog_with_prices) -> None:
        runner = BacktestRunner(catalog_with_prices)
        run_id = runner.run_engine(
            strategy=_AlwaysBuyStrategy(),
            start_date=date(2025, 1, 3),
            end_date=date(2025, 1, 8),
        )
        rows = catalog_with_prices.query(
            "SELECT strategy_id FROM gold_backtest_runs WHERE run_id = ?", [run_id]
        )
        assert rows["strategy_id"][0] == "always_buy_test"
