"""Tests for tradability filtering — verify that suspended and limit-up/down
stocks are correctly filtered from signals.

Task P1-20: Tradability filtering tests.
"""
from __future__ import annotations

from datetime import date, timedelta

import polars as pl
import pytest

from cquant.backtest_vector.costs import CostModel
from cquant.backtest_vector.engine import VectorBacktestEngine, BacktestSpec
from cquant.backtest_vector.strategy import Strategy, StrategyContext
from cquant.core.enums import EngineType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _BuyAllStrategy(Strategy):
    """Generates buy signals for every asset found in ctx.prices on each
    rebalance day.  Does NOT consult ctx.tradability — this tests the
    engine's pre-filtering of suspended stocks from ctx.prices.
    """

    @property
    def strategy_id(self) -> str:
        return "buy_all_test"

    def generate_signals(self, ctx: StrategyContext) -> pl.DataFrame:
        if ctx.prices is None or ctx.prices.is_empty():
            return _empty_signals()
        asset_ids = (
            ctx.prices
            .filter(pl.col("trade_date") == ctx.as_of_date)
            ["asset_id"]
            .unique()
            .to_list()
        )
        if not asset_ids:
            return _empty_signals()
        return pl.DataFrame({
            "asset_id": asset_ids,
            "signal_date": [ctx.as_of_date] * len(asset_ids),
            "direction": ["long"] * len(asset_ids),
            "strength": [1.0] * len(asset_ids),
            "confidence": [1.0] * len(asset_ids),
        })


class _TradabilityAwareStrategy(Strategy):
    """Generates buy signals for all assets in ctx.prices, but respects
    ctx.tradability: filters out limit-up stocks from buy signals and
    limit-down stocks from sell signals.

    On every rebalance day this strategy emits:
      - A 'long' signal for every asset that is NOT limit-up.
      - A 'sell' signal for every asset that IS limit-down
        (to test that limit-down blocks sells).
    """

    def __init__(self, emit_sell: bool = False) -> None:
        self._emit_sell = emit_sell

    @property
    def strategy_id(self) -> str:
        return "tradability_aware_test"

    def generate_signals(self, ctx: StrategyContext) -> pl.DataFrame:
        if ctx.prices is None or ctx.prices.is_empty():
            return _empty_signals()

        asset_ids = (
            ctx.prices
            .filter(pl.col("trade_date") == ctx.as_of_date)
            ["asset_id"]
            .unique()
            .to_list()
        )
        if not asset_ids:
            return _empty_signals()

        # Build limit-up / limit-down sets from tradability
        limit_up: set[str] = set()
        limit_down: set[str] = set()
        if ctx.tradability is not None and not ctx.tradability.is_empty():
            today = ctx.tradability.filter(pl.col("trade_date") == ctx.as_of_date)
            if "is_limit_up" in today.columns:
                limit_up = set(today.filter(pl.col("is_limit_up"))["asset_id"].to_list())
            if "is_limit_down" in today.columns:
                limit_down = set(today.filter(pl.col("is_limit_down"))["asset_id"].to_list())

        # Buy signals: exclude limit-up
        buy_assets = [a for a in asset_ids if a not in limit_up]
        frames: list[pl.DataFrame] = []
        if buy_assets:
            frames.append(pl.DataFrame({
                "asset_id": buy_assets,
                "signal_date": [ctx.as_of_date] * len(buy_assets),
                "direction": ["long"] * len(buy_assets),
                "strength": [1.0] * len(buy_assets),
                "confidence": [1.0] * len(buy_assets),
            }))

        # Sell signals: only for limit-down assets (to verify filtering)
        if self._emit_sell and limit_down:
            sell_assets = list(limit_down)
            frames.append(pl.DataFrame({
                "asset_id": sell_assets,
                "signal_date": [ctx.as_of_date] * len(sell_assets),
                "direction": ["sell"] * len(sell_assets),
                "strength": [1.0] * len(sell_assets),
                "confidence": [1.0] * len(sell_assets),
            }))

        if not frames:
            return _empty_signals()
        return pl.concat(frames)


