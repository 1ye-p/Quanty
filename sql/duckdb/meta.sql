-- meta.sql — Strategy configs, factor analytics cache, ML job tracking.

CREATE TABLE IF NOT EXISTS meta_strategy_configs (
    strategy_id    VARCHAR PRIMARY KEY,
    config_format  VARCHAR DEFAULT 'json',   -- 'json' | 'toml'
    config_text    TEXT NOT NULL,
    parsed_config  JSON,
    universe_id    VARCHAR,
    risk_limits_json JSON,
    created_at     TIMESTAMPTZ NOT NULL,
    updated_at     TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS meta_factor_analytics (
    job_id              VARCHAR PRIMARY KEY,
    factor_name         VARCHAR NOT NULL,
    feature_set_version VARCHAR NOT NULL,
    horizon_days        INTEGER DEFAULT 1,
    status              VARCHAR DEFAULT 'pending',  -- pending | running | done | error
    series_json         JSON,
    summary_json        JSON,
    error_text          VARCHAR,
    submitted_at        TIMESTAMPTZ NOT NULL,
    completed_at        TIMESTAMPTZ,
    UNIQUE (factor_name, feature_set_version, horizon_days)
);

CREATE TABLE IF NOT EXISTS meta_ml_jobs (
    job_id              VARCHAR PRIMARY KEY,
    trainer_name        VARCHAR NOT NULL,
    feature_set_version VARCHAR NOT NULL,
    target_name         VARCHAR NOT NULL,
    params_json         JSON,
    status              VARCHAR DEFAULT 'pending',
    mlflow_run_id       VARCHAR,
    artifact_path       VARCHAR,
    error_text          VARCHAR,
    submitted_at        TIMESTAMPTZ NOT NULL,
    completed_at        TIMESTAMPTZ
);
