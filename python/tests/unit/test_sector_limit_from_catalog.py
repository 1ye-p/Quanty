"""Tests for SectorLimitPolicy.from_catalog() classmethod."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cquant.datahub.catalog import Catalog
from cquant.riskguard.policies.sector_limit import SectorLimitPolicy

_REPO_ROOT = __import__("pathlib").Path(__file__).resolve().parents[3]


@pytest.fixture()
def catalog_with_assets(tmp_path):
    db_file = tmp_path / "test.duckdb"
    cat = Catalog(db_path=db_file, repo_root=_REPO_ROOT)
    cat.initialize()

    cat._get_conn().execute("""
        INSERT INTO silver_assets
            (asset_id, symbol, exchange, asset_class, currency, effective_from, industry, sector)
        VALUES
            ('SSE:600036', '600036', 'SSE', 'equity', 'CNY', '2020-01-01', '银行', '金融'),
            ('SSE:000001', '000001', 'SSE', 'equity', 'CNY', '2020-01-01', '银行', '金融'),
            ('SSE:600519', '600519', 'SSE', 'equity', 'CNY', '2020-01-01', '食品饮料', '消费'),
            ('SSE:002594', '002594', 'SSE', 'equity', 'CNY', '2020-01-01', NULL, NULL)
    """)
    return cat


class TestFromCatalog:
    def test_builds_sector_map_from_silver_assets(self, catalog_with_assets) -> None:
        policy = SectorLimitPolicy.from_catalog(catalog_with_assets)
        assert policy._sector_map.get("SSE:600036") == "银行"
        assert policy._sector_map.get("SSE:600519") == "食品饮料"

    def test_excludes_null_industry_assets(self, catalog_with_assets) -> None:
        policy = SectorLimitPolicy.from_catalog(catalog_with_assets)
        assert "SSE:002594" not in policy._sector_map

    def test_uses_provided_max_sector_pct(self, catalog_with_assets) -> None:
        policy = SectorLimitPolicy.from_catalog(catalog_with_assets, max_sector_pct=0.20)
        assert policy._max_pct == pytest.approx(0.20)

    def test_empty_assets_table_gives_empty_map(self, tmp_path) -> None:
        db_file = tmp_path / "empty.duckdb"
        cat = Catalog(db_path=db_file, repo_root=_REPO_ROOT)
        cat.initialize()
        policy = SectorLimitPolicy.from_catalog(cat)
        assert policy._sector_map == {}
