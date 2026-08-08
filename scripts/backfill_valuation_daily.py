"""Backfill silver_valuation_daily for all assets.

Batched (50 assets/batch), incremental (only fetches dates not yet present).

Usage::

    python scripts/backfill_valuation_daily.py [--start 20240101] [--end 20251231]
"""

from __future__ import annotations

import argparse
import logging

BATCH = 50

logger = logging.getLogger(__name__)


def backfill(
    catalog,
    connector,
    asset_ids: list[str],
    start_date: str,
    end_date: str,
) -> None:
    """Batch-backfill silver_valuation_daily (batches of 50, incremental).

    For each asset, queries the existing max trade_date and only fetches
    the missing date range.

    Parameters
    ----------
    catalog
        DuckDB Catalog instance (with ``query`` and ``upsert`` methods).
    connector
        TushareConnector instance (with ``fetch_valuation_daily`` method).
    asset_ids
        List of Tushare ts_code values.
    start_date
        Backfill start date (``YYYYMMDD``).
    end_date
        Backfill end date (``YYYYMMDD``).
    """
    total = len(asset_ids)
    written = 0
    skipped = 0

    for i in range(0, total, BATCH):
        batch = asset_ids[i : i + BATCH]
        logger.info(
            "Backfill batch %d-%d / %d", i, min(i + BATCH, total), total,
        )
        for ts_code in batch:
            try:
                existing_max = catalog.query(
                    "SELECT MAX(trade_date) AS m FROM silver_valuation_daily WHERE asset_id = ?",
                    [ts_code],
                )
                latest = existing_max["m"][0] if not existing_max.is_empty() else None
                start = (
                    str(int(latest) + 1) if latest is not None else start_date
                )
                if int(start) > int(end_date):
                    skipped += 1
                    continue

                df = connector.fetch_valuation_daily(ts_code, start, end_date)
                if len(df) > 0:
                    catalog.upsert("silver_valuation_daily", df)
                    written += 1
            except Exception as exc:
                logger.warning("Backfill failed for %s: %s", ts_code, exc)

    logger.info(
        "Backfill complete: %d written, %d skipped (up-to-date), %d total",
        written, skipped, total,
    )


def _load_asset_ids(catalog) -> list[str]:
    """Load all asset IDs from silver_assets."""
    try:
        df = catalog.query("SELECT DISTINCT asset_id FROM silver_assets LIMIT 5000")
        return df["asset_id"].to_list() if not df.is_empty() else []
    except Exception as exc:
        logger.warning("backfill: failed to load asset list: %s", exc)
        return []


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill silver_valuation_daily")
    parser.add_argument("--start", default="20240101", help="Start date YYYYMMDD")
    parser.add_argument("--end", default="20251231", help="End date YYYYMMDD")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    from cquant.datahub.catalog import Catalog  # noqa: PLC0415
    from cquant.datahub.connectors.tushare_connector import TushareConnector  # noqa: PLC0415

    catalog = Catalog()
    connector = TushareConnector()
    asset_ids = _load_asset_ids(catalog)

    if not asset_ids:
        logger.error("No asset IDs found in silver_assets. Run bootstrap first.")
        return

    logger.info("Starting backfill for %d assets (%s -> %s)", len(asset_ids), args.start, args.end)
    backfill(catalog, connector, asset_ids, args.start, args.end)


if __name__ == "__main__":
    main()
