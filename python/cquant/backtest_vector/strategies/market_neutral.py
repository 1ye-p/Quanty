"""Market-neutral strategy — long top-N, short bottom-N by factor rank."""
from __future__ import annotations

import logging

import polars as pl

from cquant.backtest_vector.strategy import Strategy, StrategyContext
from cquant.core.types import SignalFrame

logger = logging.getLogger(__name__)


class MarketNeutralStrategy(Strategy):
    """Zero-net-exposure strategy: long top-N assets, short bottom-N by factor rank.

    Parameters
    ----------
    strategy_id:
        Unique identifier.
    factor_col:
        Factor column in ``ctx.features`` (default ``"ret_20d"``).
    top_n:
        Assets to buy (long leg).
    short_n:
        Assets to sell short (short leg).
    """

    def __init__(
        self,
        strategy_id: str,
        factor_col: str = "ret_20d",
        top_n: int = 10,
        short_n: int = 10,
    ) -> None:
        self._strategy_id = strategy_id
        self._factor_col = factor_col
        self._top_n = top_n
        self._short_n = short_n

    @property
    def strategy_id(self) -> str:
        return self._strategy_id

    def generate_signals(self, ctx: StrategyContext) -> SignalFrame:
        if ctx.features is None or ctx.features.is_empty():
            return _empty_frame()

        day = ctx.features.filter(pl.col("trade_date") == ctx.as_of_date)
        if day.is_empty() or self._factor_col not in day.columns:
            return _empty_frame()

        ranked = (
            day.drop_nulls([self._factor_col])
            .sort(self._factor_col, descending=True)
        )

        if ranked.is_empty():
            return _empty_frame()

        # Long leg: top-N
        longs = ranked.head(self._top_n)
        long_n = len(longs)

        # Short leg: bottom-N (excluding assets already in longs)
        long_set = set(longs["asset_id"].to_list())
        shorts = ranked.tail(self._short_n).filter(~pl.col("asset_id").is_in(long_set))
        short_n = len(shorts)

        if short_n == 0 and len(ranked) > 0:
            logger.debug(
                "MarketNeutralStrategy '%s': insufficient assets for short leg "
                "(have %d, need %d long + %d short). Degenerating to long-only.",
                self._strategy_id, len(ranked), self._top_n, self._short_n,
            )

        rows: list[dict] = []
        for asset in longs["asset_id"].to_list():
            rows.append({
                "asset_id": asset,
                "signal_date": ctx.as_of_date,
                "direction": "long",
                "strength": 1.0 / long_n if long_n > 0 else 1.0,
                "confidence": 1.0,
            })
        for asset in shorts["asset_id"].to_list():
            rows.append({
                "asset_id": asset,
                "signal_date": ctx.as_of_date,
                "direction": "short",
                "strength": 1.0 / short_n if short_n > 0 else 1.0,
                "confidence": 1.0,
            })

        return pl.DataFrame(rows) if rows else _empty_frame()


def _empty_frame() -> SignalFrame:
    return pl.DataFrame(
        schema={
            "asset_id": pl.Utf8,
            "signal_date": pl.Date,
            "direction": pl.Utf8,
            "strength": pl.Float64,
            "confidence": pl.Float64,
        }
    )