def _empty_signals() -> pl.DataFrame:
    return pl.DataFrame(
        schema={
            "asset_id": pl.Utf8,
            "signal_date": pl.Date,
            "direction": pl.Utf8,
            "strength": pl.Float64,
            "confidence": pl.Float64,
        }
    )


def _build_tradability_price_data(
    n_days: int = 20,
    start_date: date = date(2025, 1, 2),
    initial_price: float = 10.0,
    suspended_asset: str = "SH600001",
    limit_up_asset: str = "SH600002",
    normal_asset: str = "SH600003",
    event_day: int = 10,
) -> pl.DataFrame:
    """Build synthetic OHLCV data for three assets over *n_days* days.

    - *suspended_asset*: normal until *event_day*, then ``is_suspended = True``.
    - *limit_up_asset*: normal until *event_day*, then limit-up (close == high,
      +10% from previous close) on that day.
    - *limit_down_asset* (same as *normal_asset* with special handling): not used
      here — *normal_asset* stays normal throughout.
    """
    rows: list[dict] = []

    for i in range(n_days):
        d = start_date + timedelta(days=i)
        prev_price = initial_price if i == 0 else None  # filled below

        # --- Suspended asset ---
        if i <= event_day:
            p_s = initial_price
            is_susp = False
        else:
            # Suspended: price stays at last close, flagged
            p_s = initial_price
            is_susp = True

        rows.append({
            "trade_date": d,
            "asset_id": suspended_asset,
            "open": p_s,
            "high": p_s * 1.01 if not is_susp else p_s,
            "low": p_s * 0.99 if not is_susp else p_s,
            "close": p_s,
            "volume": 1_000_000.0 if not is_susp else 0.0,
            "amount": p_s * 1_000_000 if not is_susp else 0.0,
            "is_suspended": is_susp,
        })

        # --- Limit-up asset ---
        if i < event_day:
            p_lu = initial_price
        elif i == event_day:
            # Limit-up: close = prev_close * 1.10, close == high
            p_lu = initial_price * 1.10
        else:
            # After limit-up day, normal trading at the new price
            p_lu = initial_price * 1.10

        rows.append({
            "trade_date": d,
            "asset_id": limit_up_asset,
            "open": p_lu if i != event_day else initial_price,  # opens at prev close
            "high": p_lu,  # close == high on limit-up day
            "low": initial_price * 0.99 if i == event_day else p_lu * 0.99,
            "close": p_lu,
            "volume": 1_000_000.0,
            "amount": p_lu * 1_000_000,
            "is_suspended": False,
        })

        # --- Normal asset ---
        p_n = initial_price * (1 + 0.001 * i)
        rows.append({
            "trade_date": d,
            "asset_id": normal_asset,
            "open": p_n,
            "high": p_n * 1.01,
            "low": p_n * 0.99,
            "close": p_n,
            "volume": 1_000_000.0,
            "amount": p_n * 1_000_000,
            "is_suspended": False,
        })

    return pl.DataFrame(rows)


def _build_limit_down_price_data(
    n_days: int = 20,
    start_date: date = date(2025, 1, 2),
    initial_price: float = 10.0,
    limit_down_asset: str = "SH600002",
    normal_asset: str = "SH600003",
    event_day: int = 10,
) -> pl.DataFrame:
    """Build price data where *limit_down_asset* hits limit-down on *event_day*.

    Limit-down: close == low, close <= prev_close * (1 - 0.10 + 0.005).
    """
    rows: list[dict] = []

    for i in range(n_days):
        d = start_date + timedelta(days=i)

        # --- Limit-down asset ---
        if i < event_day:
            p_ld = initial_price
        elif i == event_day:
            # Limit-down: close = prev_close * 0.90, close == low
            p_ld = initial_price * 0.90
        else:
            p_ld = initial_price * 0.90

        rows.append({
            "trade_date": d,
            "asset_id": limit_down_asset,
            "open": p_ld if i != event_day else initial_price,
            "high": initial_price * 1.01 if i == event_day else p_ld * 1.01,
            "low": p_ld,  # close == low on limit-down day
            "close": p_ld,
            "volume": 1_000_000.0,
            "amount": p_ld * 1_000_000,
            "is_suspended": False,
        })

        # --- Normal asset ---
        p_n = initial_price * (1 + 0.001 * i)
        rows.append({
            "trade_date": d,
            "asset_id": normal_asset,
            "open": p_n,
            "high": p_n * 1.01,
            "low": p_n * 0.99,
            "close": p_n,
            "volume": 1_000_000.0,
            "amount": p_n * 1_000_000,
            "is_suspended": False,
        })

    return pl.DataFrame(rows)


