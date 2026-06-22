"""cquant.backtest_vector.strategies — Concrete strategy implementations."""

from cquant.backtest_vector.strategies.combo import CompositeStrategy
from cquant.backtest_vector.strategies.custom_weight_strategy import CustomWeightStrategy
from cquant.backtest_vector.strategies.indicator_signal import IndicatorSignalStrategy
from cquant.backtest_vector.strategies.market_neutral import MarketNeutralStrategy
from cquant.backtest_vector.strategies.ml_strategy import MLModelStrategy
from cquant.backtest_vector.strategies.multi_factor import MultiFactorStrategy
from cquant.backtest_vector.strategies.position_manager import (
    PositionManager,
    PositionManagerConfig,
)
from cquant.backtest_vector.strategies.sector_rotation import SectorRotationStrategy

__all__ = [
    "CompositeStrategy",
    "CustomWeightStrategy",
    "IndicatorSignalStrategy",
    "MarketNeutralStrategy",
    "MLModelStrategy",
    "MultiFactorStrategy",
    "PositionManager",
    "PositionManagerConfig",
    "SectorRotationStrategy",
]
