"""测试 Catalog.get_data_quality_summary() 方法。"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from cquant.datahub.catalog import Catalog

_REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture()
def catalog_with_data(tmp_path):
    cat = Catalog(db_path=tmp_path / "test.duckdb", repo_root=_REPO_ROOT)
    cat.initialize()
    rng = np.random.default_rng(42)
    dates = [date(2025, 1, 2) + timedelta(days=i) for i in range(10)]
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
                "limit_up": None, "limit_down": None,
                "source": "test", "ingestion_id": None,
            })
    df = pl.DataFrame(rows)
    conn = cat._get_conn()
    conn.register("_s", df.to_arrow())
    conn.execute("INSERT INTO silver_prices_1d SELECT * FROM _s")
    conn.unregister("_s")
    return cat


class TestDataQualitySummary:
    def test_returns_dict_with_required_keys(self, catalog_with_data) -> None:
        summary = catalog_with_data.get_data_quality_summary()
        assert isinstance(summary, dict)
        assert "total_rows" in summary
        assert "asset_count" in summary
        assert "date_range" in summary

    def test_total_rows_correct(self, catalog_with_data) -> None:
        summary = catalog_with_data.get_data_quality_summary()
        assert summary["total_rows"] == 10 * 2

    def test_asset_count_correct(self, catalog_with_data) -> None:
        summary = catalog_with_data.get_data_quality_summary()
        assert summary["asset_count"] == 2

    def test_empty_catalog_returns_zeros(self, tmp_path) -> None:
        cat = Catalog(db_path=tmp_path / "empty.duckdb", repo_root=_REPO_ROOT)
        cat.initialize()
        summary = cat.get_data_quality_summary()
        assert summary["total_rows"] == 0
        assert summary["asset_count"] == 0
