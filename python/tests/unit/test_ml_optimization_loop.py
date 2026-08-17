"""End-to-end tests for the ML auto-optimization loop (ML-5).

Covers the full closed loop:
  ① health check → ② param grid → ③ walk-forward select → ④ report
  (needs_review) → ⑤ safety: no auto-apply → ⑥ human apply (confirm) →
  ⑦ version bump + baseline update + report applied.

Plus: healthy strategies skip (no evaluator calls), report query, and
confirm/status guards on the apply endpoint.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone

import duckdb
import pytest
from fastapi import HTTPException

from cquant.api_server.routes.strategies import (
    ApplyOptimizationBody,
    apply_optimization,
    get_optimization_report,
)
from cquant.scheduler.strategy_health import (
    StrategyHealthChecker,
    get_baseline_run_id,
)
from cquant.scheduler.strategy_optimizer import (
    STATUS_NEEDS_REVIEW,
    STATUS_SKIPPED_HEALTHY,
    StrategyOptimizationJob,
)

NOW = datetime.now(tz=timezone.utc)


class FakeCatalog:
    """In-memory DuckDB catalog with all tables the loop touches."""

    def __init__(self) -> None:
        self.conn = duckdb.connect(":memory:")
        self.conn.execute("""
            CREATE TABLE meta_strategy_configs (
                strategy_id VARCHAR PRIMARY KEY,
                config_format VARCHAR DEFAULT 'json',
                config_text TEXT,
                parsed_config JSON,
                universe_id VARCHAR DEFAULT '',
                created_at TIMESTAMPTZ,
                updated_at TIMESTAMPTZ
            )
        """)
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
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS gold_optimization_reports (
                strategy_id VARCHAR,
                generated_at TIMESTAMPTZ,
                status VARCHAR,
                reason VARCHAR,
                health_json JSON,
                best_params_json JSON,
                baseline_metrics_json JSON,
                candidate_metrics_json JSON,
                overfit_check_json JSON
            )
        """)

    def query(self, sql, params=None):
        return self.conn.execute(sql, params or []).pl()

    def execute(self, sql, params=None):
        self.conn.execute(sql, params or [])


def _add_strategy(cat, strategy_id, parsed):
    cat.execute(
        "INSERT INTO meta_strategy_configs VALUES (?, 'json', ?, ?, '', ?, ?)",
        [strategy_id, json.dumps(parsed), json.dumps(parsed),
         NOW.isoformat(), NOW.isoformat()],
    )


def _add_wf_run(cat, run_id, strategy_id, completed_at, folds):
    cat.execute(
        "INSERT INTO gold_backtest_runs VALUES (?, 'walk_forward', ?, 'v1', ?, ?, "
        "'completed', TRUE, ?, NULL)",
        [run_id, strategy_id, completed_at.isoformat(), completed_at.isoformat(),
         len(folds)],
    )
    for i, (sharpe, ic) in enumerate(folds):
        cat.execute(
            "INSERT INTO gold_wf_folds VALUES (?, ?, '2024-01-01', '2024-06-30', "
            "'2024-07-01', '2024-09-30', ?, ?, 0.1, 0.05, ?)",
            [run_id, i, f"{run_id}_f{i}", sharpe, ic],
        )


def _get_parsed(cat, strategy_id) -> dict:
    df = cat.query(
        "SELECT parsed_config FROM meta_strategy_configs WHERE strategy_id = ?",
        [strategy_id],
    )
    raw = df["parsed_config"][0]
    return raw if isinstance(raw, dict) else json.loads(str(raw))


@pytest.fixture()
def healthy_cat():
    """Baseline 1.5 vs recent 1.45 → healthy (within decay threshold)."""
    cat = FakeCatalog()
    _add_strategy(cat, "strat_ok", {"top_n": 10})
    _add_wf_run(cat, "run_ok_base", "strat_ok", NOW - timedelta(days=200), [(1.5, 0.05)])
    _add_wf_run(cat, "run_ok_recent", "strat_ok", NOW - timedelta(days=5), [(1.45, 0.04)])
    return cat


