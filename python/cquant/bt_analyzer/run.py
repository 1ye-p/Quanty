"""cquant.bt_analyzer.run — Backtest analysis runner with DuckDB persistence.

Loads backtest results, runs AnalysisEngine, persists results to gold tables.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from cquant.backtest_vector.engine import BacktestResult
from cquant.bt_analyzer.engine import AnalysisEngine
from cquant.bt_analyzer.models import AnalysisReport, AnalysisSpec
from cquant.datahub.catalog import Catalog

logger = logging.getLogger(__name__)


@dataclass
class AnalysisRunSpec:
    """Specification for a backtest analysis run."""

    backtest_run_id: str
    n_oos_windows: int = 5
    oos_fraction: float = 0.2
    n_splits: int = 6
    n_test_splits: int = 2
    benchmark_sharpe: float = 0.0
    n_trials: int = 1
    alpha: float = 0.05


class AnalysisRunner:
    """Run backtest robustness analysis and persist results.

    Usage::

        runner = AnalysisRunner(catalog)
        report = runner.run(backtest_result, AnalysisRunSpec(
            backtest_run_id="...",
        ))
    """

    def __init__(self, catalog: Catalog) -> None:
        self._catalog = catalog

    def run(self, result: BacktestResult, spec: AnalysisRunSpec | None = None) -> AnalysisReport:
        """Execute analysis and persist results. Returns AnalysisReport."""
        self._catalog.initialize()

        analysis_spec = AnalysisSpec(
            n_oos_windows=spec.n_oos_windows if spec else 5,
            oos_fraction=spec.oos_fraction if spec else 0.2,
            n_splits=spec.n_splits if spec else 6,
            n_test_splits=spec.n_test_splits if spec else 2,
            benchmark_sharpe=spec.benchmark_sharpe if spec else 0.0,
            n_trials=spec.n_trials if spec else 1,
            alpha=spec.alpha if spec else 0.05,
        )

        engine = AnalysisEngine(analysis_spec)
        report = engine.run(result)

        self._persist_analysis_run(report)
        self._persist_validation_windows(report)
        self._persist_multiple_testing(report)
        self._persist_tca(report)
        self._persist_attribution(report)

        logger.info(
            "Analysis complete: run_id=%s, overfit_score=%.2f, psr=%.2f, dsr=%.2f",
            report.analysis_run_id,
            report.overall_overfit_score.score,
            report.psr,
            report.dsr,
        )
        return report

    def _persist_analysis_run(self, report: AnalysisReport) -> None:
        """Write analysis run metadata to gold_bt_analysis_runs."""
        conn = self._catalog._get_conn()
        conn.execute(
            """
            INSERT OR REPLACE INTO gold_bt_analysis_runs
                (analysis_run_id, backtest_run_id, overall_overfit_score, dsr, psr, summary, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                report.analysis_run_id,
                report.backtest_run_id,
                report.overall_overfit_score.score,
                report.dsr,
                report.psr,
                report.summary,
                report.created_at.isoformat(),
            ],
        )

    def _persist_validation_windows(self, report: AnalysisReport) -> None:
        """Write walk-forward and CPCV windows to gold_bt_validation_windows."""
        windows = []

        for w in report.walk_forward_windows:
            windows.append({
                "analysis_run_id": report.analysis_run_id,
                "window_id": w.window_id,
                "method": "walk_forward",
                "train_start": w.train_start.isoformat(),
                "train_end": w.train_end.isoformat(),
                "test_start": w.test_start.isoformat(),
                "test_end": w.test_end.isoformat(),
                "metrics_json": json.dumps(w.metrics),
            })

        if report.cpcv_windows:
            for w in report.cpcv_windows:
                windows.append({
                    "analysis_run_id": report.analysis_run_id,
                    "window_id": w.window_id,
                    "method": "cpcv",
                    "train_start": w.train_start.isoformat(),
                    "train_end": w.train_end.isoformat(),
                    "test_start": w.test_start.isoformat(),
                    "test_end": w.test_end.isoformat(),
                    "metrics_json": json.dumps(w.metrics),
                })

        if not windows:
            return

        import polars as pl

        df = pl.DataFrame(windows)
        conn = self._catalog._get_conn()
        rows = df.rows()
        assert not rows or len(rows[0]) == 8, (
            f"Column mismatch: {len(rows[0])} values vs 8 placeholders"
        )
        try:
            conn.executemany(
                """
                INSERT OR REPLACE INTO gold_bt_validation_windows
                    (analysis_run_id, window_id, method, train_start, train_end,
                     test_start, test_end, metrics_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        except Exception as exc:
            logger.warning("Failed to persist validation windows: %s", exc)

    def _persist_multiple_testing(self, report: AnalysisReport) -> None:
        """Write multiple testing results to gold_bt_multiple_testing."""
        mt = report.multiple_testing_result
        conn = self._catalog._get_conn()
        conn.execute(
            """
            INSERT OR REPLACE INTO gold_bt_multiple_testing
                (analysis_run_id, method, n_trials, alpha, results_json, accepted)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                report.analysis_run_id,
                mt.get("method", "holm"),
                mt.get("n_trials", 1),
                mt.get("alpha", 0.05),
                json.dumps(mt),
                mt.get("accepted", False),
            ],
        )

    def _persist_tca(self, report: AnalysisReport) -> None:
        """Write TCA summary to gold_bt_tca."""
        if not report.tca_summary:
            return
        conn = self._catalog._get_conn()
        conn.execute(
            """
            INSERT OR REPLACE INTO gold_bt_tca
                (analysis_run_id, total_turnover, total_commission, total_stamp_duty,
                 total_slippage, total_cost, cost_per_trade, cost_pct_turnover,
                 num_trades, avg_trade_size)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                report.analysis_run_id,
                report.tca_summary.total_turnover,
                report.tca_summary.total_commission,
                report.tca_summary.total_stamp_duty,
                report.tca_summary.total_slippage,
                report.tca_summary.total_cost,
                report.tca_summary.cost_per_trade,
                report.tca_summary.cost_as_pct_turnover,
                report.tca_summary.num_trades,
                report.tca_summary.avg_trade_size,
            ],
        )

    def _persist_attribution(self, report: AnalysisReport) -> None:
        """Write Brinson attribution to gold_bt_attribution."""
        if not report.brinson_attribution:
            return
        conn = self._catalog._get_conn()
        br = report.brinson_attribution
        conn.execute(
            """
            INSERT OR REPLACE INTO gold_bt_attribution
                (analysis_run_id, total_return, benchmark_return, active_return,
                 allocation_effect, selection_effect, interaction_effect,
                 daily_json, sector_details_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                report.analysis_run_id,
                br.total_return,
                report.benchmark_return if report.benchmark_return is not None else None,
                report.active_return if report.active_return is not None else None,
                br.allocation_effect,
                br.selection_effect,
                br.interaction_effect,
                json.dumps(report.brinson_daily or []),
                json.dumps(br.sector_details),
            ],
        )