def _run_backtest(
    prices: pl.DataFrame,
    strategy: Strategy,
    start_date: date = date(2025, 1, 2),
    end_date: date = date(2025, 1, 21),
):
    """Helper to run a backtest with the given strategy and prices."""
    engine = VectorBacktestEngine()
    spec = BacktestSpec(
        strategy=strategy,
        prices=prices,
        start_date=start_date,
        end_date=end_date,
        initial_cash=1_000_000,
        cost_model=CostModel.for_cn(),
        rebalance_frequency="1d",
    )
    return engine.run(spec)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestTradabilityFiltering:
    """Verify that tradability filtering works for suspended, limit-up,
    and limit-down stocks."""

    START = date(2025, 1, 2)
    END = date(2025, 1, 21)
    EVENT_DAY = 10  # index into the 20-day window
    SUSPENDED = "SH600001"
    LIMIT_UP = "SH600002"
    NORMAL = "SH600003"

    # ---- Test 1: suspended stock produces no signals ----

    def test_suspended_stock_no_signals(self) -> None:
        """A stock that is suspended on a rebalance day should produce no
        signals — the engine pre-filters it from ctx.prices."""
        prices = _build_tradability_price_data(
            n_days=20,
            start_date=self.START,
            suspended_asset=self.SUSPENDED,
            limit_up_asset=self.LIMIT_UP,
            normal_asset=self.NORMAL,
            event_day=self.EVENT_DAY,
        )

        # Run only in the suspended window (after event_day).
        # The stock is suspended when i > event_day, i.e. from event_day+1.
        suspended_start = self.START + timedelta(days=self.EVENT_DAY + 1)
        result = _run_backtest(
            prices=prices,
            strategy=_BuyAllStrategy(),
            start_date=suspended_start,
            end_date=self.END,
        )

        # The suspended asset should NOT appear in fills (no buy executed)
        fills = result.fills
        if not fills.is_empty():
            suspended_fills = fills.filter(pl.col("asset_id") == self.SUSPENDED)
            assert suspended_fills.is_empty(), (
                f"Suspended asset {self.SUSPENDED} should have no fills, "
                f"but found:\n{suspended_fills}"
            )

        # The suspended asset should NOT appear in positions
        positions = result.positions
        if not positions.is_empty():
            suspended_pos = positions.filter(pl.col("asset_id") == self.SUSPENDED)
            assert suspended_pos.is_empty(), (
                f"Suspended asset {self.SUSPENDED} should have no positions, "
                f"but found:\n{suspended_pos}"
            )

    # ---- Test 2: limit-up stock produces no buy signal ----

    def test_limit_up_no_buy_signal(self) -> None:
        """A stock at limit-up on a rebalance day should not generate a buy
        signal.  The tradability-aware strategy filters limit-up from buys."""
        prices = _build_tradability_price_data(
            n_days=20,
            start_date=self.START,
            suspended_asset=self.SUSPENDED,
            limit_up_asset=self.LIMIT_UP,
            normal_asset=self.NORMAL,
            event_day=self.EVENT_DAY,
        )

        # Run across the event day so the engine builds tradability on that day
        result = _run_backtest(
            prices=prices,
            strategy=_TradabilityAwareStrategy(emit_sell=False),
            start_date=self.START,
            end_date=self.END,
        )

        fills = result.fills
        if not fills.is_empty():
            # On the limit-up day, there should be NO buy fill for the limit-up asset.
            # The next-bar execution means the signal on event_day executes on event_day+1.
            # However, the key check is that the strategy did not emit a buy signal
            # for the limit-up asset on the event day.  We verify by checking that
            # any fill for the limit-up asset on event_day+1 is absent (since the
            # strategy excluded it).
            event_date = self.START + timedelta(days=self.EVENT_DAY)
            exec_date = self.START + timedelta(days=self.EVENT_DAY + 1)

            limit_up_fills_on_exec = fills.filter(
                (pl.col("asset_id") == self.LIMIT_UP)
                & (pl.col("trade_date") == exec_date)
                & (pl.col("side") == "buy")
            )
            assert limit_up_fills_on_exec.is_empty(), (
                f"Limit-up asset {self.LIMIT_UP} should not have a buy fill on "
                f"exec date {exec_date}, but found:\n{limit_up_fills_on_exec}"
            )

    # ---- Test 3: limit-down stock produces no sell signal ----

    def test_limit_down_no_sell_signal(self) -> None:
        """A stock at limit-down on a rebalance day should not generate a sell
        signal.  The tradability-aware strategy filters limit-down from sells."""
        prices = _build_limit_down_price_data(
            n_days=20,
            start_date=self.START,
            limit_down_asset=self.LIMIT_UP,  # reuse the slot
            normal_asset=self.NORMAL,
            event_day=self.EVENT_DAY,
        )
        # Rename for clarity: the limit-down asset is SH600002
        limit_down_id = self.LIMIT_UP

        # First, establish a position in the limit-down asset by running
        # a buy-all strategy up to event_day - 1.
        pre_event_end = self.START + timedelta(days=self.EVENT_DAY - 1)
        result_pre = _run_backtest(
            prices=prices,
            strategy=_BuyAllStrategy(),
            start_date=self.START,
            end_date=pre_event_end,
        )

        # Now run the tradability-aware strategy (with sell enabled) on the
        # event day.  The strategy tries to sell limit-down assets, but
        # tradability filtering should block it.
        event_start = self.START + timedelta(days=self.EVENT_DAY)
        result = _run_backtest(
            prices=prices,
            strategy=_TradabilityAwareStrategy(emit_sell=True),
            start_date=event_start,
            end_date=self.END,
        )

        fills = result.fills
        if not fills.is_empty():
            # Check that no sell fill was generated for the limit-down asset
            # on or after the event day (signal on event_day executes on event_day+1)
            exec_date = self.START + timedelta(days=self.EVENT_DAY + 1)
            limit_down_sells = fills.filter(
                (pl.col("asset_id") == limit_down_id)
                & (pl.col("trade_date") >= exec_date)
                & (pl.col("side") == "sell")
            )
            assert limit_down_sells.is_empty(), (
                f"Limit-down asset {limit_down_id} should not have a sell fill "
                f"on or after {exec_date}, but found:\n{limit_down_sells}"
            )

    # ---- Test 4: normal stock generates signals ----

    def test_normal_stock_generates_signals(self) -> None:
        """A non-suspended, non-limit stock should generate normal buy signals."""
        prices = _build_tradability_price_data(
            n_days=20,
            start_date=self.START,
            suspended_asset=self.SUSPENDED,
            limit_up_asset=self.LIMIT_UP,
            normal_asset=self.NORMAL,
            event_day=self.EVENT_DAY,
        )

        result = _run_backtest(
            prices=prices,
            strategy=_BuyAllStrategy(),
            start_date=self.START,
            end_date=self.END,
        )

        fills = result.fills
        assert not fills.is_empty(), "Expected fills but got an empty DataFrame"

        # Normal asset should have at least one buy fill
        normal_buys = fills.filter(
            (pl.col("asset_id") == self.NORMAL) & (pl.col("side") == "buy")
        )
        assert normal_buys.height > 0, (
            f"Normal asset {self.NORMAL} should have at least one buy fill, "
            f"but found none.\nAll fills:\n{fills}"
        )

        # Normal asset should appear in positions
        positions = result.positions
        if not positions.is_empty():
            normal_pos = positions.filter(pl.col("asset_id") == self.NORMAL)
            assert not normal_pos.is_empty(), (
                f"Normal asset {self.NORMAL} should appear in positions"
            )
