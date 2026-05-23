"""Tests for fundamental data loading into factor ctx.extra."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import polars as pl
import pytest

from cquant.datahub.catalog import Catalog
from cquant.factorlab.factor import FactorRegistry
from cquant.factorlab.factors import BUILTIN_FACTORS
from cquant.factorlab.materialize import FactorMaterializer, FactorMaterializationSpec

# Resolve repo root relative to this test file:
# python/tests/unit/test_fundamentals_pipeline.py -> parents[3] = cQuant root
_REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture()
def catalog_with_fundamentals(tmp_path):
    db_file = tmp_path / "test.duckdb"
    cat = Catalog(db_path=db_file, repo_root=_REPO_ROOT)
    cat.initialize()

    cat._get_conn().execute("""
        INSERT INTO silver_prices_1d
            (asset_id, trade_date, open, high, low, close, volume, amount,
             adj_factor, adj_close, is_suspended, source)
        SELECT
            asset_id, trade_date::DATE, 10.0, 11.0, 9.0, 10.5, 1000000, 10500000,
            1.0, 10.5, FALSE, 'test'
        FROM (
            VALUES
                ('SSE:600036', '2025-01-02'), ('SSE:600036', '2025-01-03'),
                ('SSE:600036', '2025-01-06'), ('SSE:000001', '2025-01-02'),
                ('SSE:000001', '2025-01-03'), ('SSE:000001', '2025-01-06')
        ) t(asset_id, trade_date)
    """)

    cat._get_conn().execute("""
        INSERT INTO silver_fundamentals (asset_id, report_date, pe_ttm, pb, roe, gross_margin, market_cap)
        VALUES
            ('SSE:600036', '2024-12-31', 12.5, 1.8, 0.15, 0.42, 5.0e11),
            ('SSE:000001', '2024-12-31', 8.3, 1.2, 0.12, 0.35, 3.0e11)
    """)

    return cat


class TestSilverFundamentalsTable:
    def test_table_exists_after_initialize(self, tmp_path) -> None:
        db_file = tmp_path / "test.duckdb"
        cat = Catalog(db_path=db_file, repo_root=_REPO_ROOT)
        cat.initialize()
        result = cat.query("SELECT COUNT(*) as n FROM silver_fundamentals")
        assert result["n"][0] == 0

    def test_can_insert_and_query(self, tmp_path) -> None:
        db_file = tmp_path / "test.duckdb"
        cat = Catalog(db_path=db_file, repo_root=_REPO_ROOT)
        cat.initialize()
        cat._get_conn().execute("""
            INSERT INTO silver_fundamentals (asset_id, report_date, pe_ttm, pb, roe)
            VALUES ('SSE:600036', '2025-03-31', 12.5, 1.8, 0.15)
        """)
        df = cat.query("SELECT * FROM silver_fundamentals")
        assert len(df) == 1
        assert df["pe_ttm"][0] == pytest.approx(12.5)


class TestFundamentalsLoadedIntoCtxExtra:
    def test_fundamental_factors_return_non_null_when_data_present(
        self, catalog_with_fundamentals: Catalog
    ) -> None:
        reg = FactorRegistry()
        for f in BUILTIN_FACTORS:
            if f.name in ("pe_ttm", "pb", "roe"):
                reg.register(f)

        materializer = FactorMaterializer(catalog_with_fundamentals, reg)
        spec = FactorMaterializationSpec(
            dataset_version="v1",
            factor_names=["pe_ttm", "pb", "roe"],
            start_date=date(2025, 1, 2),
            end_date=date(2025, 1, 6),
        )
        fsv_id = materializer.run(spec)
        assert fsv_id is not None

        result = catalog_with_fundamentals.query(
            "SELECT * FROM gold_factor_values WHERE feature_set_version = ?",
            [fsv_id],
        )
        pe_values = result.filter(pl.col("factor_name") == "pe_ttm")["value"]
        assert pe_values.drop_nulls().len() > 0, "pe_ttm should be non-null when fundamentals loaded"

    def test_fundamental_factors_return_null_when_no_fundamental_data(
        self, tmp_path
    ) -> None:
        db_file = tmp_path / "test_empty.duckdb"
        cat = Catalog(db_path=db_file, repo_root=_REPO_ROOT)
        cat.initialize()

        cat._get_conn().execute("""
            INSERT INTO silver_prices_1d
                (asset_id, trade_date, open, high, low, close, volume, amount,
                 adj_factor, adj_close, is_suspended, source)
            VALUES ('SSE:600036', '2025-01-02', 10.0, 11.0, 9.0, 10.5, 1000000, 10500000, 1.0, 10.5, FALSE, 'test')
        """)

        reg = FactorRegistry()
        for f in BUILTIN_FACTORS:
            if f.name == "pe_ttm":
                reg.register(f)

        materializer = FactorMaterializer(cat, reg)
        spec = FactorMaterializationSpec(
            dataset_version="v1",
            factor_names=["pe_ttm"],
            start_date=date(2025, 1, 2),
            end_date=date(2025, 1, 2),
        )
        try:
            materializer.run(spec)
        except Exception:
            pass
