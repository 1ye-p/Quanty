-- bronze.sql — Raw ingestion audit and metadata tables.
-- Bronze layer stores only provenance metadata; raw file bytes live on the filesystem.

CREATE TABLE IF NOT EXISTS bronze_ingestions (
    ingestion_id      VARCHAR PRIMARY KEY,
    source            VARCHAR NOT NULL,        -- connector name, e.g. 'akshare'
    dataset           VARCHAR NOT NULL,        -- 'daily_bar', 'fundamentals', etc.
    symbol            VARCHAR,                 -- NULL for bulk batches
    fetch_start_date  DATE,
    fetch_end_date    DATE,
    row_count         BIGINT,
    storage_uri       VARCHAR,                 -- Parquet file path (relative to lake_root)
    content_hash      VARCHAR(64),             -- SHA-256 of serialized data
    schema_version    VARCHAR DEFAULT '1.0',
    fetched_at        TIMESTAMPTZ NOT NULL,
    status            VARCHAR DEFAULT 'ok',    -- 'ok' | 'error' | 'partial'
    error_message     VARCHAR
);

CREATE INDEX IF NOT EXISTS idx_bronze_ingestions_source_date
    ON bronze_ingestions (source, fetch_start_date, fetch_end_date);
