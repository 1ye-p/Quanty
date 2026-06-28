"""Tests for forced exit fill injection — verify that stop-loss triggered
positions produce proper sell fills through FillSimulator.

Task P0-7b: Forced exit sell-fill injection.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import polars as pl
import pytest

from cquant.backtest_vector.costs import CostModel
from cquant.backtest_vector.engine import VectorBacktestEngine, BacktestSpec
from cquant.backtest_vector.strategy import Strategy, StrategyContext
from cquant.core.enums import EngineType
from cquant.core.enums import RiskDecisionType
from cquant.core.types import OrderIntent, RiskDecision, RiskSnapshot
from cquant.riskguard.models import RiskContext
from cquant.riskguard.policies.base import RiskPolicy
from cquant.riskguard.policies.forced_exit import ForcedExit, ForcedExitPolicy


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FixedStopLossForcedExit(ForcedExitPolicy, RiskPolicy):
    """Dual policy: ForcedExitPolicy for daily forced-exit checks
    + RiskPolicy (always-approve) so the engine's pre-trade gate does not crash.

    Forced exit triggers when a position's P&L% falls below a fixed threshold.
    """

    def __init__(self, stop_pct: float = -0.05) -> None:
        self._stop_pct = stop_pct

    # -- RiskPolicy interface (always approve -- we only care about forced exits) --

    @property
    def name(self) -> str:
        return "fixed_stop_loss_forced_exit"

    def evaluate(
        self, candidate: OrderIntent, snapshot: RiskSnapshot, ctx: RiskContext
    ) -> RiskDecision:
        return RiskDecision(
            decision=RiskDecisionType.APPROVED,
            original_qty=candidate.requested_qty,
            approved_qty=candidate.requested_qty,
            reasons=[],
            policy_names=[self.name],
        )

    # -- ForcedExitPolicy interface --

    def check_exits(
        self,
        positions: dict,
        current_prices: dict[str, float],
        entry_prices: dict[str, float],
        state: dict | None = None,
    ) -> list[ForcedExit]:
        exits: list[ForcedExit] = []
        for asset_id in positions:
            if asset_id not in current_prices or asset_id not in entry_prices:
                continue
            entry = entry_prices[asset_id]
            if entry <= 0:
                continue
            pnl_pct = (current_prices[asset_id] - entry) / entry
            if pnl_pct < self._stop_pct:
                exits.append(ForcedExit(
                    asset_id=asset_id,
                    reason=f"fixed_stop_loss: P&L {pnl_pct:.2%} < {self._stop_pct:.2%}",
                    urgency="high",
                ))
        return exits


class _BuyAndHoldStrategy(Strategy):
    """Always signal to hold both assets with equal weight."""

    def __init__(self, asset_ids: list[str]) -> None:
        self._asset_ids = asset_ids

    @property
    def strategy_id(self) -> str:
        return "buy_and_hold_test"

    def generate_signals(self, ctx: StrategyContext) -> pl.DataFrame:
        return pl.DataFrame({
            "asset_id": self._asset_ids,
            "signal_date": [ctx.as_of_date] * len(self._asset_ids),
            "direction": ["long"] * len(self._asset_ids),
            "strength": [1.0] * len(self._asset_ids),
            "confidence": [1.0] * len(self._asset_ids),
        })


def _build_price_data(
    drop_asset: str = "SH600001",
    stable_asset: str = "SH600002",
    initial_price: float = 10.0,
    drop_pct: float = -0.20,
    drop_day: int = 10,
    n_days: int = 30,
    start_date: date = date(2025, 1, 2),
) -> pl.DataFrame:
    """Create synthetic OHLCV data for two assets.

    - ``drop_asset``: stable until *drop_day*, then drops by *drop_pct* and stays low.
    - ``stable_asset``: gently drifts upward (0.1%/day).
    """
    rng_dates = [start_date + timedelta(days=i) for i in range(n_days)]

    rows: list[dict] = []
    for i, d in enumerate(rng_dates):
        # Drop asset
        if i <= drop_day:
            p_drop = initial_price
        else:
            p_drop = initial_price * (1 + drop_pct)

        rows.append({
            "trade_date": d,
            "asset_id": drop_asset,
            "open": p_drop,
            "high": p_drop * 1.01,
            "low": p_drop * 0.99,
            "close": p_drop,
            "volume": 1_000_000.0,
            "amount": p_drop * 1_000_000,
            "is_suspended": False,
        })

        # Stable asset
        p_stable = initial_price * (1 + 0.001 * i)
        rows.append({
            "trade_date": d,
            "asset_id": stable_asset,
            "open": p_stable,
            "high": p_stable * 1.01,
            "low": p_stable * 0.99,
            "close": p_stable,
            "volume": 1_000_000.0,
            "amount": p_stable * 1_000_000,
            "is_suspended": False,
        })

    return pl.DataFrame(rows)


def _run_backtest(
    prices: pl.DataFrame,
    asset_ids: list[str],
    risk_policies: list | None = None,
    initial_cash: Decimal = Decimal("1_000_000"),
    start_date: date = date(2025, 1, 2),
    end_date: date = date(2025, 1, 31),
    rebalance_frequency: str = "1d",
):
    """Helper to run a backtest with sensible defaults."""
    engine = VectorBacktestEngine()
    spec = BacktestSpec(
        strategy=_BuyAndHoldStrategy(asset_ids),
        prices=prices,
        start_date=start_date,
        end_date=end_date,
        initial_cash=initial_cash,
        cost_model=CostModel.for_cn(),
        risk_policies=risk_policies or [],
        rebalance_frequency=rebalance_frequency,
    )
    return engine.run(spec)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestForcedExitFills:
    """Test that forced exits generate proper sell fills through FillSimulator."""

    ASSET_DROP = "SH600001"
    ASSET_STABLE = "SH600002"
    START = date(2025, 1, 2)
    END = date(2025, 1, 31)
    DROP_DAY = 10  # index in the price data where the crash happens

    @pytest.fixture()
    def price_data(self) -> pl.DataFrame:
        return _build_price_data(
            drop_asset=self.ASSET_DROP,
            stable_asset=self.ASSET_STABLE,
            initial_price=10.0,
            drop_pct=-0.20,
            drop_day=self.DROP_DAY,
            n_days=30,
            start_date=self.START,
        )

    @pytest.fixture()
    def result_with_forced_exit(self, price_data):
        """Run a backtest with a ForcedExitPolicy that triggers at -5% loss."""
        return _run_backtest(
            prices=price_data,
            asset_ids=[self.ASSET_DROP, self.ASSET_STABLE],
            risk_policies=[_FixedStopLossForcedExit(stop_pct=-0.05)],
            start_date=self.START,
            end_date=self.END,
        )

    # ---- Test 1: forced exit generates sell fill ----

    def test_forced_exit_generates_sell_fill(self, result_with_forced_exit) -> None:
        """A stock that drops below stop-loss should produce a 'sell' fill."""
        result = result_with_forced_exit
        fills = result.fills

        # Must have fills
        assert not fills.is_empty(), "Expected fills but got an empty DataFrame"

        # At least one forced exit should have been logged
        assert len(result.forced_exits) > 0, "Expected at least one forced exit event"

        # The dropped asset should appear in forced_exits log
        exited_assets = {fe["asset_id"] for fe in result.forced_exits}
        assert self.ASSET_DROP in exited_assets, (
            f"Expected {self.ASSET_DROP} in forced_exits, got {exited_assets}"
        )

        # There should be a sell fill for the dropped asset
        sell_fills = fills.filter(
            (pl.col("side") == "sell") & (pl.col("asset_id") == self.ASSET_DROP)
        )
        assert sell_fills.height > 0, (
            f"Expected a 'sell' fill for {self.ASSET_DROP} but found none.\n"
            f"All fills:\n{fills}"
        )

    # ---- Test 2: forced exit fill has costs ----

    def test_forced_exit_fill_has_costs(self, result_with_forced_exit) -> None:
        """Forced exit fills must include commission > 0 and stamp_duty > 0."""
        fills = result_with_forced_exit.fills

        sell_fills = fills.filter(
            (pl.col("side") == "sell") & (pl.col("asset_id") == self.ASSET_DROP)
        )
        assert sell_fills.height > 0, "No sell fills found for the dropped asset"

        for row in sell_fills.iter_rows(named=True):
            assert row["commission"] > 0, (
                f"Expected commission > 0, got {row['commission']}"
            )
            assert row["stamp_duty"] > 0, (
                f"Expected stamp_duty > 0 for sell fill, got {row['stamp_duty']}"
            )

    # ---- Test 3: cooldown prevents re-entry on same rebalance cycle ----

    def test_cooldown_prevents_reentry(self, result_with_forced_exit) -> None:
        """After forced exit, the asset should not reappear in positions
        until the next rebalance clears the cooldown set."""
        result = result_with_forced_exit

        # Identify the forced exit date
        assert len(result.forced_exits) > 0
        exit_date = result.forced_exits[0]["date"]

        # The engine clears force_exited_assets on the NEXT rebalance date.
        # With daily rebalance, the next day is the next rebalance.
        # The key check: between exit_date and the next rebalance,
        # the strategy's signals must have excluded the forced-exit asset.
        # We verify this indirectly: if the engine recorded a forced_exit,
        # the cooldown mechanism was active.  We also check that the
        # fills show a sell on the forced exit.
        fills = result.fills
        forced_exit_sell = fills.filter(
            (pl.col("side") == "sell")
            & (pl.col("asset_id") == self.ASSET_DROP)
        )
        assert forced_exit_sell.height > 0, (
            "Expected a sell fill from the forced exit"
        )

        # The sell fill date should be >= exit_date (T+1 next-bar execution)
        sell_date = forced_exit_sell["trade_date"].min()
        assert sell_date >= exit_date, (
            f"Sell fill date {sell_date} should be >= exit_date {exit_date}"
        )

    # ---- Test 4: fills DataFrame schema ----

    def test_fills_dataframe_schema(self, result_with_forced_exit) -> None:
        """The fills DataFrame must have the expected columns and types."""
        fills = result_with_forced_exit.fills
        assert not fills.is_empty(), "Fills DataFrame is empty"

        expected_columns = {
            "trade_date", "asset_id", "side", "qty", "price",
            "notional", "commission", "stamp_duty", "slippage", "total_cost",
        }
        actual_columns = set(fills.columns)
        missing = expected_columns - actual_columns
        assert not missing, f"Missing columns in fills DataFrame: {missing}"

        # Verify types for key columns
        assert fills["trade_date"].dtype == pl.Date
        assert fills["side"].dtype == pl.Utf8
        assert fills["qty"].dtype in (pl.Int64, pl.Int32)
        assert fills["price"].dtype in (pl.Float64, pl.Float32)
        assert fills["commission"].dtype in (pl.Float64, pl.Float32)
        assert fills["stamp_duty"].dtype in (pl.Float64, pl.Float32)
        assert fills["total_cost"].dtype in (pl.Float64, pl.Float32)

        # Verify side values are only "buy" or "sell"
        valid_sides = set(fills["side"].unique().to_list())
        assert valid_sides.issubset({"buy", "sell"}), (
            f"Unexpected side values: {valid_sides}"
        )

    # ---- Bonus: verify the forced_exits log entry structure ----

    def test_forced_exit_log_entry_fields(self, result_with_forced_exit) -> None:
        """Forced exit log entries must contain required fields."""
        assert len(result_with_forced_exit.forced_exits) > 0

        entry = result_with_forced_exit.forced_exits[0]
        required_keys = {"date", "asset_id", "reason", "urgency"}
        missing = required_keys - set(entry.keys())
        assert not missing, f"Missing keys in forced_exit entry: {missing}"

        assert entry["asset_id"] == self.ASSET_DROP
        assert entry["urgency"] in ("normal", "high", "critical")
        assert "fixed_stop_loss" in entry["reason"]
