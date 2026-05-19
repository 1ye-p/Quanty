"""cquant.backtest_vector.strategies — Concrete strategy implementations."""

from cquant.backtest_vector.strategies.combo import CompositeStrategy
from cquant.backtest_vector.strategies.multi_factor import MultiFactorStrategy

__all__ = [
    "CompositeStrategy",
    "MultiFactorStrategy",
]
