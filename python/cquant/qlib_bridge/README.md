# cquant.qlib_bridge

Isolation layer between cQuant and [Microsoft Qlib](https://github.com/microsoft/qlib).

## Design Principle

**All external code imports `cquant.qlib_bridge`, never `import qlib` directly.**

This ensures a single upgrade path and graceful degradation when Qlib is unavailable.

## Availability

```python
from cquant.qlib_bridge import QLIB_AVAILABLE

if QLIB_AVAILABLE:
    print("Qlib is installed and usable")
else:
    print("Qlib unavailable — cQuant native fallbacks active")
```

## Modules

| File | Purpose |
|------|---------|
| `_compat.py` | `QLIB_AVAILABLE` flag, `require_qlib()`, `qlib_or_fallback()` |
| `data_handler.py` | `CQuantDataHandler` — DuckDB → Qlib DataHandlerLP adapter |
| `evaluator.py` | `QlibEvaluator` — IC/risk analysis wrappers (Polars in/out) |
| `factor_set.py` | `QlibFactorSet` — reads Alpha158/360 factor definitions |

## Usage

```python
from cquant.qlib_bridge import CQuantDataHandler, QlibEvaluator

# Load features from DuckDB
handler = CQuantDataHandler.from_catalog(
    catalog=catalog,
    dataset_version="tdx_bulk_v1",   # matches dataset version in DuckDB
    start=date(2024, 1, 1),
    end=date(2024, 12, 31),
)
features = handler.fetch_features()   # Polars DataFrame
labels   = handler.fetch_labels(horizon=5)  # Polars Series

# Risk / return analysis
evaluator = QlibEvaluator()
result = evaluator.risk_analysis(returns_series)
# → {"annualized_return": ..., "information_ratio": ..., "max_drawdown": ..., "mean": ..., "std": ...}
```

## Graceful Fallback

`qlib_or_fallback()` routes to Qlib when available, otherwise to cQuant's scipy-based
native implementation — callers are unaware of which path runs:

```python
from cquant.qlib_bridge._compat import qlib_or_fallback

result = qlib_or_fallback(
    qlib_fn=lambda: _qlib_ic_impl(factor, returns),
    fallback_fn=lambda: _scipy_ic_impl(factor, returns),
)
```

## Alpha158 Factors

`cquant.factorlab.factors.alpha158` contains Polars-native reimplementations of Alpha158
factors, derived using `QlibFactorSet.alpha158_definitions()`. These run independently of
Qlib at inference time.

`QlibFactorSet.alpha158_definitions()` returns an empty list when Qlib is unavailable
(graceful degradation — no exception raised).

## Version Management

Qlib is a git submodule at `lib/qlib/`. To upgrade:
```bash
cd lib/qlib && git checkout v0.9.x
cd ../.. && pip install -e lib/qlib --no-deps
pytest python/tests/unit/test_qlib_bridge*.py
```
