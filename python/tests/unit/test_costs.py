"""Unit tests for CostModel — verifies CN A-share fee calculation.

These tests are also the reference specification for the Rust parity test in
rust/crates/cquant-portfolio/tests/costs_parity.rs.
"""

from decimal import Decimal

import pytest

from cquant.backtest_vector.costs import CostModel


class TestCNCostModel:
    def setup_method(self) -> None:
        self.model = CostModel.for_cn()

    def test_commission_standard_order(self) -> None:
        # 100,000 CNY notional × 0.03% = 30 CNY > minimum (5 CNY)
        assert self.model.commission(Decimal("100000")) == Decimal("30.00")

    def test_commission_minimum_applied(self) -> None:
        # 10,000 CNY × 0.03% = 3 CNY < minimum, so min 5 CNY applies
        assert self.model.commission(Decimal("10000")) == Decimal("5.00")

    def test_stamp_duty_on_sell(self) -> None:
        # 100,000 CNY × 0.1% = 100 CNY
        assert self.model.stamp_duty(Decimal("100000"), is_sell=True) == Decimal("100.00")

    def test_no_stamp_duty_on_buy(self) -> None:
        # A-share: no stamp duty on buy
        assert self.model.stamp_duty(Decimal("100000"), is_sell=False) == Decimal("0")

    def test_total_cost_sell(self) -> None:
        # commission(100k) + stamp_duty(100k) + slippage(100k)
        # = 30 + 100 + 10 = 140
        total = self.model.total_cost(Decimal("100000"), is_sell=True)
        assert total == Decimal("140.00")

    def test_total_cost_buy(self) -> None:
        # commission(100k) + 0 + slippage(100k) = 30 + 10 = 40
        total = self.model.total_cost(Decimal("100000"), is_sell=False)
        assert total == Decimal("40.00")


class TestUSCostModel:
    def setup_method(self) -> None:
        self.model = CostModel.for_us()

    def test_no_stamp_duty_on_sell(self) -> None:
        assert self.model.stamp_duty(Decimal("100000"), is_sell=True) == Decimal("0")


class TestHKCostModel:
    def setup_method(self) -> None:
        self.model = CostModel.for_hk()

    def test_stamp_duty_on_both_sides(self) -> None:
        duty_buy = self.model.stamp_duty(Decimal("100000"), is_sell=False)
        duty_sell = self.model.stamp_duty(Decimal("100000"), is_sell=True)
        assert duty_buy > Decimal("0")
        assert duty_sell > Decimal("0")
        assert duty_buy == duty_sell
