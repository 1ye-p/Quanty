"""cquant.ml_lab.preprocessing — Cross-sectional feature preprocessing for ML.

Provides standalone functions that operate on Polars DataFrames with
[asset_id, trade_date, factor1, factor2, ...] format:

- ``cross_sectional_zscore``: z-score normalization per date
- ``winsorize``: clip values to quantile bounds per date
- ``fill_nulls_cross_section``: fill nulls using cross-sectional statistics
"""

from __future__ import annotations

from typing import Sequence

import polars as pl


def cross_sectional_zscore(
    frame: pl.DataFrame,
    columns: Sequence[str],
    date_column: str = "trade_date",
) -> pl.DataFrame:
    """Z-score each column cross-sectionally per date (mean=0, std=1).

    For each date: z = (val - mean) / std.

    Parameters
    ----------
    frame
        DataFrame with ``date_column`` and the specified factor columns.
    columns
        Column names to z-score.
    date_column
        Column used to group cross-sectional slices (default ``"trade_date"``).

    Returns
    -------
    pl.DataFrame
        Same schema as input with specified columns replaced by z-scores.
    """
    exprs = [
        (
            (pl.col(c) - pl.col(c).mean().over(date_column))
            / pl.col(c).std().over(date_column)
        ).alias(c)
        for c in columns
    ]
    return frame.with_columns(exprs)


def winsorize(
    frame: pl.DataFrame,
    columns: Sequence[str],
    lower: float = 0.01,
    upper: float = 0.99,
    date_column: str = "trade_date",
) -> pl.DataFrame:
    """Clip values to quantile bounds per cross-sectional date.

    Parameters
    ----------
    frame
        DataFrame with ``date_column`` and the specified factor columns.
    columns
        Column names to winsorize.
    lower
        Lower quantile bound (default 0.01).
    upper
        Upper quantile bound (default 0.99).
    date_column
        Column used to group cross-sectional slices (default ``"trade_date"``).

    Returns
    -------
    pl.DataFrame
        Same schema as input with specified columns clipped.
    """
    # Compute quantile bounds per date first, then join and clip
    bound_exprs = []
    for c in columns:
        bound_exprs.extend([
            pl.col(c).quantile(lower).alias(f"__lb_{c}"),
            pl.col(c).quantile(upper).alias(f"__ub_{c}"),
        ])
    bounds = frame.group_by(date_column).agg(bound_exprs)
    result = frame.join(bounds, on=date_column, how="left")

    clip_exprs = [
        pl.col(c)
        .clip(
            lower_bound=pl.col(f"__lb_{c}"),
            upper_bound=pl.col(f"__ub_{c}"),
        )
        .alias(c)
        for c in columns
    ]
    drop_cols = [f"__lb_{c}" for c in columns] + [f"__ub_{c}" for c in columns]
    return result.with_columns(clip_exprs).drop(drop_cols)


def fill_nulls_cross_section(
    frame: pl.DataFrame,
    columns: Sequence[str],
    method: str = "median",
    date_column: str = "trade_date",
) -> pl.DataFrame:
    """Fill nulls using cross-sectional statistics per date.

    Parameters
    ----------
    frame
        DataFrame with ``date_column`` and the specified factor columns.
    columns
        Column names to fill.
    method
        Fill strategy: ``'median'``, ``'mean'``, or ``'zero'``.
    date_column
        Column used to group cross-sectional slices (default ``"trade_date"``).

    Returns
    -------
    pl.DataFrame
        Same schema as input with nulls filled.
    """
    if method == "zero":
        return frame.with_columns([pl.col(c).fill_null(0) for c in columns if c in frame.columns])

    if method not in ("median", "mean"):
        raise ValueError(f"Invalid fill method: {method!r}. Expected 'median', 'mean', or 'zero'.")

    exprs = [
        pl.when(pl.col(c).is_null())
        .then(
            (pl.col(c).median() if method == "median" else pl.col(c).mean())
            .over(date_column)
        )
        .otherwise(pl.col(c))
        .alias(c)
        for c in columns
    ]
    return frame.with_columns(exprs)
