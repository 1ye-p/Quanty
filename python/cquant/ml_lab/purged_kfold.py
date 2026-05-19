"""Purged K-Fold cross-validation for time-series ML.

Prevents information leakage by:
1. Purging: removing training samples whose target window overlaps the validation period
2. Embargo: adding a gap between train and validation sets
"""
from __future__ import annotations

from datetime import timedelta

import polars as pl


class PurgedKFold:
    """Purged K-Fold cross-validation for time-series data.

    Parameters:
        n_splits: Number of folds.
        purge_window: Number of calendar days to purge before validation start.
        embargo_days: Number of calendar days to embargo after validation end.
        date_column: Column name for dates.
    """

    def __init__(
        self,
        n_splits: int = 5,
        purge_window: int = 0,
        embargo_days: int = 0,
        date_column: str = "trade_date",
    ) -> None:
        if n_splits < 2:
            raise ValueError("n_splits must be >= 2")
        if purge_window < 0:
            raise ValueError("purge_window must be >= 0")
        if embargo_days < 0:
            raise ValueError("embargo_days must be >= 0")
        self.n_splits = n_splits
        self.purge_window = purge_window
        self.embargo_days = embargo_days
        self.date_column = date_column

    def split(
        self, dataset: "pl.DataFrame",
    ) -> list[tuple[pl.DataFrame, pl.DataFrame]]:
        """Return purged (train_df, valid_df) splits."""
        frame = dataset
        if self.date_column not in frame.columns:
            raise ValueError(f"Date column '{self.date_column}' not found")

        unique_dates = sorted(frame.get_column(self.date_column).unique().to_list())
        n_dates = len(unique_dates)
        if n_dates <= self.n_splits:
            raise ValueError(
                f"Dataset has {n_dates} unique dates but n_splits={self.n_splits}"
            )

        fold_size = n_dates // self.n_splits
        splits: list[tuple[pl.DataFrame, pl.DataFrame]] = []

        for i in range(self.n_splits):
            valid_start_idx = i * fold_size
            valid_end_idx = min(valid_start_idx + fold_size - 1, n_dates - 1)
            if i == self.n_splits - 1:
                valid_end_idx = n_dates - 1

            valid_start = unique_dates[valid_start_idx]
            valid_end = unique_dates[valid_end_idx]

            # Embargo: exclude training data after validation end
            embargo_cutoff = valid_end + timedelta(days=self.embargo_days)
            # Purge: exclude training data before validation start within purge window
            purge_cutoff = valid_start - timedelta(days=self.purge_window)

            train_df = frame.filter(
                (pl.col(self.date_column) < purge_cutoff)
                | (pl.col(self.date_column) > embargo_cutoff)
            )
            valid_df = frame.filter(
                (pl.col(self.date_column) >= valid_start)
                & (pl.col(self.date_column) <= valid_end)
            )

            if train_df.is_empty() or valid_df.is_empty():
                continue

            sort_cols = [self.date_column] + (
                ["asset_id"] if "asset_id" in train_df.columns else []
            )
            splits.append((
                train_df.sort(sort_cols),
                valid_df.sort(sort_cols),
            ))

        if not splits:
            raise ValueError(
                "All splits empty — reduce n_splits, purge_window, or embargo_days"
            )

        return splits
