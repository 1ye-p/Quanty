"""cquant.execution — Order execution and broker interfaces.

Provides:
- Broker ABC: abstract broker interface
- PaperBroker: simulated broker for testing
- BrokerAdapter: broker adapter interface for real brokers
- AdapterRegistry: discover and create broker adapters
"""

from cquant.execution.adapter import BrokerAdapter, BrokerInfo
from cquant.execution.adapters import create_adapter, list_adapters, register_adapter
from cquant.execution.broker import Broker, OrderStatus
from cquant.execution.paper_broker import PaperBroker

__all__ = [
    "Broker",
    "OrderStatus",
    "PaperBroker",
    "BrokerAdapter",
    "BrokerInfo",
    "create_adapter",
    "list_adapters",
    "register_adapter",
]
