"""从 silver_prices_1d 中提取资产列表并填充 silver_assets 表。"""
from __future__ import annotations
import logging
from cquant.datahub.catalog import Catalog

logger = logging.getLogger(__name__)


def bootstrap_assets_from_prices(catalog: Catalog) -> int:
    """从 silver_prices_1d 中提取资产列表并填充 silver_assets 表。
    
    Returns: 插入的资产数量
    """
    catalog.execute("""
        CREATE TABLE IF NOT EXISTS silver_assets (
            asset_id VARCHAR PRIMARY KEY,
            symbol VARCHAR NOT NULL,
            exchange VARCHAR NOT NULL,
            asset_class VARCHAR NOT NULL,
            currency VARCHAR NOT NULL,
            name VARCHAR DEFAULT '',
            name_en VARCHAR DEFAULT '',
            status VARCHAR DEFAULT 'active',
            lot_size INTEGER DEFAULT 100,
            tick_size DECIMAL(18, 8) DEFAULT 0.01,
            list_date DATE,
            delist_date DATE,
            industry VARCHAR,
            sector VARCHAR,
            effective_from DATE NOT NULL,
            effective_to DATE,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    
    # 从 silver_prices_1d 提取资产信息
    df = catalog.query("""
        SELECT 
            asset_id,
            SPLIT_PART(asset_id, ':', 2) as symbol,
            SPLIT_PART(asset_id, ':', 1) as exchange,
            MIN(trade_date) as first_trade,
            MAX(trade_date) as last_trade,
            COUNT(*) as trade_days
        FROM silver_prices_1d
        GROUP BY asset_id
    """)
    
    if df.is_empty():
        return 0
    
    count = 0
    for row in df.to_dicts():
        asset_id = row["asset_id"]
        symbol = row["symbol"]
        exchange = row["exchange"]
        
        # 判断资产类别
        if symbol.startswith("688"):
            sector = "STAR"
        elif symbol.startswith("300"):
            sector = "ChiNext"
        elif symbol.startswith("8"):
            sector = "BSE"
        else:
            sector = "Main"
        
        try:
            catalog.execute("""
                INSERT INTO silver_assets 
                (asset_id, symbol, exchange, asset_class, currency, name, name_en, 
                 status, lot_size, tick_size, list_date, delist_date, industry, sector,
                 effective_from, effective_to, updated_at)
                VALUES (?, ?, ?, 'EQUITY', 'CNY', '', '', 'active', 100, 0.01, 
                        ?, NULL, ?, ?, ?, NULL, NOW())
                ON CONFLICT (asset_id) DO UPDATE SET
                    status = 'active',
                    updated_at = NOW()
            """, [asset_id, symbol, exchange, row["first_trade"], sector, sector, 
                  row["first_trade"]])
            count += 1
        except Exception as exc:
            logger.warning("Failed to insert asset %s: %s", asset_id, exc)
    
    logger.info("Bootstrap from prices: populated %d assets", count)
    return count
