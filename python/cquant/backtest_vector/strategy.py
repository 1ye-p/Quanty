"""cquant.backtest_vector.strategy — Strategy ABC and context."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date

import polars as pl

from cquant.core.types import SignalFrame


@dataclass
class StrategyContext:
    """Runtime context provided to a strategy during signal generation."""

    as_of_date: date
    universe_id: str
    feature_set_version: str = ""
    features: pl.DataFrame | None = None    # Gold factor values for the universe
    prices: pl.DataFrame | None = None      # Silver OHLCV
    extra: dict = field(default_factory=dict)


class Strategy(ABC):
    """Abstract base for all cQuant strategies.

    A strategy is a pure function: given context, return signals.
    Strategies do NOT manage positions, risk, or execution.
    """

    @property
    @abstractmethod
    def strategy_id(self) -> str:
        """Unique stable identifier for this strategy."""

    @abstractmethod
    def generate_signals(self, ctx: StrategyContext) -> SignalFrame:
        """Generate trading signals for the given context.

        Returns a Polars DataFrame with columns:
            [asset_id (str), signal_date (date), direction (str),
             strength (f64), confidence (f64)]
        """
