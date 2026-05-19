"""cquant.backtest_vector — Vectorized backtesting engine backed by vectorbt."""

from cquant.backtest_vector.costs import CostModel
from cquant.backtest_vector.engine import BacktestSpec, BacktestResult, VectorBacktestEngine
from cquant.backtest_vector.run import BacktestRunner, BacktestRunSpec, StaticTopNStrategy
from cquant.backtest_vector.strategy import Strategy, StrategyContext

__all__ = [
    "CostModel",
    "BacktestSpec",
    "BacktestResult",
    "VectorBacktestEngine",
    "BacktestRunner",
    "BacktestRunSpec",
    "StaticTopNStrategy",
    "Strategy",
    "StrategyContext",
]
