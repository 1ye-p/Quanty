"""Tests for IR/TE/Alpha persistence in backtest run artifacts."""
from __future__ import annotations

import glob
import json
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
def catalog(tmp_path):
    cat = Catalog(db_path=tmp_path / "test.duckdb", repo_root=_REPO_ROOT)
    cat.initialize()
    rng = np.random.default_rng(42)
    dates = [date(2025, 1, 2) + timedelta(days=i) for i in range(5)]
    assets = ["SSE:600036", "SSE:000001", "BM:CSI300"]
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
    return cat


class TestMetricsPersistence:
    def test_metrics_json_contains_ir_fields(self, catalog) -> None:
        runner = BacktestRunner(catalog)
        spec = BacktestRunSpec(
            dataset_version="test_v1",
            strategy_id="top2",
            start_date=date(2025, 1, 2),
            end_date=date(2025, 1, 6),
            top_n=2,
            initial_cash=Decimal("100000"),
            benchmark_asset_id="BM:CSI300",
        )
        runner.run(spec)

        artifacts = glob.glob("data/backtest_artifacts/*.json")
        assert len(artifacts) >= 1
        latest = max(artifacts, key=lambda p: Path(p).stat().st_mtime)
        data = json.loads(Path(latest).read_text())

        assert "information_ratio" in data
        assert "tracking_error" in data
        assert "alpha" in data

    def test_ir_value_is_number_or_none(self, catalog) -> None:
        runner = BacktestRunner(catalog)
        spec = BacktestRunSpec(
            dataset_version="test_v1",
            strategy_id="top2",
            start_date=date(2025, 1, 2),
            end_date=date(2025, 1, 6),
            top_n=2,
            initial_cash=Decimal("100000"),
            benchmark_asset_id="BM:CSI300",
        )
        runner.run(spec)

        artifacts = glob.glob("data/backtest_artifacts/*.json")
        latest = max(artifacts, key=lambda p: Path(p).stat().st_mtime)
        data = json.loads(Path(latest).read_text())

        ir = data["information_ratio"]
        assert ir is None or isinstance(ir, (int, float))
