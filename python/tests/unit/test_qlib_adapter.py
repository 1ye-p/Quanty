"""测试 DuckDB → Qlib 数据适配层。"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import polars as pl
import pytest

from cquant.datahub.catalog import Catalog
from cquant.factorlab.qlib_adapter import DuckDBToQlibAdapter

_REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture()
def catalog_with_prices(tmp_path):
    cat = Catalog(db_path=tmp_path / "test.duckdb", repo_root=_REPO_ROOT)
    cat.initialize()
    rng = np.random.default_rng(42)
    dates = [date(2024, 1, 2) + timedelta(days=i) for i in range(30)]
    assets = ["SSE:600036", "SSE:000001"]
    rows = []
    p = {a: 50.0 for a in assets}
    for d in dates:
        for a in assets:
            p[a] *= 1 + rng.normal(0.001, 0.01)
            rows.append({
                "asset_id": a, "trade_date": d,
                "open": p[a]*0.99, "high": p[a]*1.02, "low": p[a]*0.97,
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
    return cat


class TestDuckDBToQlibAdapter:
    def test_load_prices_returns_dataframe(self, catalog_with_prices) -> None:
        adapter = DuckDBToQlibAdapter(catalog_with_prices)
        df = adapter.load_prices(start_date=date(2024, 1, 5), end_date=date(2024, 1, 20))
        assert isinstance(df, pd.DataFrame)

    def test_load_prices_has_multiindex(self, catalog_with_prices) -> None:
        adapter = DuckDBToQlibAdapter(catalog_with_prices)
        df = adapter.load_prices(start_date=date(2024, 1, 5), end_date=date(2024, 1, 20))
        assert isinstance(df.index, pd.MultiIndex)
        assert df.index.names == ["datetime", "instrument"]

    def test_load_prices_has_qlib_column_names(self, catalog_with_prices) -> None:
        adapter = DuckDBToQlibAdapter(catalog_with_prices)
        df = adapter.load_prices(start_date=date(2024, 1, 5), end_date=date(2024, 1, 20))
        for col in ["$open", "$high", "$low", "$close", "$volume"]:
            assert col in df.columns, f"缺少列 '{col}'"

    def test_load_prices_no_data_returns_empty(self, catalog_with_prices) -> None:
        adapter = DuckDBToQlibAdapter(catalog_with_prices)
        df = adapter.load_prices(start_date=date(2020, 1, 1), end_date=date(2020, 1, 10))
        assert len(df) == 0
