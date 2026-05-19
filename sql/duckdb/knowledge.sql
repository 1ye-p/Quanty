-- knowledge.sql — Knowledge base metadata catalog (kb_* tables).
-- Stores document provenance, processing lineage, entities, tags, and search history.

-- ── Document catalog ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS kb_documents (
    doc_id              VARCHAR PRIMARY KEY,        -- '{source_slug}__{date}__{sha256[:8]}'
    logical_type        VARCHAR NOT NULL,            -- 'research' | 'strategy' | 'notes' | 'data'
    source_type         VARCHAR NOT NULL,            -- 'pdf' | 'url' | 'markdown' | 'tabular'
    title               VARCHAR NOT NULL DEFAULT '',
    source_name         VARCHAR NOT NULL DEFAULT '', -- Institution / author / feed name
    canonical_url       VARCHAR,
    published_at        TIMESTAMPTZ,
    available_at        TIMESTAMPTZ,
    ingested_at         TIMESTAMPTZ NOT NULL,
    language            VARCHAR DEFAULT 'zh-CN',
    content_hash        VARCHAR(64) UNIQUE,          -- SHA-256 of raw content
    raw_path            VARCHAR,                     -- Relative path under knowledge/raw_ingested/
    current_version_id  VARCHAR,
    status              VARCHAR DEFAULT 'active',   -- 'active' | 'quarantined' | 'deleted'
    tags_json           JSON
);

CREATE INDEX IF NOT EXISTS idx_kb_documents_source
    ON kb_documents (source_type, published_at);

CREATE INDEX IF NOT EXISTS idx_kb_documents_type
    ON kb_documents (logical_type, ingested_at);

