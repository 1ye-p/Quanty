-- analysis.sql — Backtest analysis mart tables.

CREATE TABLE IF NOT EXISTS gold_bt_analysis_runs (
    analysis_run_id         VARCHAR PRIMARY KEY,
    backtest_run_id         VARCHAR NOT NULL,
    overall_overfit_score   DOUBLE NOT NULL,
    dsr                     DOUBLE NOT NULL,
    psr                     DOUBLE NOT NULL,
    summary                 VARCHAR,
    created_at              TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_bt_analysis_runs_backtest
    ON gold_bt_analysis_runs (backtest_run_id);

CREATE TABLE IF NOT EXISTS gold_bt_validation_windows (
    analysis_run_id         VARCHAR NOT NULL,
    window_id               INTEGER NOT NULL,
    method                  VARCHAR NOT NULL,    -- 'walk_forward' | 'cpcv'
    train_start             DATE,
    train_end               DATE,
    test_start              DATE NOT NULL,
    test_end                DATE NOT NULL,
    metrics_json            JSON,
    PRIMARY KEY (analysis_run_id, method, window_id)
);

CREATE TABLE IF NOT EXISTS gold_bt_multiple_testing (
    analysis_run_id         VARCHAR NOT NULL,
    method                  VARCHAR NOT NULL,    -- 'bonferroni' | 'bhy' | 'bailey_lopez'
    n_trials                INTEGER NOT NULL,
    alpha                   DOUBLE NOT NULL,
    results_json            JSON,
    accepted                BOOLEAN NOT NULL,
    PRIMARY KEY (analysis_run_id, method)
);