@pytest.fixture()
def decayed_cat():
    """Baseline sharpe 2.0 → recent 1.0 (>40% decay) → needs_reoptimization."""
    cat = FakeCatalog()
    _add_strategy(cat, "strat_decay", {"top_n": 10, "rebalance_freq": "weekly"})
    _add_wf_run(
        cat, "run_decay_base", "strat_decay", NOW - timedelta(days=200),
        [(2.0, 0.05), (2.0, 0.05)],
    )
    _add_wf_run(
        cat, "run_decay_recent", "strat_decay", NOW - timedelta(days=5),
        [(1.0, 0.05), (1.0, 0.05)],
    )
    return cat


# ── 场景 1: healthy strategy skips, evaluator never called ─────────────────────


class TestScenario1HealthySkips:
    def test_healthy_skips_without_evaluation(self, healthy_cat):
        calls = []

        def evaluator(strategy_id, params, data):
            calls.append(params)
            return {"oos_sharpe_ratio_mean": 99.0}

        health = StrategyHealthChecker(healthy_cat).check("strat_ok")
        assert health.status == "healthy"

        report = StrategyOptimizationJob(
            healthy_cat, wf_evaluator=evaluator
        ).run("strat_ok", {"top_n": 10})
        assert report.status == STATUS_SKIPPED_HEALTHY
        assert calls == []  # no compute wasted
        assert report.best_params is None


# ── 场景 2: decayed strategy — full loop ①→⑦ ──────────────────────────────────


class TestScenario2FullCycle:
    def test_decay_report_needs_review_and_no_auto_apply(self, decayed_cat):
        def evaluator(strategy_id, params, data):
            if params == {"top_n": 10}:
                return {"oos_sharpe_ratio_mean": 2.5, "oos_max_drawdown_mean": 0.1}
            return {"oos_sharpe_ratio_mean": 1.8, "oos_max_drawdown_mean": 0.2}

        job = StrategyOptimizationJob(decayed_cat, wf_evaluator=evaluator)
        report = job.run(
            "strat_decay", {"top_n": 10, "grid_spec": {"top_n": [5, 10]}}
        )

        # ① health gate fired
        assert report.health.status == "needs_reoptimization"
        assert report.health.reason == "sharpe_decay"
        # ③ best candidate selected
        assert report.status == STATUS_NEEDS_REVIEW
        assert report.best_params == {"top_n": 10}
        assert report.candidate_metrics["oos_sharpe_ratio_mean"] == pytest.approx(2.5)
        assert report.baseline_metrics["oos_sharpe_mean"] == pytest.approx(2.0)
        assert report.overfit_check is not None
        assert report.overfit_check["passed"] is True
        # ⑤ SAFETY: strategy config untouched, baseline unchanged
        assert _get_parsed(decayed_cat, "strat_decay") == {
            "top_n": 10, "rebalance_freq": "weekly",
        }
        assert get_baseline_run_id(decayed_cat, "strat_decay") == "run_decay_base"

    def test_human_apply_bumps_version_updates_baseline_and_marks_applied(
        self, decayed_cat
    ):
        def evaluator(strategy_id, params, data):
            return {"oos_sharpe_ratio_mean": 2.5, "oos_max_drawdown_mean": 0.1}

        report = StrategyOptimizationJob(
            decayed_cat, wf_evaluator=evaluator
        ).run("strat_decay", {"top_n": 10, "grid_spec": {"top_n": [5, 10]}})
        assert report.status == STATUS_NEEDS_REVIEW

        # ⑥ human confirms via the apply endpoint (new baseline = recent run)
        result = asyncio.run(apply_optimization(
            "strat_decay",
            ApplyOptimizationBody(
                best_params={"top_n": 20}, confirm=True,
                baseline_run_id="run_decay_recent",
            ),
            decayed_cat,
        ))

        # ⑦ version snapshot created (old config preserved for rollback)
        versions = decayed_cat.query(
            "SELECT config_text FROM meta_strategy_versions WHERE strategy_id = 'strat_decay'"
        )
        assert versions.height == 1
        old_cfg = json.loads(versions["config_text"][0])
        assert old_cfg["top_n"] == 10  # snapshot is the pre-apply config

        # new config contains best_params; other keys preserved
        parsed = _get_parsed(decayed_cat, "strat_decay")
        assert parsed["top_n"] == 20
        assert parsed["rebalance_freq"] == "weekly"

        # baseline_run_id updated (explicit new baseline run supplied)
        assert result["status"] == "applied"
        assert result["baseline_run_id"] == "run_decay_recent"
        assert get_baseline_run_id(decayed_cat, "strat_decay") == "run_decay_recent"

        # report marked applied
        df = decayed_cat.query(
            "SELECT status FROM gold_optimization_reports WHERE strategy_id = 'strat_decay'"
        )
        assert df["status"][0] == "applied"


