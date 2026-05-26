"""CustomWeightStrategy — backtest with fixed pre-specified asset weights."""

from __future__ import annotations

import polars as pl

from cquant.backtest_vector.strategy import Strategy, StrategyContext
from cquant.core.types import SignalFrame


class CustomWeightStrategy(Strategy):
    """Use a fixed weight dict {asset_id: weight} as portfolio allocation.

    On each rebalance date emits the specified weights as signals with
    strength proportional to the given weight.
    """

    def __init__(self, strategy_id: str, weights: dict[str, float]) -> None:
        self._strategy_id = strategy_id
        self._weights = {k: float(v) for k, v in weights.items() if float(v) > 0}

    @property
    def strategy_id(self) -> str:
        return self._strategy_id

    def generate_signals(self, ctx: StrategyContext) -> SignalFrame:
        if not self._weights:
            return _empty_frame()
        rows = [
            {
                "asset_id": asset_id,
                "signal_date": ctx.as_of_date,
                "direction": "long",
                "strength": weight,
                "confidence": 1.0,
            }
            for asset_id, weight in self._weights.items()
        ]
        return pl.DataFrame(rows)


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
