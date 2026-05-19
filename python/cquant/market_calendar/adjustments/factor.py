"""cquant.market_calendar.adjustments.factor — Corporate action adjustment factors.

Adjustment factors convert raw (unadjusted) prices to forward- or backward-
adjusted prices for backtesting and factor research.

Forward adjustment (前复权): Scales historical prices downward relative to the
latest price, so that recent prices are unadjusted and older prices are reduced.
This is the standard method for backtesting strategies.

Backward adjustment (后复权): Scales historical prices upward relative to the
IPO price, so that the IPO price is used as the base. Useful for long-term
total-return charting.
"""

from __future__ import annotations

import logging
from datetime import date

import polars as pl

from cquant.core.enums import AdjMethod
from cquant.core.types import Asset

logger = logging.getLogger(__name__)


class AdjustmentFactor:
    """Retrieves and applies corporate action adjustment factors.

    The underlying data is loaded from the Silver DuckDB layer on demand.
    For offline / test use, factors can be injected directly via
    ``inject_factors()``.
    """

    def __init__(self) -> None:
        # Internal cache: asset_id → DataFrame with columns
        # [trade_date: date, adj_factor: f64, source: str]
        self._cache: dict[str, pl.DataFrame] = {}

    def inject_factors(self, asset_id: str, factors: pl.DataFrame) -> None:
        """Inject pre-loaded adjustment factor data for testing or offline use.

        *factors* must have columns: [trade_date (date), adj_factor (f64)].
        """
        required = {"trade_date", "adj_factor"}
        missing = required - set(factors.columns)
        if missing:
            raise ValueError(f"factors DataFrame missing columns: {missing}")
        self._cache[asset_id] = factors.sort("trade_date")

    def get_factor(
        self,
        asset: Asset,
        ref_date: date,
        method: AdjMethod = AdjMethod.FORWARD,
    ) -> pl.DataFrame:
        """Return a DataFrame of adjustment factors for *asset* up to *ref_date*.

        Columns: [trade_date (date), adj_factor (f64)]

        For AdjMethod.NONE, returns a DataFrame of all-1.0 factors (no adjustment).

        Note: This method returns the raw factor series.  To apply adjustments
        to a price DataFrame, use ``apply_to_prices()``.
        """
        if method == AdjMethod.NONE:
            return pl.DataFrame(
                {"trade_date": [ref_date], "adj_factor": [1.0]},
                schema={"trade_date": pl.Date, "adj_factor": pl.Float64},
            )

        if asset.asset_id not in self._cache:
            logger.warning(
                "No adjustment factors loaded for %s; returning identity factor.",
                asset.asset_id,
            )
            return pl.DataFrame(
                {"trade_date": [ref_date], "adj_factor": [1.0]},
                schema={"trade_date": pl.Date, "adj_factor": pl.Float64},
            )

        df = self._cache[asset.asset_id].filter(pl.col("trade_date") <= ref_date)

        if method == AdjMethod.FORWARD:
            # Normalize so the latest factor == 1.0 (prices look "current")
            latest = df.select(pl.col("adj_factor").last()).item()
            if latest and latest != 0:
                df = df.with_columns((pl.col("adj_factor") / latest).alias("adj_factor"))

        return df

    def apply_to_prices(
        self,
        prices: pl.DataFrame,
        asset: Asset,
        method: AdjMethod = AdjMethod.FORWARD,
        price_cols: list[str] | None = None,
    ) -> pl.DataFrame:
        """Apply adjustment factors to *prices* in-place (returns new DataFrame).

        *prices* must have a ``trade_date`` (date) column.
        *price_cols* defaults to ['open', 'high', 'low', 'close'].
        """
        if method == AdjMethod.NONE:
            return prices

        cols = price_cols or ["open", "high", "low", "close"]
        max_date = prices["trade_date"].max()
        factors = self.get_factor(asset, max_date, method)  # type: ignore[arg-type]

        joined = prices.join(
            factors.select(["trade_date", "adj_factor"]),
            on="trade_date",
            how="left",
        ).with_columns(pl.col("adj_factor").fill_null(1.0))

        for col in cols:
            if col in joined.columns:
                joined = joined.with_columns(
                    (pl.col(col) * pl.col("adj_factor")).alias(col)
                )

        return joined.drop("adj_factor")
