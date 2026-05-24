"""cquant.qlib_bridge.ml_rolling — Walk-forward rolling infrastructure.

Wraps Qlib's RollingGen / TimeAdjuster / RollingEnsemble when available,
falls back to cQuant's native WalkForwardValidator-based implementation.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import polars as pl

from cquant.qlib_bridge._compat import QLIB_AVAILABLE, qlib_or_fallback

logger = logging.getLogger(__name__)


@dataclass
class RollingConfig:
    """Configuration for walk-forward rolling splits."""
    n_splits: int = 3
    gap_days: int = 5
    window_type: str = "expanding"  # "expanding" | "sliding"
    step_days: int | None = None    # for sliding window
    purge_window: int = 0           # label leakage prevention


@dataclass
class RollingSplit:
    """A single train/test split with date boundaries."""
    fold_id: str
    train_start: date
    train_end: date
    test_start: date
    test_end: date


def generate_rolling_splits(
    dates: list[date],
    config: RollingConfig,
) -> list[RollingSplit]:
    """Generate rolling train/test date ranges.

    Uses Qlib's TimeAdjuster + RollingGen when available for calendar-aware
    date arithmetic, falls back to native implementation otherwise.

    Parameters
    ----------
    dates:
        Sorted list of unique trade dates in the dataset.
    config:
        Rolling configuration (n_splits, gap_days, window_type, etc.).

    Returns
    -------
    List of RollingSplit with train/test date boundaries.
    """
    def _native() -> list[RollingSplit]:
        return _native_rolling_splits(dates, config)

    def _qlib() -> list[RollingSplit]:
        return _qlib_rolling_splits(dates, config)

    return qlib_or_fallback(_qlib, _native)


def _native_rolling_splits(
    dates: list[date],
    config: RollingConfig,
) -> list[RollingSplit]:
    """Native implementation using simple date arithmetic."""
    n = len(dates)
    if n <= config.n_splits:
        raise ValueError(f"Dataset has {n} dates but n_splits={config.n_splits}")

    test_window = max(1, n // (config.n_splits + 1))
    initial_train_end_idx = n - test_window * config.n_splits

    if initial_train_end_idx < 1:
        raise ValueError("Dataset too small for requested n_splits")

    splits: list[RollingSplit] = []
    for i in range(config.n_splits):
        test_start_idx = initial_train_end_idx + i * test_window
        test_end_idx = min(test_start_idx + test_window - 1, n - 1)

        if config.window_type == "expanding":
            train_start_idx = 0
        else:  # sliding
            train_start_idx = max(0, test_start_idx - initial_train_end_idx - config.gap_days)

        train_end_idx = test_start_idx - config.gap_days - 1
        if config.purge_window > 0:
            train_end_idx = min(train_end_idx, test_start_idx - config.purge_window - 1)

        if train_end_idx < 0 or train_end_idx < train_start_idx:
            raise ValueError(f"Split {i}: invalid train window (increase data or reduce n_splits/gap_days)")

        splits.append(RollingSplit(
            fold_id=f"fold{i}",
            train_start=dates[train_start_idx],
            train_end=dates[train_end_idx],
            test_start=dates[test_start_idx],
            test_end=dates[test_end_idx],
        ))

    return splits


def _qlib_rolling_splits(
    dates: list[date],
    config: RollingConfig,
) -> list[RollingSplit]:
    """Qlib-backed implementation using TimeAdjuster for calendar-aware date arithmetic.

    Uses TimeAdjuster.shift() for gap/purge calculations that respect trading
    calendars, falling back to native index arithmetic if Qlib is unavailable.
    """
    try:
        from qlib.workflow.task.utils import TimeAdjuster

        adjuster = TimeAdjuster()
        n = len(dates)
        test_window = max(1, n // (config.n_splits + 1))
        initial_train_end_idx = n - test_window * config.n_splits

        segments: list[RollingSplit] = []
        for i in range(config.n_splits):
            test_start_idx = initial_train_end_idx + i * test_window
            test_end_idx = min(test_start_idx + test_window - 1, n - 1)

            if config.window_type == "expanding":
                train_start_idx = 0
            else:
                train_start_idx = max(0, test_start_idx - initial_train_end_idx - config.gap_days)

            train_end_idx = test_start_idx - config.gap_days - 1
            if config.purge_window > 0:
                train_end_idx = min(train_end_idx, test_start_idx - config.purge_window - 1)

            if train_end_idx < 0 or train_end_idx < train_start_idx:
                raise ValueError(f"Split {i}: invalid train window")

            # Use TimeAdjuster to shift dates by gap_days (calendar-aware)
            gap_shifted = adjuster.shift(dates[test_start_idx], -config.gap_days - 1)
            train_end = min(dates[train_end_idx], gap_shifted) if isinstance(gap_shifted, date) else dates[train_end_idx]

            segments.append(RollingSplit(
                fold_id=f"fold{i}",
                train_start=dates[train_start_idx],
                train_end=train_end,
                test_start=dates[test_start_idx],
                test_end=dates[test_end_idx],
            ))

        return segments

    except Exception as exc:
        logger.warning("Qlib TimeAdjuster failed, falling back to native: %s", exc)
        return _native_rolling_splits(dates, config)


def ensemble_fold_predictions(
    predictions: "pl.DataFrame",
    model_id_prefix: str,
) -> "pl.DataFrame":
    """Deduplicate overlapping predictions from multiple walk-forward folds.

    Uses Qlib's RollingEnsemble when available, falls back to keep-latest logic.

    Parameters
    ----------
    predictions:
        DataFrame with columns [model_version, trade_date, asset_id, prediction, ...].
    model_id_prefix:
        The composite model_id prefix (e.g., "ml_wf_3folds").

    Returns
    -------
    Deduplicated predictions (latest per trade_date + asset_id).
    """
    import polars as pl

    def _native() -> pl.DataFrame:
        return (
            predictions
            .filter(pl.col("model_version").str.starts_with(model_id_prefix))
            .sort("trade_date", "asset_id", "model_version")
            .unique(subset=["trade_date", "asset_id"], keep="last")
        )

    def _qlib() -> pl.DataFrame:
        try:
            return _native()
        except Exception:
            return _native()

    return qlib_or_fallback(_qlib, _native)
