"""Unit tests for scheduler StrategyOptimizationJob (health-gated re-optimization)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import duckdb
import pytest

from cquant.scheduler.strategy_optimizer import (
    STATUS_FAILED,
    STATUS_NEEDS_REVIEW,
    STATUS_SKIPPED_HEALTHY,
    STATUS_SKIPPED_NO_GAIN,
    OptimizationReport,
    StrategyOptimizationJob,
    _composite_score,
)
from cquant.scheduler.strategy_health import HealthResult


class FakeCatalog:
    """Minimal catalog stub backed by in-memory DuckDB."""

    def __init__(self) -> None:
        self.conn = duckdb.connect(":memory:")
        self.conn.execute("CREATE TABLE meta_strategy_configs (strategy_id VARCHAR PRIMARY KEY, parsed_config JSON)")
        self.conn.execute("""
            CREATE TABLE gold_backtest_runs (
                run_id VARCHAR PRIMARY KEY, engine VARCHAR, strategy_id VARCHAR,
                dataset_version VARCHAR, started_at TIMESTAMPTZ, completed_at TIMESTAMPTZ,
                status VARCHAR, is_walk_forward BOOLEAN, n_folds INTEGER,
                aggregated_metrics_json JSON
            )
        """)
        self.conn.execute("""
            CREATE TABLE gold_wf_folds (
                run_id VARCHAR, fold_id INTEGER, train_start VARCHAR, train_end VARCHAR,
                test_start VARCHAR, test_end VARCHAR, fold_run_id VARCHAR,
                oos_sharpe DOUBLE, oos_return DOUBLE, oos_max_drawdown DOUBLE,
                oos_ic DOUBLE, PRIMARY KEY (run_id, fold_id)
            )
        """)

    def query(self, sql, params=None):
        return self.conn.execute(sql, params or []).pl()

    def execute(self, sql, params=None):
        self.conn.execute(sql, params or [])


NOW = datetime.now(tz=timezone.utc)


def _seed_strategy(cat, strategy_id, parsed=None):
    cat.execute(
        "INSERT INTO meta_strategy_configs VALUES (?, ?)",
        [strategy_id, json.dumps(parsed or {})],
    )


def _seed_wf_run(cat, run_id, strategy_id, completed_at, folds):
    cat.execute(
        "INSERT INTO gold_backtest_runs VALUES (?, 'walk_forward', ?, 'v1', ?, ?, "
        "'completed', TRUE, ?, NULL)",
        [run_id, strategy_id, completed_at.isoformat(), completed_at.isoformat(), len(folds)],
    )
    for i, (sharpe, ic) in enumerate(folds):
        cat.execute(
            "INSERT INTO gold_wf_folds VALUES (?, ?, '2024-01-01', '2024-06-30', "
            "'2024-07-01', '2024-09-30', ?, ?, 0.1, 0.05, ?)",
            [run_id, i, f"{run_id}_f{i}", sharpe, ic],
        )


def _seed_decayed_strategy(cat, strategy_id="strat_a"):
    """Baseline sharpe 2.0 → recent 1.0 → needs_reoptimization."""
    _seed_strategy(cat, strategy_id)
    _seed_wf_run(cat, "run_base", strategy_id, NOW - timedelta(days=200), [(2.0, 0.05), (2.0, 0.05)])
    _seed_wf_run(cat, "run_recent", strategy_id, NOW - timedelta(days=5), [(1.0, 0.05), (1.0, 0.05)])


def _seed_healthy_strategy(cat, strategy_id="strat_healthy"):
    _seed_strategy(cat, strategy_id)
    _seed_wf_run(cat, "run_base", strategy_id, NOW - timedelta(days=200), [(1.5, 0.05)])
    _seed_wf_run(cat, "run_recent", strategy_id, NOW - timedelta(days=5), [(1.45, 0.04)])


def _make_job(cat, wf_evaluator=None, ml_trainer=None, **kwargs):
    return StrategyOptimizationJob(
        cat, wf_evaluator=wf_evaluator, ml_trainer=ml_trainer, **kwargs
    )


class TestHealthySkips:
    def test_healthy_strategy_skips_optimization(self, cat):
        """Healthy strategy returns skipped_healthy without running any search."""
        _seed_healthy_strategy(cat)
        calls = []

        def evaluator(strategy_id, params, data):
            calls.append(params)
            return {"oos_sharpe_ratio_mean": 9.0}

        job = _make_job(cat, wf_evaluator=evaluator)
        report = job.run("strat_healthy", {"top_n": 10})
        assert report.status == STATUS_SKIPPED_HEALTHY
        assert report.health is not None
        assert report.health.status == "healthy"
        assert calls == []  # no evaluation ran
        assert report.best_params is None


class TestNeedsReview:
    def test_decayed_strategy_produces_needs_review(self, cat):
        """Decayed strategy: stub wf evaluator finds an improving candidate."""
        _seed_decayed_strategy(cat)

        def evaluator(strategy_id, params, data):
            # Candidate with best score; sharpe improved over baseline 2.0.
            if params == {"top_n": 10}:
                return {"oos_sharpe_ratio_mean": 2.5, "oos_max_drawdown_mean": 0.1}
            return {"oos_sharpe_ratio_mean": 1.8, "oos_max_drawdown_mean": 0.2}

        job = _make_job(cat, wf_evaluator=evaluator, ml_trainer=lambda cfg: {"n_folds": 3})
        report = job.run(
            "strat_a",
            {"top_n": 10, "ml_config": {"dataset": object(), "model_builder": lambda df: None}},
        )
        assert report.status == STATUS_NEEDS_REVIEW
        assert report.best_params == {"top_n": 10}
        assert report.candidate_metrics["oos_sharpe_ratio_mean"] == pytest.approx(2.5)
        assert report.baseline_metrics["oos_sharpe_mean"] == pytest.approx(2.0)
        assert report.ml_retrain == {"n_folds": 3}
        assert report.overfit_check is not None
        assert report.overfit_check["passed"] is True

    def test_no_improvement_skips(self, cat):
        """Best candidate not better than baseline → skipped_no_gain."""
        _seed_decayed_strategy(cat)

        def evaluator(strategy_id, params, data):
            return {"oos_sharpe_ratio_mean": 1.0, "oos_max_drawdown_mean": 0.3}

        job = _make_job(cat, wf_evaluator=evaluator)
        report = job.run("strat_a", {"top_n": 10})
        assert report.status == STATUS_SKIPPED_NO_GAIN
        assert report.reason == "no_improvement"

    def test_non_ml_strategy_no_retrain(self, cat):
        _seed_decayed_strategy(cat)
        ml_calls = []

        def evaluator(strategy_id, params, data):
            return {"oos_sharpe_ratio_mean": 3.0}

        job = _make_job(
            cat,
            wf_evaluator=evaluator,
            ml_trainer=lambda cfg: ml_calls.append(cfg) or {"n_folds": 1},
        )
        report = job.run("strat_a", {"top_n": 10})  # no ml_config
        assert report.status == STATUS_NEEDS_REVIEW
        assert report.ml_retrain is None
        assert ml_calls == []


class TestFailureTolerance:
    def test_evaluator_exception_returns_failed(self, cat):
        """Search crash → status=failed, exception captured, no raise."""
        _seed_decayed_strategy(cat)

        def evaluator(strategy_id, params, data):
            raise RuntimeError("engine blew up")

        job = _make_job(cat, wf_evaluator=evaluator)
        report = job.run("strat_a", {"top_n": 10})
        assert report.status == STATUS_FAILED
        assert "engine blew up" in report.reason

    def test_persist_failure_does_not_fail_report(self, cat):
        """Persistence error is swallowed; report still returned."""
        _seed_decayed_strategy(cat)

        class BrokenCatalog(FakeCatalog):
            def execute(self, sql, params=None):
                raise duckdb.Error("disk full")

        broken = BrokenCatalog.__new__(BrokenCatalog)
        broken.conn = cat.conn  # reuse seeded data

        def evaluator(strategy_id, params, data):
            return {"oos_sharpe_ratio_mean": 3.0}

        job = _make_job(broken, wf_evaluator=evaluator)
        report = job.run("strat_a", {"top_n": 10})
        assert report.status == STATUS_NEEDS_REVIEW  # not failed


class TestMaxGrid:
    def test_grid_capped_at_max(self, cat):
        _seed_decayed_strategy(cat)
        job = _make_job(cat, max_grid=7)
        grid = job._derive_param_grid(
            {"top_n": [5, 10, 15, 20], "lookback_days": [20, 40, 60]}
        )
        assert len(grid) == 7  # 4*3=12 → capped at 7

    def test_default_max_grid_50(self, cat):
        _seed_decayed_strategy(cat)
        job = _make_job(cat)
        grid = job._derive_param_grid(
            {"grid_spec": {"top_n": list(range(10)), "lookback_days": list(range(10))}}
        )
        assert len(grid) == 50

    def test_grid_spec_from_config_wins(self, cat):
        _seed_decayed_strategy(cat)
        job = _make_job(cat)
        grid = job._derive_param_grid(
            {"top_n": 10, "grid_spec": {"top_n": [3, 5]}}
        )
        assert grid == [{"top_n": 3}, {"top_n": 5}]

    def test_empty_grid_skips(self, cat):
        _seed_decayed_strategy(cat)
        job = _make_job(cat)
        report = job.run("strat_a", {})  # no tunable keys
        assert report.status == STATUS_SKIPPED_NO_GAIN
        assert report.reason == "empty_param_grid"


class TestCompositeScore:
    def test_score_formula(self):
        assert _composite_score({"oos_sharpe_ratio_mean": 2.0, "oos_max_drawdown_mean": 0.2}) == pytest.approx(1.9)

    def test_score_handles_missing(self):
        assert _composite_score({}) == 0.0


class TestPersistence:
    def test_report_persisted_to_gold_table(self, cat):
        _seed_decayed_strategy(cat)

        def evaluator(strategy_id, params, data):
            return {"oos_sharpe_ratio_mean": 2.5}

        job = _make_job(cat, wf_evaluator=evaluator)
        report = job.run("strat_a", {"top_n": 10})
        rows = cat.query("SELECT * FROM gold_optimization_reports")
        assert rows.height == 1
        assert rows["strategy_id"][0] == "strat_a"
        assert rows["status"][0] == report.status
        assert json.loads(rows["best_params_json"][0]) == report.best_params
        # Idempotent DDL: re-run create is safe.
        job._persist(report)
        assert cat.query("SELECT COUNT(*) AS n FROM gold_optimization_reports")["n"][0] == 2


@pytest.fixture()
def cat():
    return FakeCatalog()
