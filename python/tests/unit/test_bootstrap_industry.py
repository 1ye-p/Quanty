"""Tests for enrich_industry_from_lookup."""

from unittest.mock import MagicMock, call

import polars as pl

from cquant.datahub.bootstrap import enrich_industry_from_lookup


def test_enriches_matching_assets():
    """3 assets in lookup match silver_assets → industry updated."""
    catalog = MagicMock()

    # silver_assets has 5 assets
    catalog.query.return_value = pl.DataFrame({
        "asset_id": ["SSE:600000", "SSE:600001", "SZSE:000001", "SZSE:000002", "SZSE:300001"],
    })

    lookup = pl.DataFrame({
        "asset_id": ["SSE:600000", "SZSE:000001", "SZSE:300001"],
        "industry": ["银行", "电子", "医药生物"],
    })

    result = enrich_industry_from_lookup(catalog, lookup)
    assert result == 3

    # Verify staged UPDATE pattern: CREATE TEMP → DELETE → executemany INSERT → UPDATE → DROP
    # Implementation calls catalog.execute / catalog.executemany directly.
    assert catalog.execute.call_count == 4  # CREATE, DELETE, UPDATE, DROP
    assert catalog.executemany.call_count == 1  # INSERT

    # First call: CREATE TEMP TABLE
    create_sql = catalog.execute.call_args_list[0][0][0]
    assert "CREATE TEMP TABLE" in create_sql
    assert "_industry_lookup_stage" in create_sql

    # Second call: DELETE FROM temp table
    delete_sql = catalog.execute.call_args_list[1][0][0]
    assert "DELETE FROM _industry_lookup_stage" in delete_sql

    # Third call: UPDATE silver_assets
    update_sql = catalog.execute.call_args_list[2][0][0]
    assert "UPDATE" in update_sql
    assert "industry" in update_sql
    assert "_industry_lookup_stage" in update_sql

    # Fourth call: DROP temp table
    drop_sql = catalog.execute.call_args_list[3][0][0]
    assert "DROP TABLE" in drop_sql
    assert "_industry_lookup_stage" in drop_sql


def test_empty_lookup_returns_zero():
    """Empty lookup DataFrame → returns 0, no queries made."""
    catalog = MagicMock()
    lookup = pl.DataFrame({"asset_id": [], "industry": []}, schema={"asset_id": pl.Utf8, "industry": pl.Utf8})

    result = enrich_industry_from_lookup(catalog, lookup)
    assert result == 0
    catalog.query.assert_not_called()
    catalog.execute.assert_not_called()


def test_no_matching_assets_returns_zero():
    """Lookup asset_ids don't overlap with silver_assets → returns 0."""
    catalog = MagicMock()

    # silver_assets has some assets
    catalog.query.return_value = pl.DataFrame({
        "asset_id": ["SSE:600000", "SSE:600001"],
    })

    # lookup has completely different asset_ids
    lookup = pl.DataFrame({
        "asset_id": ["SSE:999999", "SZSE:888888"],
        "industry": ["银行", "电子"],
    })

    result = enrich_industry_from_lookup(catalog, lookup)
    assert result == 0
    # No catalog.execute call because nothing matched
    catalog.execute.assert_not_called()
