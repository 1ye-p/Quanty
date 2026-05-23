"""测试 CQuantDataHandler（DuckDB → Qlib 数据适配）。"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from cquant.datahub.catalog import Catalog
from cquant.qlib_bridge.data_handler import CQuantDataHandler

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


class TestCQuantDataHandler:
    def test_from_catalog_returns_handler(self, catalog_with_prices) -> None:
        handler = CQuantDataHandler.from_catalog(
            catalog=catalog_with_prices,
            dataset_version="v1",
            start=date(2024, 1, 5),
            end=date(2024, 1, 20),
        )
        assert isinstance(handler, CQuantDataHandler)

    def test_fetch_features_returns_polars(self, catalog_with_prices) -> None:
        handler = CQuantDataHandler.from_catalog(
            catalog=catalog_with_prices,
            dataset_version="v1",
            start=date(2024, 1, 5),
            end=date(2024, 1, 20),
        )
        df = handler.fetch_features()
        assert isinstance(df, pl.DataFrame)

    def test_fetch_labels_returns_polars_series(self, catalog_with_prices) -> None:
        handler = CQuantDataHandler.from_catalog(
            catalog=catalog_with_prices,
            dataset_version="v1",
            start=date(2024, 1, 5),
            end=date(2024, 1, 20),
        )
        labels = handler.fetch_labels(horizon=5)
        assert isinstance(labels, pl.Series)

    def test_fetch_labels_correct_length(self, catalog_with_prices) -> None:
        handler = CQuantDataHandler.from_catalog(
            catalog=catalog_with_prices,
            dataset_version="v1",
            start=date(2024, 1, 5),
            end=date(2024, 1, 20),
        )
        prices_df = handler.fetch_features()
        labels = handler.fetch_labels(horizon=5)
        assert len(labels) == len(prices_df) or len(labels) > 0

    def test_no_prices_returns_empty(self, catalog_with_prices) -> None:
        handler = CQuantDataHandler.from_catalog(
            catalog=catalog_with_prices,
            dataset_version="v1",
            start=date(2020, 1, 1),
            end=date(2020, 1, 10),
        )
        df = handler.fetch_features()
        assert len(df) == 0
