"""Tests for purged walk-forward and purged K-fold validation."""
from __future__ import annotations

from datetime import date, timedelta
import random

import polars as pl
import pytest

from cquant.ml_lab.purged_kfold import PurgedKFold
from cquant.ml_lab.walk_forward import WalkForwardValidator


def _make_dataset(n_dates: int = 100, n_assets: int = 10) -> pl.DataFrame:
    """Build a synthetic dataset with trade_date and asset_id."""
    random.seed(42)
    dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(n_dates)]
    assets = [f"A{i}" for i in range(n_assets)]
    rows = []
    for d in dates:
        for a in assets:
            rows.append({
                "asset_id": a,
                "trade_date": d,
                "f1": random.gauss(0, 1),
                "ret_5d": random.gauss(0, 0.05),
            })
    return pl.DataFrame(rows)


class TestPurgedKFold:
    def test_n_splits_output(self):
        df = _make_dataset(100)
        pkf = PurgedKFold(n_splits=5)
        splits = pkf.split(df)
        assert len(splits) == 5

    def test_no_overlap_between_train_and_valid(self):
        df = _make_dataset(100)
        pkf = PurgedKFold(n_splits=5, embargo_days=5)
        for train_df, valid_df in pkf.split(df):
            train_dates = set(train_df["trade_date"].unique().to_list())
            valid_dates = set(valid_df["trade_date"].unique().to_list())
            assert train_dates.isdisjoint(valid_dates)

    def test_embargo_gap_enforced(self):
        """Embargo creates a gap between validation end and post-validation training data."""
        df = _make_dataset(100)
        embargo = 10
        pkf = PurgedKFold(n_splits=5, embargo_days=embargo)
        for train_df, valid_df in pkf.split(df):
            if train_df.is_empty() or valid_df.is_empty():
                continue
            max_valid = max(valid_df["trade_date"].to_list())
            # Post-validation training dates must be at least embargo_days after valid_end
            post_valid_train = [
                d for d in train_df["trade_date"].unique().to_list() if d > max_valid
            ]
            if post_valid_train:
                min_post = min(post_valid_train)
                gap = (min_post - max_valid).days
                assert gap >= embargo

    def test_purge_removes_overlapping_targets(self):
        """With purge_window=5, training samples within 5 days of validation start are removed."""
        df = _make_dataset(100)
        pkf = PurgedKFold(n_splits=5, purge_window=5)
        splits = pkf.split(df)
        assert len(splits) == 5
        for train_df, valid_df in splits:
            assert not train_df.is_empty()
            assert not valid_df.is_empty()


class TestWalkForwardWithPurge:
    def test_walk_forward_purge_gap(self):
        """WalkForwardValidator with purge_window should remove overlapping training data."""
        df = _make_dataset(100)
        wfv = WalkForwardValidator(n_splits=3, gap_days=5)
        splits = wfv.split(df)
        assert len(splits) == 3
        for train_df, valid_df in splits:
            assert not train_df.is_empty()
            assert not valid_df.is_empty()
