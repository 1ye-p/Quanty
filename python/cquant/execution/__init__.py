"""cquant.execution — Order execution and broker interfaces.

Provides:
- Broker ABC: abstract broker interface
- PaperBroker: simulated broker for testing
- BrokerAdapter: broker adapter interface for real brokers
- AdapterRegistry: discover and create broker adapters
- StrategyLoader: load strategy instances from backtest config
- SignalConverter: convert signals to Order objects
- ExecutionPersister: persist execution results
- LiveExecutor: daily execution engine
- AlgoOrderManager: TWAP/VWAP algorithmic order execution
"""

from cquant.execution.adapter import BrokerAdapter, BrokerInfo
from cquant.execution.adapters import create_adapter, list_adapters, register_adapter
from cquant.execution.algo_orders import (
    AlgoOrder,
    AlgoOrderManager,
    AlgoOrderParams,
    AlgoSlice,
    AlgoType,
    TWAPEngine,
    VWAPEngine,
)
from cquant.execution.broker import Broker, OrderStatus
from cquant.execution.execution_persister import ExecutionPersister
from cquant.execution.live_executor import LiveExecutor
from cquant.execution.paper_broker import PaperBroker
from cquant.execution.signal_converter import SignalConverter
from cquant.execution.strategy_loader import StrategyLoader

__all__ = [
    "Broker",
    "OrderStatus",
    "PaperBroker",
    "BrokerAdapter",
    "BrokerInfo",
    "create_adapter",
    "list_adapters",
    "register_adapter",
    "StrategyLoader",
    "SignalConverter",
    "ExecutionPersister",
    "LiveExecutor",
    "AlgoType",
    "AlgoOrderParams",
    "AlgoSlice",
    "AlgoOrder",
    "TWAPEngine",
    "VWAPEngine",
    "AlgoOrderManager",
]
