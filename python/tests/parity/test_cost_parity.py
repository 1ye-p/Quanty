"""Cross-engine parity tests: Python CostModel ↔ Rust cquant_py CostModel.

These tests are SKIPPED automatically when the Rust wheel is not built.
To run them: build the wheel with `scripts/build_rust.sh`, then re-run pytest.

Each test case corresponds to a test in python/tests/unit/test_costs.py.
Both models must produce identical results (within Decimal rounding).
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

import pytest

from cquant.backtest_vector.costs import CostModel

cquant_py = pytest.importorskip("cquant_py", reason="Rust cquant_py wheel is not built; skipping parity tests")


def _money(value: Any) -> Decimal:
    """Round any numeric value to 2 dp for comparison."""
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _assert_parity(
    py_model: CostModel,
    rust_model: Any,
    method: str,
    notional: Decimal,
    expected: Decimal,
    *,
    is_sell: bool | None = None,
) -> None:
    py_fn = getattr(py_model, method)
    rust_fn = getattr(rust_model, method)
    notional_float = float(notional)

    py_result = py_fn(notional) if is_sell is None else py_fn(notional, is_sell)
    rust_result = rust_fn(notional_float) if is_sell is None else rust_fn(notional_float, is_sell)

    assert _money(py_result) == expected, f"Python {method}: expected {expected}, got {_money(py_result)}"
    assert _money(rust_result) == expected, f"Rust {method}: expected {expected}, got {_money(rust_result)}"
    assert _money(py_result) == _money(rust_result), (
        f"{method} parity failed: Python={_money(py_result)}, Rust={_money(rust_result)}"
    )


def test_cn_commission_standard() -> None:
    _assert_parity(CostModel.for_cn(), cquant_py.cost_model_cn(),
                   "commission", Decimal("100000"), Decimal("30.00"))


def test_cn_commission_minimum() -> None:
    _assert_parity(CostModel.for_cn(), cquant_py.cost_model_cn(),
                   "commission", Decimal("10000"), Decimal("5.00"))


def test_cn_stamp_duty_sell() -> None:
    _assert_parity(CostModel.for_cn(), cquant_py.cost_model_cn(),
                   "stamp_duty", Decimal("100000"), Decimal("100.00"), is_sell=True)


def test_cn_no_stamp_duty_buy() -> None:
    _assert_parity(CostModel.for_cn(), cquant_py.cost_model_cn(),
                   "stamp_duty", Decimal("100000"), Decimal("0.00"), is_sell=False)


def test_cn_total_cost_sell() -> None:
    _assert_parity(CostModel.for_cn(), cquant_py.cost_model_cn(),
                   "total_cost", Decimal("100000"), Decimal("140.00"), is_sell=True)


def test_cn_total_cost_buy() -> None:
    _assert_parity(CostModel.for_cn(), cquant_py.cost_model_cn(),
                   "total_cost", Decimal("100000"), Decimal("40.00"), is_sell=False)


def test_us_no_stamp_duty() -> None:
    _assert_parity(CostModel.for_us(), cquant_py.cost_model_us(),
                   "stamp_duty", Decimal("100000"), Decimal("0.00"), is_sell=True)


def test_hk_stamp_duty_both_sides() -> None:
    py_model = CostModel.for_hk()
    rust_factory = getattr(cquant_py, "cost_model_hk", None)
    if not callable(rust_factory):
        pytest.skip("cost_model_hk not exposed by cquant_py")
    rust_model = rust_factory()

    for is_sell in (True, False):
        py_val = _money(py_model.stamp_duty(Decimal("100000"), is_sell))
        rust_val = _money(rust_model.stamp_duty(100000.0, is_sell))
        assert py_val > Decimal("0.00"), f"HK stamp duty should be > 0 for is_sell={is_sell}"
        assert py_val == rust_val, f"HK stamp duty parity failed is_sell={is_sell}: {py_val} != {rust_val}"
