"""cquant.factorlab.universe.builder — Universe construction from price data."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date

import polars as pl

from cquant.core.enums import Exchange
from cquant.core.errors import FactorComputeError

logger = logging.getLogger(__name__)


@dataclass
class UniverseSpec:
    """Configuration for universe construction."""

    universe_id: str
    exchanges: list[Exchange] = field(default_factory=lambda: [Exchange.SSE, Exchange.SZSE])
    # Liquidity filter: minimum average daily turnover over the lookback window
    min_avg_amount: float = 1_000_000.0   # CNY 100万
    liquidity_lookback_days: int = 20
    # Exclude suspended stocks
    exclude_suspended: bool = True
    # Exclude ST/*ST stocks
    exclude_st: bool = True
    # Maximum number of assets (None = all passing filters)
    top_n: int | None = None


class UniverseBuilder:
    """Builds a tradeable universe from Silver price data.

    Usage::

        builder = UniverseBuilder()
        spec = UniverseSpec(universe_id="cn_liquid_top500", top_n=500)
        membership = builder.build(prices_df, spec, as_of_date=date(2026, 5, 9))
    """

    def build(
        self,
        prices: pl.DataFrame,
        spec: UniverseSpec,
        as_of_date: date,
    ) -> pl.DataFrame:
        """Return universe membership DataFrame for *as_of_date*.

        *prices* must have columns: [asset_id, trade_date, close, amount, is_suspended].

        Returns a DataFrame with columns: [universe_id, trade_date, asset_id].
        """
        required = {"asset_id", "trade_date", "close", "amount", "is_suspended"}
        missing = required - set(prices.columns)
        if missing:
            raise FactorComputeError(f"prices DataFrame missing columns: {missing}")

        # Filter to lookback window
        lookback_start = self._offset_date(as_of_date, spec.liquidity_lookback_days)
        window = prices.filter(
            (pl.col("trade_date") >= lookback_start)
            & (pl.col("trade_date") <= as_of_date)
        )

        if window.is_empty():
            logger.warning("No price data in lookback window for %s", as_of_date)
            return pl.DataFrame(
                schema={"universe_id": pl.Utf8, "trade_date": pl.Date, "asset_id": pl.Utf8}
            )

        # Compute average daily amount per asset
        avg_amount = (
            window.group_by("asset_id")
            .agg(pl.col("amount").mean().alias("avg_amount"))
        )

        # Suspension filter: exclude assets suspended on as_of_date
        today_data = prices.filter(pl.col("trade_date") == as_of_date)

        candidates = avg_amount.filter(pl.col("avg_amount") >= spec.min_avg_amount)

        if spec.exclude_suspended and "is_suspended" in today_data.columns:
            suspended = today_data.filter(pl.col("is_suspended"))["asset_id"].to_list()
            candidates = candidates.filter(~pl.col("asset_id").is_in(suspended))

        # Exchange filter
        if spec.exchanges:
            exchange_prefixes = [e.value + ":" for e in spec.exchanges]
            candidates = candidates.filter(
                pl.col("asset_id").map_elements(
                    lambda aid: any(aid.startswith(p) for p in exchange_prefixes),
                    return_dtype=pl.Boolean,
                )
            )

        # Sort by liquidity and optionally cap to top_n
        candidates = candidates.sort("avg_amount", descending=True)
        if spec.top_n is not None:
            candidates = candidates.head(spec.top_n)

        return candidates.with_columns(
            pl.lit(spec.universe_id).alias("universe_id"),
            pl.lit(as_of_date).cast(pl.Date).alias("trade_date"),
        ).select(["universe_id", "trade_date", "asset_id"])

    @staticmethod
    def _offset_date(d: date, n_days: int) -> date:
        """Approximate calendar offset (not trading-day aware)."""
        from datetime import timedelta
        return d - timedelta(days=n_days * 2)  # Double to account for weekends/holidays
