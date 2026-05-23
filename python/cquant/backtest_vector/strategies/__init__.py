"""cquant.backtest_vector.strategies — Concrete strategy implementations."""

from cquant.backtest_vector.strategies.combo import CompositeStrategy
from cquant.backtest_vector.strategies.market_neutral import MarketNeutralStrategy
from cquant.backtest_vector.strategies.ml_strategy import MLModelStrategy
from cquant.backtest_vector.strategies.multi_factor import MultiFactorStrategy
from cquant.backtest_vector.strategies.sector_rotation import SectorRotationStrategy

__all__ = [
    "CompositeStrategy",
    "MarketNeutralStrategy",
    "MLModelStrategy",
    "MultiFactorStrategy",
    "SectorRotationStrategy",
]