# ── 场景 3: report query returns the latest report ────────────────────────────


class TestScenario3ReportQuery:
    def test_get_latest_report(self, decayed_cat):
        def evaluator(strategy_id, params, data):
            if params == {"top_n": 10}:
                return {"oos_sharpe_ratio_mean": 2.5}
            return {"oos_sharpe_ratio_mean": 1.8}

        StrategyOptimizationJob(decayed_cat, wf_evaluator=evaluator).run(
            "strat_decay", {"top_n": 10, "grid_spec": {"top_n": [5, 10]}}
        )
        payload = asyncio.run(get_optimization_report("strat_decay", decayed_cat))
        assert payload["strategy_id"] == "strat_decay"
        assert payload["status"] == STATUS_NEEDS_REVIEW
        assert payload["best_params"] == {"top_n": 10}
        assert payload["baseline_metrics"]["oos_sharpe_mean"] == pytest.approx(2.0)
        assert payload["overfit_check"] is not None

    def test_no_report_404(self, decayed_cat):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(get_optimization_report("strat_decay", decayed_cat))
        assert exc.value.status_code == 404


# ── 场景 4: guards — no confirm / non-reviewable status ───────────────────────


class TestScenario4Guards:
    def test_apply_without_confirm_rejected(self, decayed_cat):
        def evaluator(strategy_id, params, data):
            return {"oos_sharpe_ratio_mean": 2.5}

        StrategyOptimizationJob(decayed_cat, wf_evaluator=evaluator).run(
            "strat_decay", {"top_n": 10, "grid_spec": {"top_n": [5, 10]}}
        )
        with pytest.raises(HTTPException) as exc:
            asyncio.run(apply_optimization(
                "strat_decay",
                ApplyOptimizationBody(best_params={"top_n": 20}, confirm=False),
                decayed_cat,
            ))
        assert exc.value.status_code == 400
        # config untouched after rejection
        assert _get_parsed(decayed_cat, "strat_decay")["top_n"] == 10

    def test_apply_non_reviewable_status_409(self, healthy_cat):
        """skipped_healthy report is not reviewable → 409."""
        StrategyOptimizationJob(
            healthy_cat,
            wf_evaluator=lambda *a: {"oos_sharpe_ratio_mean": 9.0},
        ).run("strat_ok", {"top_n": 10})
        with pytest.raises(HTTPException) as exc:
            asyncio.run(apply_optimization(
                "strat_ok",
                ApplyOptimizationBody(best_params={"top_n": 20}, confirm=True),
                healthy_cat,
            ))
        assert exc.value.status_code == 409

    def test_reapply_after_applied_is_idempotent_no_new_needs_review(
        self, decayed_cat
    ):
        """Applied reports may be re-applied (idempotent by design) — the
        UPDATE only touches status='needs_review' rows, and no report ever
        regresses from 'applied'."""
        def evaluator(strategy_id, params, data):
            return {"oos_sharpe_ratio_mean": 2.5}

        StrategyOptimizationJob(decayed_cat, wf_evaluator=evaluator).run(
            "strat_decay", {"top_n": 10, "grid_spec": {"top_n": [5, 10]}}
        )
        asyncio.run(apply_optimization(
            "strat_decay",
            ApplyOptimizationBody(best_params={"top_n": 20}, confirm=True),
            decayed_cat,
        ))
        # second apply — allowed, stays applied
        result = asyncio.run(apply_optimization(
            "strat_decay",
            ApplyOptimizationBody(best_params={"top_n": 20}, confirm=True),
            decayed_cat,
        ))
        assert result["status"] == "applied"
        statuses = decayed_cat.query(
            "SELECT status FROM gold_optimization_reports WHERE strategy_id = 'strat_decay'"
        )["status"].to_list()
        assert set(statuses) == {"applied"}
