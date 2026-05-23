# cquant.portfolio_opt

Portfolio optimization utilities for the cQuant platform.

## Overview

`portfolio_opt` provides classical and modern portfolio construction algorithms.
All optimizers share a common `PortfolioOptimizer` ABC and return an
`OptimizationResult`, making them interchangeable in back-test and live
execution pipelines.

---

## Optimizers

| Class | Algorithm | Notes |
|---|---|---|
| `MeanVarianceOptimizer` | Markowitz Mean-Variance (max Sharpe) | Long-only, configurable weight bounds |
| `RiskParityOptimizer` | Equal Risk Contribution | Covariance-based position sizing |
| `CovarianceEstimator` | Covariance matrix estimation | Used as an input helper for optimizers |

---

## Quick Start

```python
from cquant.portfolio_opt import MeanVarianceOptimizer

optimizer = MeanVarianceOptimizer(risk_free_rate=0.0, long_only=True)

result = optimizer.optimize(
    expected_returns={
        "SSE:600036": 0.10,
        "SZSE:000858": 0.12,
    },
    covariance={
        "SSE:600036": {"SSE:600036": 0.04, "SZSE:000858": 0.02},
        "SZSE:000858": {"SSE:600036": 0.02, "SZSE:000858": 0.09},
    },
)

print(result.weights)          # {"SSE:600036": 0.45, "SZSE:000858": 0.55}
print(result.sharpe_ratio)
```

---

## OptimizationResult Fields

Defined in `base.py` as a dataclass:

| Field | Type | Description |
|---|---|---|
| `weights` | `dict[str, float]` | Optimal weights keyed by `asset_id` |
| `expected_return` | `float` | Portfolio expected return (annualised) |
| `expected_volatility` | `float` | Portfolio expected volatility (annualised) |
| `sharpe_ratio` | `float` | Sharpe ratio at the optimal weights |
| `metadata` | `dict[str, Any]` | Solver diagnostics and extra info |

---

## Integration with BacktestVector

`cquant.backtest_vector.engine.BacktestVector` accepts an optional
`optimizer: PortfolioOptimizer` argument.  When supplied, the engine calls
`optimizer.optimize()` at each rebalance date and replaces the raw signal
weights with the optimizer's output before executing trades.

```python
from cquant.backtest_vector.engine import BacktestVector
from cquant.portfolio_opt import MeanVarianceOptimizer

bt = BacktestVector(
    catalog=catalog,
    strategy=strategy,
    optimizer=MeanVarianceOptimizer(),
)
result = bt.run()
```

When no optimizer is provided, the engine uses raw signal weights directly.
