-- news.sql — Silver-layer news events with point-in-time availability semantics.

CREATE TABLE IF NOT EXISTS silver_news_events (
    event_id              VARCHAR PRIMARY KEY,
    source                VARCHAR NOT NULL,
    vendor_id             VARCHAR NOT NULL,
    headline              VARCHAR NOT NULL,
    body                  TEXT,
    published_at          TIMESTAMPTZ,
    available_at          TIMESTAMPTZ NOT NULL,
    ingested_at           TIMESTAMPTZ NOT NULL,
    asset_ids_mentioned   VARCHAR[] NOT NULL DEFAULT [],
    event_type            VARCHAR NOT NULL,
    sentiment_score       DOUBLE,
    language              VARCHAR NOT NULL,
    region                VARCHAR NOT NULL,
    dedupe_key            VARCHAR NOT NULL UNIQUE
);

CREATE INDEX IF NOT EXISTS idx_silver_news_available_at
    ON silver_news_events (available_at);

CREATE INDEX IF NOT EXISTS idx_silver_news_source_published
    ON silver_news_events (source, published_at);

CREATE INDEX IF NOT EXISTS idx_silver_news_ingested_at
    ON silver_news_events (ingested_at);
