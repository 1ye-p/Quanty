# cquant.execution

Order execution and broker interfaces for the cQuant platform.

## Overview

`execution` provides a layered broker abstraction:

- **`Broker` ABC** — core order submission interface
- **`PaperBroker`** — simulated broker for paper trading and back-test replay
- **`BrokerAdapter`** — extended ABC for real broker connections, adding
  connect/disconnect lifecycle and event callbacks

---

## Architecture

```
Strategy signal
      |
      v
  Broker  (ABC)
  ├── PaperBroker          ← simulation / testing
  └── BrokerAdapter (ABC)  ← real broker connections
        └── QMTAdapter / IBAdapter / ...  ← concrete implementations
```

Adapters are registered and discovered via the `AdapterRegistry` helpers
(`register_adapter`, `list_adapters`, `create_adapter`).

---

## Key Classes

| Class / Dataclass | Module | Description |
|---|---|---|
| `Broker` | `broker.py` | Abstract base — submit, cancel, query orders |
| `Order` | `broker.py` | Order representation (see fields below) |
| `OrderStatus` | `broker.py` | Lifecycle enum for orders |
| `Position` | `broker.py` | Per-asset position with PnL |
| `Account` | `broker.py` | Cash + positions aggregate |
| `PaperBroker` | `paper_broker.py` | Simulated broker using `CostModel` |
| `BrokerAdapter` | `adapter.py` | ABC with connection lifecycle + callbacks |
| `BrokerInfo` | `adapter.py` | Broker connection metadata dataclass |

---

## Order Fields

| Field | Type | Description |
|---|---|---|
| `order_id` | `str` | Unique order identifier |
| `asset_id` | `str` | Asset identifier (e.g. `"SSE:600036"`) |
| `side` | `str` | `"buy"` or `"sell"` |
| `qty` | `int` | Requested quantity |
| `order_type` | `str` | `"market"` (default) or `"limit"` |
| `limit_price` | `float \| None` | Limit price for limit orders |
| `status` | `OrderStatus` | Current lifecycle state |
| `filled_qty` | `int` | Quantity actually filled |
| `filled_price` | `float` | Average fill price |
| `commission` | `float` | Broker commission charged |
| `stamp_duty` | `float` | Stamp duty (applies to A-share sells) |
| `slippage` | `float` | Slippage cost recorded |
| `total_cost` | `float` | Sum of all transaction costs |
| `strategy_id` | `str` | Owning strategy identifier |
| `submitted_at` | `datetime \| None` | Submission timestamp |
| `filled_at` | `datetime \| None` | Fill timestamp |
| `reject_reason` | `str` | Rejection message if applicable |

### OrderStatus values

`PENDING` → `SUBMITTED` → `PARTIAL_FILLED` → `FILLED`  
`SUBMITTED` → `CANCELLED` or `REJECTED`

---

## Quick Start — PaperBroker

```python
from cquant.execution import PaperBroker
from cquant.execution.broker import Order

broker = PaperBroker(initial_cash=1_000_000)

order = Order(
    order_id="ord-001",
    asset_id="SSE:600036",
    side="buy",
    qty=1000,
)

filled_order = broker.submit_order(order)
print(filled_order.status)       # OrderStatus.FILLED
print(filled_order.total_cost)

account = broker.get_account()
print(account.cash)
```

---

## Adding a Real Broker Adapter

1. Subclass `BrokerAdapter` and implement all abstract methods:
   - `connect()` / `disconnect()` / `is_connected()`
   - `get_broker_info() -> BrokerInfo`
   - All `Broker` ABC methods (`submit_order`, `cancel_order`, `get_order`,
     `get_positions`, `get_account`)

2. Register the adapter:

```python
from cquant.execution import register_adapter
from mypackage.qmt_adapter import QMTAdapter

register_adapter("qmt", QMTAdapter)

# Later, create by name:
from cquant.execution import create_adapter
adapter = create_adapter("qmt", config={...})
adapter.connect()
adapter.on_fill = lambda order: print(f"Filled: {order.order_id}")
```

3. Wire event callbacks (`on_fill`, `on_reject`, `on_cancel`) as needed; the
   base class dispatches them safely with exception isolation.
