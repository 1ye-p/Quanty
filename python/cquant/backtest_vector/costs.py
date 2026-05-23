"""cquant.backtest_vector.costs — CostModel: commission, stamp duty, and slippage.

This module is the Python authority for transaction cost calculation.
The Rust implementation (cquant-portfolio/src/costs.rs) must produce identical
results on the same inputs — this is enforced by the cross-engine parity test suite.

All rates are expressed as fractions (not basis points):
- 0.0003 = 0.03% = 万分之三 (standard A-share commission)
- 0.0005 = 0.05% = 万分之五 (A-share stamp duty, 2023-08-28 起减半)
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal


@dataclass
class CostModel:
    """Transaction cost model shared by backtest_vector and backtest_event.

    Default values are calibrated for CN A-share retail trading.
    Override when constructing for US/HK markets (see market_presets in backtest.toml).
    """

    # ── Commission ─────────────────────────────────────────────────────────────
    # Bilateral: charged on both buy and sell sides.
    commission_rate: Decimal = Decimal("0.0003")      # 0.03% of notional
    min_commission: Decimal = Decimal("5.0")           # CNY 5 minimum per order

    # ── Stamp duty ────────────────────────────────────────────────────────────
    # A-share: levied only on the SELL side.
    stamp_duty_rate: Decimal = Decimal("0.0005")       # 0.05% of notional (2023-08-28 起减半)
    stamp_duty_side: Literal["sell_only", "both", "none"] = "sell_only"

    # ── Slippage ───────────────────────────────────────────────────────────────
    # Modelled as a fixed fraction of notional (percentage slippage model).
    slippage_rate: Decimal = Decimal("0.0001")         # 0.01% of notional
    slippage_type: Literal["pct", "tick"] = "pct"

    # ── Market impact ──────────────────────────────────────────────────────────
    # Volume participation impact using square-root model.
    market_impact_rate: Decimal = Decimal("0")         # 0% of notional (default: disabled)

    # ── Market identifier ──────────────────────────────────────────────────────
    market: Literal["CN", "US", "HK"] = "CN"

    # ── Class methods for common market presets ────────────────────────────────

    @classmethod
    def for_cn(cls) -> "CostModel":
        """Standard CN A-share retail cost model."""
        return cls()

    @classmethod
    def for_us(cls) -> "CostModel":
        return cls(
            commission_rate=Decimal("0.0001"),
            min_commission=Decimal("1.0"),
            stamp_duty_rate=Decimal("0"),
            stamp_duty_side="none",
            slippage_rate=Decimal("0.0001"),
            market="US",
        )

    @classmethod
    def for_hk(cls) -> "CostModel":
        return cls(
            commission_rate=Decimal("0.0003"),
            min_commission=Decimal("50"),
            stamp_duty_rate=Decimal("0.0013"),
            stamp_duty_side="both",
            slippage_rate=Decimal("0.0001"),
            market="HK",
        )

    @classmethod
    def with_market_impact(
        cls,
        rate: Decimal = Decimal("0.001"),
        base_model: "CostModel | None" = None,
    ) -> "CostModel":
        """Return a copy of *base_model* (or default CN) with market impact enabled.

        Args:
            rate: Market impact coefficient for volume participation model.
            base_model: Base model to extend. Defaults to for_cn() if None.

        Returns:
            New CostModel with market_impact_rate set and all other fields copied.
        """
        base = base_model or cls.for_cn()
        return cls(
            commission_rate=base.commission_rate,
            min_commission=base.min_commission,
            stamp_duty_rate=base.stamp_duty_rate,
            stamp_duty_side=base.stamp_duty_side,
            slippage_rate=base.slippage_rate,
            slippage_type=base.slippage_type,
            market=base.market,
            market_impact_rate=rate,
        )

    # ── Cost calculation ───────────────────────────────────────────────────────

    def commission(self, notional: Decimal) -> Decimal:
        """Bilateral commission for a single order."""
        calculated = notional * self.commission_rate
        return max(calculated, self.min_commission).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    def stamp_duty(self, notional: Decimal, is_sell: bool) -> Decimal:
        """Stamp duty for a single order."""
        if self.stamp_duty_side == "none":
            return Decimal("0")
        if self.stamp_duty_side == "sell_only" and not is_sell:
            return Decimal("0")
        return (notional * self.stamp_duty_rate).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    def slippage(self, notional: Decimal) -> Decimal:
        """Slippage cost for a single fill."""
        if self.slippage_type == "pct":
            return (notional * self.slippage_rate).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        return Decimal("0")  # tick mode: implemented at fill level in engine

    def volume_participation_slippage(
        self,
        notional: Decimal,
        order_qty: int,
        avg_daily_volume: float,
    ) -> Decimal:
        """Market impact cost from volume participation (square-root model).

        Computes: impact = market_impact_rate × sqrt(order_qty / avg_daily_volume) × notional

        Args:
            notional: Order value in currency units.
            order_qty: Number of shares/units to order.
            avg_daily_volume: Average daily trading volume (shares/units).

        Returns:
            Market impact cost quantized to 0.01. Returns zero when market_impact_rate
            is 0 (default) or avg_daily_volume <= 0.
        """
        if self.market_impact_rate == Decimal("0") or avg_daily_volume <= 0:
            return Decimal("0")
        import math
        participation = float(order_qty) / avg_daily_volume
        impact_rate = self.market_impact_rate * Decimal(str(math.sqrt(participation)))
        return (notional * impact_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def total_cost(self, notional: Decimal, is_sell: bool) -> Decimal:
        """Total transaction cost = commission + stamp_duty + slippage."""
        return (
            self.commission(notional)
            + self.stamp_duty(notional, is_sell)
            + self.slippage(notional)
        )

    def cost_rate(self, is_sell: bool) -> Decimal:
        """Effective total cost rate as a fraction of notional (for vectorized use)."""
        rate = self.commission_rate + self.slippage_rate
        if self.stamp_duty_side == "both":
            rate += self.stamp_duty_rate
        elif self.stamp_duty_side == "sell_only" and is_sell:
            rate += self.stamp_duty_rate
        return rate
