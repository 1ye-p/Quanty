"""Tests for portfolio snapshot accuracy improvements."""
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

_FSV = "test_fsv_v1"


@pytest.fixture()
def catalog(tmp_path):
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
                "adj_factor": 1.0, "adj_close": p[a], "is_suspended": False, "source": "test",
            })
    df = pl.DataFrame(rows)
    conn = cat._get_conn()
    conn.register("_price_stage", df.to_arrow())
    conn.execute("""
        INSERT OR REPLACE INTO silver_prices_1d
            (asset_id, trade_date, open, high, low, close, volume, amount,
             adj_factor, adj_close, is_suspended, source)
        SELECT asset_id, trade_date, open, high, low, close, volume, amount,
               adj_factor, adj_close, is_suspended, source
        FROM _price_stage
    """)
    conn.unregister("_price_stage")

    # Insert factor data so the strategy can generate signals
    factor_rows = []
    for i, d in enumerate(dates):
        for j, a in enumerate(assets):
            factor_rows.append({
                "feature_set_version": _FSV,
                "factor_name": "ret_20d",
                "trade_date": d,
                "asset_id": a,
                "value": float(j * 0.01 + i * 0.001),
            })
    fdf = pl.DataFrame(factor_rows)
    conn.register("_factor_stage", fdf.to_arrow())
    conn.execute("""
        INSERT OR REPLACE INTO gold_factor_values
            (feature_set_version, factor_name, trade_date, asset_id, value)
        SELECT feature_set_version, factor_name, trade_date, asset_id, value
        FROM _factor_stage
    """)
    conn.unregister("_factor_stage")

    return cat


class TestPortfolioSnapshotAccuracy:
    def test_gross_exposure_within_valid_range(self, catalog: Catalog) -> None:
        runner = BacktestRunner(catalog)
        spec = BacktestRunSpec(
            dataset_version="test_v1",
            strategy_id="top2_test",
            start_date=date(2025, 1, 2),
            end_date=date(2025, 1, 6),
            feature_set_version=_FSV,
            top_n=2,
            initial_cash=Decimal("100000"),
        )
        run_id = runner.run(spec)

        snapshots = catalog.query(
            "SELECT nav, gross_exposure FROM gold_portfolio_snapshots WHERE run_id = ?",
            [run_id],
        )
        assert not snapshots.is_empty()
        for row in snapshots.iter_rows(named=True):
            nav = row["nav"]
            gross = row["gross_exposure"]
            if nav > 0:
                ratio = gross / nav
                # Valid range: 0 to 1.0 (long-only)
                assert 0.0 <= ratio <= 1.0, f"Invalid exposure ratio: {ratio}"

    def test_positions_count_is_non_negative(self, catalog: Catalog) -> None:
        runner = BacktestRunner(catalog)
        spec = BacktestRunSpec(
            dataset_version="test_v1",
            strategy_id="top2_test",
            start_date=date(2025, 1, 2),
            end_date=date(2025, 1, 6),
            feature_set_version=_FSV,
            top_n=2,
            initial_cash=Decimal("100000"),
        )
        run_id = runner.run(spec)

        snapshots = catalog.query(
            "SELECT positions_count FROM gold_portfolio_snapshots WHERE run_id = ?",
            [run_id],
        )
        counts = snapshots["positions_count"].to_list()
        assert all(c >= 0 for c in counts)
