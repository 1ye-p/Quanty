"""测试 BacktestRunner.get_run_metrics() 方法。"""
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
    dates = [date(2025, 1, 2) + timedelta(days=i) for i in range(5)]
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
                "adj_factor": 1.0, "adj_close": p[a], "is_suspended": False,
                "limit_up": p[a]*1.1, "limit_down": p[a]*0.9,
                "source": "test", "ingestion_id": "test_ingest_001",
            })
    df = pl.DataFrame(rows)
    conn = cat._get_conn()
    conn.register("_price_stage", df.to_arrow())
    conn.execute("INSERT INTO silver_prices_1d SELECT * FROM _price_stage")
    conn.unregister("_price_stage")
    runner = BacktestRunner(cat)
    spec = BacktestRunSpec(
        dataset_version="v1", strategy_id="top2",
        start_date=date(2025, 1, 2), end_date=date(2025, 1, 6),
        top_n=2, initial_cash=Decimal("100000"),
    )
    run_id = runner.run(spec)
    return cat, runner, run_id


class TestGetRunMetrics:
    def test_returns_dict_for_existing_run(self, catalog_with_run) -> None:
        cat, runner, run_id = catalog_with_run
        metrics = runner.get_run_metrics(run_id)
        assert metrics is not None
        assert isinstance(metrics, dict)

    def test_metrics_contains_required_keys(self, catalog_with_run) -> None:
        cat, runner, run_id = catalog_with_run
        metrics = runner.get_run_metrics(run_id)
        required_keys = ["sharpe_ratio", "max_drawdown", "total_return", "annualized_return"]
        for key in required_keys:
            assert key in metrics, f"指标 '{key}' 缺失"

    def test_returns_none_for_nonexistent_run(self, catalog_with_run) -> None:
        cat, runner, run_id = catalog_with_run
        result = runner.get_run_metrics("nonexistent-run-id-12345")
        assert result is None
