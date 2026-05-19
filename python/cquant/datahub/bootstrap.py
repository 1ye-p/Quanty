"""cquant.datahub.bootstrap — Bootstrap silver_assets and silver_trading_calendar from TDX.

Extracts asset metadata and trading dates from tdx.db to populate the
silver layer, enabling universe building, suspension detection, and
calendar-aware scheduling.
"""

from __future__ import annotations

import logging
from datetime import date

import duckdb
import polars as pl

from cquant.datahub.catalog import Catalog
from cquant.datahub.connectors.tdx_connector import _to_asset_id

logger = logging.getLogger(__name__)


def bootstrap_assets_from_tdx(
    catalog: Catalog,
    tdx_db_path: str = "tdx.db",
) -> int:
    """Populate silver_assets from tdx.db symbol metadata.

    Returns the number of assets inserted.
    """
    catalog.initialize()
    con = duckdb.connect(tdx_db_path, read_only=True)
    try:
        # Get distinct symbols with their first/last trade dates
        df = con.execute("""
            SELECT
                symbol,
                MIN(date) AS first_trade,
                MAX(date) AS last_trade,
                COUNT(*) AS trade_days
            FROM raw_stocks_daily
            GROUP BY symbol
            ORDER BY symbol
        """).pl()
    finally:
        con.close()

    if df.is_empty():
        logger.warning("No symbols found in tdx.db")
        return 0

    # Map to cQuant asset format
    df = df.with_columns(
        pl.col("symbol").map_elements(_to_asset_id, return_dtype=pl.Utf8).alias("asset_id"),
    )

    # Extract exchange and symbol from asset_id
    df = df.with_columns([
        pl.col("asset_id").str.split(":").list.get(0).alias("exchange"),
        pl.col("asset_id").str.split(":").list.get(1).alias("code"),
    ])

    # Determine asset class based on code patterns
    df = df.with_columns(
        pl.when(pl.col("code").str.starts_with("688"))
        .then(pl.lit("STAR"))  # 科创板
        .when(pl.col("code").str.starts_with("300"))
        .then(pl.lit("ChiNext"))  # 创业板
        .when(pl.col("code").str.starts_with("8"))
        .then(pl.lit("BSE"))  # 北交所
        .when(pl.col("code").str.starts_with("0"))
        .then(pl.lit("Main"))  # 深主板
        .otherwise(pl.lit("Main"))  # 沪主板
        .alias("sector")
    )

    # Build silver_assets rows
    now_iso = "2026-05-17T00:00:00Z"
    asset_rows = df.select([
        pl.col("asset_id"),
        pl.col("code").alias("symbol"),
        pl.col("exchange"),
        pl.lit("EQUITY").alias("asset_class"),
        pl.lit("CNY").alias("currency"),
        pl.lit("").alias("name"),
        pl.lit("").alias("name_en"),
        pl.lit("active").alias("status"),
        pl.lit(100).alias("lot_size"),
        pl.lit(0.01).alias("tick_size"),
        pl.col("first_trade").alias("list_date"),
        pl.lit(None).cast(pl.Date).alias("delist_date"),
        pl.col("sector").alias("industry"),
        pl.col("sector").alias("sector"),
        pl.col("first_trade").alias("effective_from"),
        pl.lit(None).cast(pl.Date).alias("effective_to"),
        pl.lit(now_iso).alias("updated_at"),
    ])

    # Write to DuckDB
    conn = catalog._get_conn()
    stage = "_assets_stage"
    conn.register(stage, asset_rows.to_arrow())
    try:
        conn.execute(f"""
            INSERT OR REPLACE INTO silver_assets
            SELECT * FROM {stage}
        """)
    except Exception as exc:
        logger.error("Failed to write silver_assets: %s", exc)
        raise
    finally:
        try:
            conn.unregister(stage)
        except Exception:
            pass

    count = len(asset_rows)
    logger.info("Bootstrapped %d assets to silver_assets", count)
    return count


def enrich_industry_from_lookup(
    catalog: Catalog,
    lookup: pl.DataFrame,
) -> int:
    """Enrich silver_assets with real industry classifications.

    Parameters:
        catalog: Initialized Catalog instance.
        lookup: DataFrame with columns [asset_id, industry].

    Returns number of assets updated.
    """
    if lookup.is_empty():
        return 0

    # Get current asset_ids from silver_assets
    current = catalog.query("SELECT asset_id FROM silver_assets")
    if current.is_empty():
        return 0

    # Find asset_ids present in both silver_assets and lookup
    current_ids = set(current["asset_id"].to_list())
    lookup_matched = lookup.filter(pl.col("asset_id").is_in(list(current_ids)))

    if lookup_matched.is_empty():
        return 0

    matched_ids = lookup_matched["asset_id"].to_list()

    # Update industry using a temp table + UPDATE ... FROM
    conn = catalog._get_conn()
    stage = "_industry_lookup_stage"
    conn.register(stage, lookup_matched.to_arrow())
    try:
        conn.execute(f"""
            UPDATE silver_assets
            SET industry = l.industry
            FROM {stage} AS l
            WHERE silver_assets.asset_id = l.asset_id
        """)
    finally:
        try:
            conn.unregister(stage)
        except Exception:
            pass

    return len(matched_ids)


def bootstrap_calendar_from_tdx(
    catalog: Catalog,
    tdx_db_path: str = "tdx.db",
) -> int:
    """Populate silver_trading_calendar from actual trading dates in tdx.db.

    Returns the number of calendar entries inserted.
    """
    catalog.initialize()
    con = duckdb.connect(tdx_db_path, read_only=True)
    try:
        # Get distinct trading dates per exchange
        df = con.execute("""
            SELECT DISTINCT
                CASE
                    WHEN symbol LIKE 'sh%' THEN 'SSE'
                    WHEN symbol LIKE 'sz%' THEN 'SZSE'
                    WHEN symbol LIKE 'bj%' THEN 'BSE'
                END AS exchange,
                date
            FROM raw_stocks_daily
            WHERE symbol NOT LIKE '~%'  -- Exclude indices
            ORDER BY exchange, date
        """).pl()
    finally:
        con.close()

    if df.is_empty():
        logger.warning("No trading dates found in tdx.db")
        return 0

    df = df.with_columns([
        pl.lit(True).alias("is_open"),
        pl.lit(None).cast(pl.Utf8).alias("open_time"),
        pl.lit(None).cast(pl.Utf8).alias("close_time"),
        pl.lit("tdx").alias("source"),
    ])

    conn = catalog._get_conn()
    stage = "_calendar_stage"
    conn.register(stage, df.to_arrow())
    try:
        conn.execute(f"""
            INSERT OR REPLACE INTO silver_trading_calendar
            SELECT * FROM {stage}
        """)
    except Exception as exc:
        logger.error("Failed to write silver_trading_calendar: %s", exc)
        raise
    finally:
        try:
            conn.unregister(stage)
        except Exception:
            pass

    count = len(df)
    logger.info("Bootstrapped %d calendar entries to silver_trading_calendar", count)
    return count
