"""Universe resolver: maps universe IDs to asset_id lists."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cquant.datahub.catalog import Catalog


UNIVERSE_PRESETS: dict[str, dict] = {
    "all": {"type": "none"},
    "sse": {"type": "prefix", "prefix": "SSE:"},
    "szse": {"type": "prefix", "prefix": "SZSE:"},
    "cyb": {"type": "like", "pattern": "SZSE:3%"},
    "kcb": {"type": "like", "pattern": "SSE:688%"},
    "bse": {"type": "like", "pattern": "BSE:%"},
    "idx_sse": {"type": "index", "index_code": "000001"},
    "idx_szse": {"type": "index", "index_code": "399001"},
    "idx_hs300": {"type": "index", "index_code": "000300"},
    "idx_zz500": {"type": "index", "index_code": "000905"},
    "idx_zz1000": {"type": "index", "index_code": "000852"},
    "idx_cyb": {"type": "index", "index_code": "399006"},
    "idx_kcb50": {"type": "index", "index_code": "000688"},
}

INDEX_CONSTITUENTS_DDL = """
CREATE TABLE IF NOT EXISTS meta_index_constituents (
    index_code  VARCHAR NOT NULL,
    asset_id    VARCHAR NOT NULL,
    entry_date  DATE,
    is_current  BOOLEAN DEFAULT TRUE,
    PRIMARY KEY (index_code, asset_id)
);
"""


def resolve_universe(
    catalog: "Catalog", universe_id: str
) -> list[str] | None:
    """Resolve a universe ID to a list of asset_ids.

    Returns None for 'all' (no filtering), empty list for no matches.
    """
    preset = UNIVERSE_PRESETS.get(universe_id)
    if not preset or preset["type"] == "none":
        return None

    if preset["type"] == "prefix":
        df = catalog.query(
            "SELECT DISTINCT asset_id FROM silver_prices_1d "
            "WHERE asset_id LIKE ? AND trade_date >= CURRENT_DATE - INTERVAL '30 days'",
            [f"{preset['prefix']}%"],
        )
        return df["asset_id"].to_list() if not df.is_empty() else []

    if preset["type"] == "like":
        df = catalog.query(
            "SELECT DISTINCT asset_id FROM silver_prices_1d "
            "WHERE asset_id LIKE ? AND trade_date >= CURRENT_DATE - INTERVAL '30 days'",
            [preset["pattern"]],
        )
        return df["asset_id"].to_list() if not df.is_empty() else []

    if preset["type"] == "index":
        try:
            df = catalog.query(
                "SELECT asset_id FROM meta_index_constituents "
                "WHERE index_code = ? AND is_current = TRUE",
                [preset["index_code"]],
            )
            return df["asset_id"].to_list() if not df.is_empty() else []
        except Exception:
            return None

    return None
