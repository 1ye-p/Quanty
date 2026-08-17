"""Unit tests for scheduler StrategyHealthChecker + baseline_run_id mechanism."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import duckdb
import pytest

from cquant.scheduler.strategy_health import (
    StrategyHealthChecker,
    get_baseline_run_id,
    set_baseline_run_id,
)


class FakeCatalog:
    """Minimal catalog stub backed by in-memory DuckDB."""

    def __init__(self) -> None:
        self.conn = duckdb.connect(":memory:")
        self.conn.execute("""
            CREATE TABLE meta_strategy_configs (
                strategy_id VARCHAR PRIMARY KEY,
                config_format VARCHAR DEFAULT 'json',
                config_text TEXT,
                parsed_config JSON,
                created_at TIMESTAMPTZ,
                updated_at TIMESTAMPTZ
            )
        """)
        self.conn.execute("""
            CREATE TABLE gold_backtest_runs (
                run_id VARCHAR PRIMARY KEY,
                engine VARCHAR,
                strategy_id VARCHAR,
                dataset_version VARCHAR,
                started_at TIMESTAMPTZ,
                completed_at TIMESTAMPTZ,
                status VARCHAR,
                is_walk_forward BOOLEAN,
                n_folds INTEGER,
                aggregated_metrics_json JSON
            )
        """)
        self.conn.execute("""
            CREATE TABLE gold_wf_folds (
                run_id VARCHAR,
                fold_id INTEGER,
                train_start VARCHAR,
                train_end VARCHAR,
                test_start VARCHAR,
                test_end VARCHAR,
                fold_run_id VARCHAR,
                oos_sharpe DOUBLE,
                oos_return DOUBLE,
                oos_max_drawdown DOUBLE,
                oos_ic DOUBLE,
                PRIMARY KEY (run_id, fold_id)
            )
        """)

    def query(self, sql, params=None):
        return self.conn.execute(sql, params or []).pl()

    def execute(self, sql, params=None):
        self.conn.execute(sql, params or [])


NOW = datetime.now(tz=timezone.utc)


def _add_strategy(cat, strategy_id="strat_a", parsed=None):
    cat.execute(
        "INSERT INTO meta_strategy_configs VALUES (?, 'json', ?, ?, ?, ?)",
        [strategy_id, json.dumps(parsed or {}), json.dumps(parsed or {}),
         NOW.isoformat(), NOW.isoformat()],
    )


def _add_wf_run(cat, run_id, strategy_id="strat_a", completed_at=None, folds=()):
    completed_at = completed_at or (NOW - timedelta(days=200))
    cat.execute(
        "INSERT INTO gold_backtest_runs VALUES (?, 'walk_forward', ?, 'v1', ?, ?, "
        "'completed', TRUE, ?, NULL)",
        [run_id, strategy_id, completed_at.isoformat(), completed_at.isoformat(), len(folds)],
    )
    for i, (sharpe, ic) in enumerate(folds):
        cat.execute(
            "INSERT INTO gold_wf_folds VALUES (?, ?, '2024-01-01', '2024-06-30', "
            "'2024-07-01', '2024-09-30', ?, ?, 0.1, -0.05, ?)",
            [run_id, i, f"{run_id}_f{i}", sharpe, ic],
        )


@pytest.fixture()
def cat():
    return FakeCatalog()


class TestBaselineRunId:
    def test_explicit_config_wins(self, cat):
        _add_strategy(cat)
        _add_wf_run(cat, "run_early")
        _add_wf_run(cat, "run_late")
        set_baseline_run_id(cat, "strat_a", "run_late")
        assert get_baseline_run_id(cat, "strat_a") == "run_late"

    def test_defaults_to_earliest_wf_run(self, cat):
        _add_strategy(cat)
        _add_wf_run(cat, "run_late", completed_at=NOW - timedelta(days=10))
        _add_wf_run(cat, "run_early", completed_at=NOW - timedelta(days=300))
        assert get_baseline_run_id(cat, "strat_a") == "run_early"

    def test_no_runs_returns_none(self, cat):
        _add_strategy(cat)
        assert get_baseline_run_id(cat, "strat_a") is None

    def test_set_updates_parsed_config(self, cat):
        _add_strategy(cat, parsed={"top_n": 5})
        set_baseline_run_id(cat, "strat_a", "run_x")
        row = cat.query(
            "SELECT parsed_config FROM meta_strategy_configs WHERE strategy_id = 'strat_a'"
        )
        parsed = json.loads(row["parsed_config"][0])
        assert parsed["baseline_run_id"] == "run_x"
        assert parsed["top_n"] == 5  # other keys preserved


class TestStrategyHealthChecker:
    def test_decay_triggers(self, cat):
        """Baseline sharpe 2.0 → recent 1.0 (>40% decay) → sharpe_decay."""
        _add_strategy(cat)
        _add_wf_run(cat, "run_base", folds=[(2.0, 0.05), (2.0, 0.05)])
        _add_wf_run(
            cat, "run_recent", completed_at=NOW - timedelta(days=5),
            folds=[(1.0, 0.05), (1.0, 0.05)],
        )
        result = StrategyHealthChecker(cat).check("strat_a")
        assert result.status == "needs_reoptimization"
        assert result.reason == "sharpe_decay"
        assert result.baseline_sharpe == pytest.approx(2.0)
        assert result.recent_sharpe == pytest.approx(1.0)

    def test_ic_loss_triggers(self, cat):
        """Baseline IC 0.08 → recent IC 0.0 (below floor) → ic-loss."""
        _add_strategy(cat)
        _add_wf_run(cat, "run_base", folds=[(1.5, 0.08), (1.5, 0.08)])
        _add_wf_run(
            cat, "run_recent", completed_at=NOW - timedelta(days=5),
            folds=[(1.5, 0.0), (1.5, -0.01)],
        )
        result = StrategyHealthChecker(cat).check("strat_a")
        assert result.status == "needs_reoptimization"
        assert result.reason == "ic_loss"

    def test_healthy_skips(self, cat):
        """Recent within threshold of baseline → healthy."""
        _add_strategy(cat)
        _add_wf_run(cat, "run_base", folds=[(1.5, 0.05)])
        _add_wf_run(
            cat, "run_recent", completed_at=NOW - timedelta(days=5),
            folds=[(1.4, 0.04)],
        )
        result = StrategyHealthChecker(cat).check("strat_a")
        assert result.status == "healthy"
        assert result.reason is None

    def test_insufficient_data_skips(self, cat):
        """No folds in recent window → insufficient_data."""
        _add_strategy(cat)
        _add_wf_run(cat, "run_base", completed_at=NOW - timedelta(days=300),
                    folds=[(1.5, 0.05)])
        result = StrategyHealthChecker(cat).check("strat_a")
        assert result.status == "insufficient_data"

    def test_no_baseline_run(self, cat):
        """Strategy with no wf runs at all → insufficient_data."""
        _add_strategy(cat)
        result = StrategyHealthChecker(cat).check("strat_a")
        assert result.status == "insufficient_data"