-- ── Document version lineage ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS kb_document_versions (
    version_id          VARCHAR PRIMARY KEY,
    doc_id              VARCHAR NOT NULL,
    parent_version_id   VARCHAR,
    raw_hash            VARCHAR(64),
    extracted_text_path VARCHAR,
    parser_name         VARCHAR,
    parser_version      VARCHAR,
    is_current          BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_kb_versions_doc
    ON kb_document_versions (doc_id, is_current);

-- ── Chunks ────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS kb_chunks (
    chunk_id        VARCHAR PRIMARY KEY,
    doc_id          VARCHAR NOT NULL,
    version_id      VARCHAR NOT NULL,
    chunk_index     INTEGER NOT NULL,
    section_path    VARCHAR DEFAULT '',   -- e.g. '1.2.3 Momentum Factors'
    text_path       VARCHAR,              -- Path to chunk text file
    token_count     INTEGER DEFAULT 0,
    char_start      INTEGER,
    char_end        INTEGER,
    chunk_hash      VARCHAR(64)
);

CREATE INDEX IF NOT EXISTS idx_kb_chunks_doc
    ON kb_chunks (doc_id, chunk_index);

-- ── Summaries ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS kb_summaries (
    summary_id      VARCHAR PRIMARY KEY,
    doc_id          VARCHAR NOT NULL,
    version_id      VARCHAR NOT NULL,
    summary_kind    VARCHAR NOT NULL,     -- 'executive' | 'thesis' | 'factors' | 'risks'
    content_path    VARCHAR,
    model_name      VARCHAR,
    prompt_version  VARCHAR DEFAULT 'v1',
    created_at      TIMESTAMPTZ NOT NULL
);

-- ── Tags ──────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS kb_tags (
    tag_id          VARCHAR PRIMARY KEY,
    namespace       VARCHAR NOT NULL,     -- 'industry' | 'ticker' | 'strategy_type' | 'time_window'
    value           VARCHAR NOT NULL,
    normalized_value VARCHAR NOT NULL,
    UNIQUE (namespace, normalized_value)
);

CREATE TABLE IF NOT EXISTS kb_document_tags (
    doc_id          VARCHAR NOT NULL,
    version_id      VARCHAR NOT NULL,
    tag_id          VARCHAR NOT NULL,
    confidence      DOUBLE DEFAULT 1.0,
    source_stage    VARCHAR DEFAULT 'tagger',
    run_id          VARCHAR,
    PRIMARY KEY (doc_id, tag_id)
);

-- ── Entity catalog ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS kb_entities (
    entity_id       VARCHAR PRIMARY KEY,
    entity_type     VARCHAR NOT NULL,     -- 'company' | 'factor' | 'strategy' | 'author' | 'macro'
    canonical_name  VARCHAR NOT NULL,
    ticker          VARCHAR,
    exchange        VARCHAR,
    industry        VARCHAR,
    country         VARCHAR DEFAULT 'CN',
    first_seen_at   TIMESTAMPTZ,
    last_seen_at    TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS kb_entity_mentions (
    mention_id      VARCHAR PRIMARY KEY,
    entity_id       VARCHAR NOT NULL,
    doc_id          VARCHAR NOT NULL,
    chunk_id        VARCHAR,
    mention_text    VARCHAR NOT NULL,
    confidence      DOUBLE DEFAULT 1.0,
    role            VARCHAR DEFAULT 'mentioned'  -- 'subject' | 'mentioned' | 'compared'
);

CREATE INDEX IF NOT EXISTS idx_kb_mentions_entity
    ON kb_entity_mentions (entity_id, doc_id);

-- ── Knowledge graph (lightweight, no Neo4j required for MVP) ──────────────────
CREATE TABLE IF NOT EXISTS kb_graph_edges (
    edge_id             VARCHAR PRIMARY KEY,
    src_entity_id       VARCHAR NOT NULL,
    dst_entity_id       VARCHAR NOT NULL,
    relation_type       VARCHAR NOT NULL,    -- 'covers' | 'recommends' | 'compares' | 'cites'
    weight              DOUBLE DEFAULT 1.0,
    confidence          DOUBLE DEFAULT 1.0,
    evidence_doc_id     VARCHAR,
    evidence_chunk_id   VARCHAR,
    valid_from          TIMESTAMPTZ,
    valid_to            TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_kb_graph_src
    ON kb_graph_edges (src_entity_id, relation_type);

-- ── Vector index pointer (DuckDB → LanceDB) ───────────────────────────────────
CREATE TABLE IF NOT EXISTS kb_vector_index (
    vector_row_id   VARCHAR PRIMARY KEY,
    doc_id          VARCHAR NOT NULL,
    chunk_id        VARCHAR NOT NULL,
    backend         VARCHAR DEFAULT 'lancedb',
    collection      VARCHAR DEFAULT 'kb_chunks',
    vector_key      VARCHAR NOT NULL,
    embedding_model VARCHAR NOT NULL,
    embedding_dim   INTEGER,
    content_hash    VARCHAR(64),
    created_at      TIMESTAMPTZ NOT NULL,
    UNIQUE (doc_id, chunk_id, embedding_model)
);

-- ── Ingestion audit ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS kb_ingest_runs (
    run_id          VARCHAR PRIMARY KEY,
    loader_type     VARCHAR NOT NULL,
    input_uri       VARCHAR NOT NULL,
    input_hash      VARCHAR(64),
    status          VARCHAR DEFAULT 'ok',   -- 'ok' | 'error' | 'quarantined'
    error_text      VARCHAR,
    started_at      TIMESTAMPTZ NOT NULL,
    finished_at     TIMESTAMPTZ
);

-- ── Search history (for ai_advisor context) ───────────────────────────────────
CREATE TABLE IF NOT EXISTS kb_search_history (
    query_id        VARCHAR PRIMARY KEY,
    session_id      VARCHAR,
    query_text      VARCHAR NOT NULL,
    query_type      VARCHAR DEFAULT 'hybrid',   -- 'hybrid' | 'semantic' | 'keyword' | 'graph'
    filters_json    JSON,
    top_k           INTEGER DEFAULT 10,
    latency_ms      INTEGER,
    result_count    INTEGER,
    created_at      TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_kb_search_history_session
    ON kb_search_history (session_id, created_at);
