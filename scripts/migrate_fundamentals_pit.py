#!/usr/bin/env python3
"""migrate_fundamentals_pit.py — Backfill announce_date for silver_fundamentals.

Tier-based announce_date estimation (decision 3-C):
  - Annual  (month=12): report_date + 120 days
  - H1      (month=6):  report_date + 90 days
  - Q1/Q3   (month=3/9): report_date + 45 days
  - Others:              report_date + 90 days

Idempotent: only updates rows WHERE announce_date IS NULL.
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


def migrate(catalog) -> None:
    """Backfill announce_date based on report period tier."""
    logger.info("Starting announce_date migration on silver_fundamentals ...")

    # Count rows that will be affected before update.
    before = catalog.query(
        "SELECT COUNT(*) AS n FROM silver_fundamentals WHERE announce_date IS NULL"
    )
    null_count = before["n"][0] if len(before) > 0 else 0
    logger.info("Rows with NULL announce_date: %d", null_count)

    if null_count == 0:
        logger.info("Nothing to migrate — skipping.")
        return

    catalog.execute("""
        UPDATE silver_fundamentals
        SET announce_date = CASE
            WHEN EXTRACT(MONTH FROM report_date) = 3  THEN report_date + INTERVAL '45 days'
            WHEN EXTRACT(MONTH FROM report_date) = 6  THEN report_date + INTERVAL '90 days'
            WHEN EXTRACT(MONTH FROM report_date) = 9  THEN report_date + INTERVAL '45 days'
            WHEN EXTRACT(MONTH FROM report_date) = 12 THEN report_date + INTERVAL '120 days'
            ELSE report_date + INTERVAL '90 days'
        END
        WHERE announce_date IS NULL
    """)

    after = catalog.query(
        "SELECT COUNT(*) AS n FROM silver_fundamentals WHERE announce_date IS NULL"
    )
    remaining = after["n"][0] if len(after) > 0 else 0
    logger.info(
        "Migration complete — updated %d rows, %d still NULL.",
        null_count - remaining,
        remaining,
    )


if __name__ == "__main__":
    from cquant.datahub.catalog import Catalog

    db_path = _REPO_ROOT / "data" / "catalog.duckdb"
    logger.info("Connecting to DuckDB at %s ...", db_path)

    cat = Catalog(db_path=str(db_path))
    try:
        migrate(cat)
    finally:
        cat._backend.close()
        logger.info("Connection closed.")
