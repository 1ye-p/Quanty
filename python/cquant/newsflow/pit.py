"""cquant.newsflow.pit — Point-in-time news availability filter."""

from __future__ import annotations

from datetime import datetime, timezone

import polars as pl

from cquant.core.errors import SchemaValidationError


class PITGate:
    """Filter news events to only those available at a given simulation time.

    Usage::

        gate = PITGate()
        # In backtest: only use news published and available before rebalance date
        visible = gate.filter(silver_news_df, as_of_ts=datetime(2025, 3, 1, tzinfo=timezone.utc))
    """

    def filter(self, frame: pl.DataFrame, as_of_ts: datetime) -> pl.DataFrame:
        """Return rows where available_at <= *as_of_ts*."""
        if "available_at" not in frame.columns:
            raise SchemaValidationError(
                "PITGate.filter() requires an 'available_at' column in the DataFrame"
            )
        utc = as_of_ts if as_of_ts.tzinfo else as_of_ts.replace(tzinfo=timezone.utc)
        utc = utc.astimezone(timezone.utc)
        return frame.filter(
            pl.col("available_at")
            <= pl.lit(utc, dtype=pl.Datetime(time_unit="us", time_zone="UTC"))
        )
