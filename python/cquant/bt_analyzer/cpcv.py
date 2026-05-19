"""cquant.bt_analyzer.cpcv — Combinatorial Purged Cross-Validation.

Reference: Lopez de Prado, "Advances in Financial Machine Learning" (2018), Ch.12.

CPCV selects k out of n folds as the test set (combinatorially), purges a gap
around test fold boundaries to prevent leakage, trains on the rest, and evaluates
on the test folds. This produces ≈ C(n, k) independent out-of-sample evaluations.
"""

from __future__ import annotations

from datetime import timedelta
from itertools import combinations

import polars as pl

from cquant.backtest_vector.engine import BacktestResult
from cquant.bt_analyzer.models import AnalysisSpec, ValidationWindow
from cquant.bt_analyzer.walk_forward import _period_metrics


class CPCVAnalyzer:
    """Apply CPCV to a portfolio return series."""

    def __init__(self, spec: AnalysisSpec) -> None:
        if spec.n_splits < 2:
            raise ValueError("n_splits must be >= 2")
        if not (1 <= spec.n_test_splits < spec.n_splits):
            raise ValueError("n_test_splits must satisfy 1 <= n_test_splits < n_splits")
        if spec.gap_days < 0:
            raise ValueError("gap_days must be >= 0")
        self.spec = spec

    def analyze(self, result: BacktestResult) -> list[ValidationWindow]:
        """Return one ValidationWindow per combinatorial test selection."""
        frame = result.portfolio_returns.sort("trade_date")
        if frame.is_empty():
            return []
        dates = frame.get_column("trade_date").to_list()
        if len(dates) <= self.spec.n_splits:
            return []

        bounds = _fold_bounds(len(dates), self.spec.n_splits)
        folds = [dates[s:e] for s, e in bounds]
        windows: list[ValidationWindow] = []

        for wid, test_ids in enumerate(
            combinations(range(len(folds)), self.spec.n_test_splits), start=1
        ):
            test_dates_set = {d for i in test_ids for d in folds[i]}
            train_dates = self._purged_train(folds, set(test_ids))
            if not test_dates_set or not train_dates:
                continue

            test_df = frame.filter(pl.col("trade_date").is_in(list(test_dates_set)))
            if test_df.is_empty():
                continue

            metrics = _period_metrics(
                test_df.get_column("portfolio_return"),
                self.spec.trading_days_per_year,
            )
            metrics["test_fold_count"] = float(len(test_ids))
            metrics["test_observations"] = float(len(test_dates_set))
            metrics["purged_train_observations"] = float(len(train_dates))

            windows.append(
                ValidationWindow(
                    window_id=wid,
                    train_start=min(train_dates),
                    train_end=max(train_dates),
                    test_start=min(test_dates_set),
                    test_end=max(test_dates_set),
                    metrics=metrics,
                )
            )
        return windows

    def _purged_train(self, folds: list[list], test_ids: set[int]) -> list:
        """Return train dates with a gap around each test fold boundary purged."""
        exclusions: list[tuple] = []
        for i in test_ids:
            fd = folds[i]
            if fd:
                exclusions.append((
                    fd[0] - timedelta(days=self.spec.gap_days),
                    fd[-1] + timedelta(days=self.spec.gap_days),
                ))
        result = []
        for i, fold in enumerate(folds):
            if i in test_ids:
                continue
            for d in fold:
                if any(lo <= d <= hi for lo, hi in exclusions):
                    continue
                result.append(d)
        return result


def _fold_bounds(n: int, k: int) -> list[tuple[int, int]]:
    """Return k non-overlapping [start, end) index pairs covering [0, n)."""
    bounds, start = [], 0
    for i in range(k):
        width = n // k + (1 if i < n % k else 0)
        bounds.append((start, start + width))
        start += width
    return bounds
