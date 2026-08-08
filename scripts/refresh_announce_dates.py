#!/usr/bin/env python3
"""refresh_announce_dates.py — Overwrite tier-estimated announce_date with real f_ann_date.

The migrate_fundamentals_pit.py script estimates announce_date using report-period
tiers (120/90/45 days).  This script replaces those estimates with the actual
`f_ann_date` field from Tushare's `fina_indicator` API.

Idempotent: only processes rows WHERE announce_date IS NOT NULL (i.e. rows that
already have a tier-estimated value).
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

# Ensure project root is on sys.path so ``cquant`` is importable.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def _to_ts_code(asset_id: str) -> str:
    """Convert cQuant asset_id (e.g. 'SSE:600036') to Tushare code ('600036.SH')."""
    if ":" not in asset_id:
        return asset_id
    exchange, symbol = asset_id.split(":", 1)
    suffix = {"SSE": "SH", "SZSE": "SZ"}.get(exchange, exchange)
    return f"{symbol}.{suffix}"


def _to_period(report_date) -> str:
    """Convert a report_date (datetime / date / str) to Tushare period format 'YYYYMMDD'.

    Accepts datetime objects (from DuckDB query results) or ISO-format strings
    like '2024-12-31'.
    """
    if hasattr(report_date, "strftime"):
        return report_date.strftime("%Y%m%d")
    # Fallback: strip hyphens from string representation.
    return str(report_date).replace("-", "")[:8]


def refresh(catalog, connector) -> int:
    """Replace tier-estimated announce_date with real f_ann_date from tushare."""
    rows = catalog.query(
        "SELECT DISTINCT asset_id, report_date FROM silver_fundamentals "
        "WHERE announce_date IS NOT NULL"
    )

    if len(rows) == 0:
        logger.info("No rows with announce_date to refresh — skipping.")
        return 0

    total = len(rows)
    updated = 0
    errors = 0
    logger.info("Refreshing announce_date for %d distinct (asset_id, report_date) pairs ...", total)

    # Collect all updates first, then apply in a single transaction
    updates: list[tuple] = []

    for i, row in enumerate(rows.to_dicts(), 1):
        asset_id: str = row["asset_id"]
        report_date = row["report_date"]

        ts_code = _to_ts_code(asset_id)
        period = _to_period(report_date)

        try:
            records = connector.fetch_fundamentals(ts_code, period)
        except Exception as exc:
            logger.warning("Failed to fetch %s period=%s: %s", ts_code, period, exc)
            errors += 1
            continue

        for rec in records:
            ann = rec.get("announce_date")
            if ann is not None:
                updates.append((ann, asset_id, report_date))

        if i % 200 == 0 or i == total:
            logger.info("Progress: %d / %d processed, %d pending updates, %d errors", i, total, len(updates), errors)

    # Apply all updates in a single transaction
    if updates:
        logger.info("Applying %d updates ...", len(updates))
        for ann, asset_id, report_date in updates:
            catalog.execute(
                "UPDATE silver_fundamentals SET announce_date = ? "
                "WHERE asset_id = ? AND report_date = ?",
                [ann, asset_id, report_date],
            )
        updated = len(updates)

    logger.info(
        "Refresh complete — %d rows updated, %d errors out of %d pairs.",
        updated, errors, total,
    )
    return updated


if __name__ == "__main__":
    from cquant.datahub.catalog import Catalog
    from cquant.datahub.connectors.tushare_connector import TushareConnector

    db_path = _REPO_ROOT / "data" / "catalog.duckdb"
    logger.info("Connecting to DuckDB at %s ...", db_path)

    cat = Catalog(db_path=str(db_path))
    conn = TushareConnector()
    try:
        n = refresh(cat, conn)
        logger.info("Done — %d announce_dates refreshed.", n)
    finally:
        cat._backend.close()
        logger.info("Connection closed.")
