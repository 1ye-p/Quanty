"""Unit tests for gold_wf_folds OOS metrics persistence.

ML-1: per-fold OOS metrics (oos_sharpe / oos_return / oos_max_drawdown /
oos_ic) persisted from WalkForwardResult.folds_df into gold_wf_folds.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import duckdb
import polars as pl
import pytest

from cquant.backtest_vector.run import BacktestRunner, BacktestRunSpec


@pytest.fixture()
def catalog():
    """In-memory DuckDB catalog stub with gold tables + upsert support."""
    conn = duckdb.connect(":memory:")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS gold_backtest_runs (
            run_id VARCHAR PRIMARY KEY, engine VARCHAR, strategy_id VARCHAR,
            dataset_version VARCHAR, started_at VARCHAR, completed_at VARCHAR,
            status VARCHAR
        )
    """)
    cat = MagicMock()
    cat.execute.side_effect = conn.execute

    def upsert(table, columns, rows, keys):
        cols = ", ".join(columns)
        ph = ", ".join(["?"] * len(columns))
        updates = ", ".join(f"{c} = excluded.{c}" for c in columns if c not in keys)
        conn.executemany(
            f"INSERT INTO {table} ({cols}) VALUES ({ph}) "
            f"ON CONFLICT ({', '.join(keys)}) DO UPDATE SET {updates}",
            rows,
        )

    cat.upsert.side_effect = upsert
    yield cat, conn
    conn.close()


def _make_fold_results():
    return [
        {
            "fold_id": 1,
            "train_start": "2024-01-01", "train_end": "2024-06-30",
            "test_start": "2024-07-01", "test_end": "2024-09-30",
            "run_id": "fold-run-1",
            "oos_sharpe": 1.23, "oos_return": 0.15,
            "oos_max_drawdown": -0.08, "oos_ic": 0.05,
        },
        {
            "fold_id": 2,
            "train_start": "2024-04-01", "train_end": "2024-09-30",
            "test_start": "2024-10-01", "test_end": "2024-12-31",
            "run_id": "fold-run-2",
            "oos_sharpe": 0.87, "oos_return": 0.09,
            "oos_max_drawdown": -0.12, "oos_ic": 0.03,
        },
    ]


def _make_spec() -> BacktestRunSpec:
    return BacktestRunSpec(
        dataset_version="test_v1",
        strategy_id="test_wf",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        initial_cash=Decimal("1_000_000"),
    )


class TestPersistWalkForwardOosMetrics:
    def test_persist_writes_oos_metrics(self, catalog):
        cat, conn = catalog
        runner = BacktestRunner.__new__(BacktestRunner)
        runner._catalog = cat

        run_id = runner._persist_walk_forward_result(
            _make_spec(), _make_fold_results(), {}
        )

        rows = conn.execute(
            "SELECT fold_id, oos_sharpe, oos_return, oos_max_drawdown, oos_ic "
            "FROM gold_wf_folds WHERE run_id = ? ORDER BY fold_id",
            [run_id],
        ).fetchall()
        assert len(rows) == 2
        for row, expected_sharpe in zip(rows, [1.23, 0.87]):
            assert row[1] == pytest.approx(expected_sharpe)
            assert row[2] is not None
            assert row[3] is not None  # max_drawdown
        assert rows[0][4] == pytest.approx(0.05)
        assert rows[1][4] == pytest.approx(0.03)

    def test_ddl_idempotent(self, catalog):
        cat, conn = catalog
        runner = BacktestRunner.__new__(BacktestRunner)
        runner._catalog = cat
        spec, folds = _make_spec(), _make_fold_results()

        runner._persist_walk_forward_result(spec, folds, {})
        # Second call re-runs CREATE TABLE IF NOT EXISTS + ALTERs without error
        runner._persist_walk_forward_result(spec, folds, {})
        count = conn.execute("SELECT COUNT(*) FROM gold_wf_folds").fetchone()[0]
        assert count == 4  # two runs x two folds

    def test_migration_on_legacy_table(self, catalog):
        """Pre-existing gold_wf_folds (old schema) gets oos_* columns via ALTER."""
        cat, conn = catalog
        conn.execute("""
            CREATE TABLE gold_wf_folds (
                run_id VARCHAR, fold_id INTEGER,
                train_start VARCHAR, train_end VARCHAR,
                test_start VARCHAR, test_end VARCHAR,
                fold_run_id VARCHAR, PRIMARY KEY (run_id, fold_id)
            )
        """)
        runner = BacktestRunner.__new__(BacktestRunner)
        runner._catalog = cat

        run_id = runner._persist_walk_forward_result(
            _make_spec(), _make_fold_results(), {}
        )
        row = conn.execute(
            "SELECT oos_sharpe, oos_ic FROM gold_wf_folds "
            "WHERE run_id = ? AND fold_id = 1",
            [run_id],
        ).fetchone()
        assert row[0] == pytest.approx(1.23)
        assert row[1] == pytest.approx(0.05)

    def test_missing_metrics_persist_null(self, catalog):
        """Fold dicts without oos_* keys persist NULLs instead of failing."""
        cat, conn = catalog
        runner = BacktestRunner.__new__(BacktestRunner)
        runner._catalog = cat
        folds = [
            {
                "fold_id": 1,
                "train_start": "2024-01-01", "train_end": "2024-06-30",
                "test_start": "2024-07-01", "test_end": "2024-09-30",
                "run_id": "fold-run-1",
            }
        ]
        runner._persist_walk_forward_result(_make_spec(), folds, {})
        row = conn.execute(
            "SELECT oos_sharpe, oos_return, oos_max_drawdown, oos_ic FROM gold_wf_folds"
        ).fetchone()
        assert row == (None, None, None, None)


class TestExtractOosMetrics:
    def test_maps_test_columns(self):
        folds_df = pl.DataFrame({
            "fold_id": [1, 2],
            "test_sharpe_ratio": [1.5, 0.5],
            "test_total_return": [0.20, 0.05],
            "test_max_drawdown": [-0.10, -0.03],
        })
        m = BacktestRunner._extract_oos_metrics(folds_df, 1)
        assert m["oos_sharpe"] == pytest.approx(1.5)
        assert m["oos_return"] == pytest.approx(0.20)
        assert m["oos_max_drawdown"] == pytest.approx(-0.10)
        assert m["oos_ic"] is None  # no ic column in folds_df

    def test_missing_fold_returns_none(self):
        folds_df = pl.DataFrame({"fold_id": [1], "test_sharpe_ratio": [1.0]})
        m = BacktestRunner._extract_oos_metrics(folds_df, 99)
        assert m == {"oos_sharpe": None, "oos_return": None,
                     "oos_max_drawdown": None, "oos_ic": None}

    def test_empty_df(self):
        m = BacktestRunner._extract_oos_metrics(pl.DataFrame(), 1)
        assert all(v is None for v in m.values())
