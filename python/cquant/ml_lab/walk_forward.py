"""cquant.ml_lab.walk_forward — Rolling walk-forward validation."""

from __future__ import annotations

from datetime import timedelta

import polars as pl

from cquant.ml_lab.datasets import MLDataset


class WalkForwardValidator:
    """Generate rolling train / validation splits without look-ahead leakage.

    Usage::

        validator = WalkForwardValidator(n_splits=5, gap_days=5)
        for train_df, valid_df in validator.split(dataset):
            artifact = trainer.fit(train_df, valid_df, config)
    """

    def __init__(
        self,
        n_splits: int = 5,
        gap_days: int = 0,
        purge_window: int = 0,
        date_column: str = "trade_date",
    ) -> None:
        if n_splits < 1:
            raise ValueError("n_splits must be >= 1")
        if gap_days < 0:
            raise ValueError("gap_days must be >= 0")
        if purge_window < 0:
            raise ValueError("purge_window must be >= 0")
        self.n_splits = n_splits
        self.gap_days = gap_days
        self.purge_window = purge_window
        self.date_column = date_column

    def split(
        self, dataset: "MLDataset | pl.DataFrame"
    ) -> list[tuple[pl.DataFrame, pl.DataFrame]]:
        """Return time-ordered (train_df, valid_df) splits.

        Each successive split extends the training window by one period.
        A gap of *gap_days* calendar days is excluded between train and
        validation to prevent target leakage from lookahead features.
        """
        frame = dataset.data if isinstance(dataset, MLDataset) else dataset
        if self.date_column not in frame.columns:
            raise ValueError(f"Date column '{self.date_column}' not found in DataFrame")

        unique_dates = sorted(frame.get_column(self.date_column).unique().to_list())
        if len(unique_dates) <= self.n_splits:
            raise ValueError(
                f"Dataset has {len(unique_dates)} unique dates but n_splits={self.n_splits}; "
                "reduce n_splits or provide more data"
            )

        valid_window = max(1, len(unique_dates) // (self.n_splits + 1))
        initial_train_periods = len(unique_dates) - valid_window * self.n_splits
        if initial_train_periods < 1:
            raise ValueError(
                "Dataset too small for the requested walk-forward configuration; "
                "reduce n_splits or gap_days"
            )

        splits: list[tuple[pl.DataFrame, pl.DataFrame]] = []
        for i in range(self.n_splits):
            valid_start_idx = initial_train_periods + i * valid_window
            valid_end_idx = min(valid_start_idx + valid_window - 1, len(unique_dates) - 1)

            valid_start = unique_dates[valid_start_idx]
            valid_end = unique_dates[valid_end_idx]
            train_cutoff = valid_start - timedelta(days=self.gap_days)
            if self.purge_window > 0:
                purge_cutoff = valid_start - timedelta(days=self.purge_window)
                effective_cutoff = min(train_cutoff, purge_cutoff)
                train_df = frame.filter(pl.col(self.date_column) < effective_cutoff)
            else:
                train_df = frame.filter(pl.col(self.date_column) < train_cutoff)
            valid_df = frame.filter(
                (pl.col(self.date_column) >= valid_start)
                & (pl.col(self.date_column) <= valid_end)
            )

            if train_df.is_empty():
                raise ValueError(
                    f"Split {i}: empty training set. "
                    "Try reducing gap_days or n_splits."
                )
            if valid_df.is_empty():
                raise ValueError(f"Split {i}: empty validation set")

            splits.append((_sorted(train_df, self.date_column), _sorted(valid_df, self.date_column)))

        return splits


def _sorted(frame: pl.DataFrame, date_column: str) -> pl.DataFrame:
    sort_cols = [date_column] + (["asset_id"] if "asset_id" in frame.columns else [])
    return frame.sort(sort_cols)
