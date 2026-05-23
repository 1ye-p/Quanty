"""测试 BacktestRunner 工具方法：list_runs() 和 compute_kelly_win_rates()。"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from cquant.backtest_vector.run import BacktestRunSpec, BacktestRunner
from cquant.datahub.catalog import Catalog

_REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture()
def catalog_with_run(tmp_path):
    cat = Catalog(db_path=tmp_path / "test.duckdb", repo_root=_REPO_ROOT)
    cat.initialize()
    rng = np.random.default_rng(42)
    dates = [date(2025, 1, 2) + timedelta(days=i) for i in range(6)]
    assets = ["SSE:600036", "SSE:000001"]
    rows = []
    p = {a: 50.0 for a in assets}
    for d in dates:
        for a in assets:
            p[a] *= 1 + rng.normal(0.001, 0.01)
            rows.append({
                "asset_id": a, "trade_date": d,
                "open": p[a], "high": p[a]*1.01, "low": p[a]*0.99,
                "close": p[a], "volume": 1e6, "amount": p[a]*1e6,
                "adj_factor": 1.0, "adj_close": p[a], "is_suspended": False, "source": "test",
            })
    df = pl.DataFrame(rows)
    conn = cat._get_conn()
    conn.register("_s", df.to_arrow())
    conn.execute(
        "INSERT OR REPLACE INTO silver_prices_1d "
        "(asset_id, trade_date, open, high, low, close, volume, amount, adj_factor, adj_close, is_suspended, source) "
        "SELECT asset_id, trade_date, open, high, low, close, volume, amount, adj_factor, adj_close, is_suspended, source FROM _s"
    )
    conn.unregister("_s")
    runner = BacktestRunner(cat)
    run_id = runner.run(BacktestRunSpec(
        dataset_version="v1", strategy_id="top2",
        start_date=date(2025, 1, 2), end_date=date(2025, 1, 7),
        top_n=2, initial_cash=Decimal("100000"),
    ))
    return cat, runner, run_id


class TestListRuns:
    def test_list_runs_returns_dataframe(self, catalog_with_run) -> None:
        cat, runner, run_id = catalog_with_run
        df = runner.list_runs()
        assert isinstance(df, pl.DataFrame)

    def test_list_runs_includes_recent_run(self, catalog_with_run) -> None:
        cat, runner, run_id = catalog_with_run
        df = runner.list_runs()
        assert run_id in df["run_id"].to_list()

    def test_list_runs_filter_by_strategy(self, catalog_with_run) -> None:
        cat, runner, run_id = catalog_with_run
        df = runner.list_runs(strategy_id="top2")
        assert len(df) >= 1
        assert all(s == "top2" for s in df["strategy_id"].to_list())

    def test_list_runs_empty_for_nonexistent_strategy(self, catalog_with_run) -> None:
        cat, runner, run_id = catalog_with_run
        df = runner.list_runs(strategy_id="nonexistent_strategy_xyz")
        assert len(df) == 0


class TestComputeKellyWinRates:
    def test_returns_dict(self, catalog_with_run) -> None:
        cat, runner, run_id = catalog_with_run
        result = runner.compute_kelly_win_rates(run_id)
        assert isinstance(result, dict)

    def test_empty_for_nonexistent_run(self, catalog_with_run) -> None:
        cat, runner, run_id = catalog_with_run
        result = runner.compute_kelly_win_rates("nonexistent_run_id")
        assert result == {}
