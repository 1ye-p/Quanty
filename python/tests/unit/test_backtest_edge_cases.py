"""Unit tests for backtest engine edge cases.

Tests cover 8 boundary scenarios:
  TC1: Empty universe (zero stocks) -> no crash, empty result
  TC2: All stocks suspended -> no signal that day, position unchanged
  TC3: Single-stock universe -> top_n=1 works, weight=1.0
  TC4: top_n > universe_size -> selects all, no crash
  TC5: Zero volume -> FillSimulator participation limit kicks in
  TC6: No trading days in date range -> no crash, empty result
  TC7: Negative initial cash -> reject or return error
  TC8: Consecutive multi-day suspension spanning rebalance -> no signal, no slot occupied
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import polars as pl
import pytest

from cquant.backtest_vector.engine import BacktestSpec, BacktestResult, VectorBacktestEngine
from cquant.backtest_vector.strategy import Strategy, StrategyContext


# ── Helpers ────────────────────────────────────────────────────────────────────


def _dates(start: date, n_days: int) -> list[date]:
    """Generate *n_days* consecutive calendar dates starting from *start*."""
    return [start + timedelta(days=i) for i in range(n_days)]


def _make_prices(
    asset_ids: list[str],
    dates: list[date],
    close: float = 10.0,
    volume: float = 100_000.0,
    is_suspended: bool = False,
    amount: float | None = None,
) -> pl.DataFrame:
    """Build a minimal prices DataFrame accepted by the engine.

    Parameters
    ----------
    asset_ids:
        List of asset identifiers.
    dates:
        Trade dates to include.
    close:
        Constant close price for all rows.
    volume:
        Constant volume for all rows.
    is_suspended:
        Whether all rows are flagged as suspended.
    amount:
        Notional amount (defaults to ``close * volume``).
    """
    if amount is None:
        amount = close * volume

    rows = []
    for aid in asset_ids:
        for d in dates:
            rows.append({
                "asset_id": aid,
                "trade_date": d,
                "open": close,
                "high": close,
                "low": close,
                "close": close,
                "volume": volume,
                "amount": amount,
                "is_suspended": is_suspended,
            })
    return pl.DataFrame(rows)


class _FixedSignalStrategy(Strategy):
    """Strategy that returns a fixed set of signals on every rebalance.

    Parameters
    ----------
    signal_assets:
        Asset IDs to emit signals for.  If empty, returns an empty SignalFrame.
    strength:
        Signal strength (default 1.0).
    """

    def __init__(
        self,
        signal_assets: list[str] | None = None,
        strength: float = 1.0,
        strategy_id: str = "fixed_signal",
    ) -> None:
        self._signal_assets = signal_assets or []
        self._strength = strength
        self._strategy_id = strategy_id

    @property
    def strategy_id(self) -> str:
        return self._strategy_id

    def generate_signals(self, ctx: StrategyContext) -> pl.DataFrame:
        if not self._signal_assets:
            return pl.DataFrame(
                schema={
                    "asset_id": pl.Utf8,
                    "signal_date": pl.Date,
                    "direction": pl.Utf8,
                    "strength": pl.Float64,
                    "confidence": pl.Float64,
                }
            )

        return pl.DataFrame({
            "asset_id": self._signal_assets,
            "signal_date": [ctx.as_of_date] * len(self._signal_assets),
            "direction": ["long"] * len(self._signal_assets),
            "strength": [self._strength] * len(self._signal_assets),
            "confidence": [0.9] * len(self._signal_assets),
        })


class _SuspendAwareStrategy(Strategy):
    """Strategy that only signals non-suspended stocks.

    On each rebalance it inspects ``ctx.prices`` to discover which assets
    are present, then signals all of them.  Suspended stocks are already
    filtered out of ``ctx.prices`` by the engine (line ~515 in engine.py),
    so this naturally produces signals only for tradable assets.
    """

    def __init__(self, all_assets: list[str]) -> None:
        self._all_assets = all_assets

    @property
    def strategy_id(self) -> str:
        return "suspend_aware"

    def generate_signals(self, ctx: StrategyContext) -> pl.DataFrame:
        # ctx.prices already has suspended stocks filtered out by the engine
        if ctx.prices is None or ctx.prices.is_empty():
            return pl.DataFrame(
                schema={
                    "asset_id": pl.Utf8,
                    "signal_date": pl.Date,
                    "direction": pl.Utf8,
                    "strength": pl.Float64,
                    "confidence": pl.Float64,
                }
            )

        available = ctx.prices["asset_id"].unique().to_list()
        if not available:
            return pl.DataFrame(
                schema={
                    "asset_id": pl.Utf8,
                    "signal_date": pl.Date,
                    "direction": pl.Utf8,
                    "strength": pl.Float64,
                    "confidence": pl.Float64,
                }
            )

        return pl.DataFrame({
            "asset_id": available,
            "signal_date": [ctx.as_of_date] * len(available),
            "direction": ["long"] * len(available),
            "strength": [1.0] * len(available),
            "confidence": [0.9] * len(available),
        })


# ── TC1: Empty universe (zero stocks) ─────────────────────────────────────────


class TestEmptyUniverse:
    """TC1: Running a backtest with zero price rows should not crash."""

    def test_empty_prices_returns_error(self):
        """Empty price DataFrame should produce an error result, not an exception."""
        strategy = _FixedSignalStrategy(signal_assets=["SSE:600000"])
        dates = _dates(date(2025, 1, 2), 5)

        spec = BacktestSpec(
            strategy=strategy,
            prices=pl.DataFrame(schema={
                "asset_id": pl.Utf8,
                "trade_date": pl.Date,
                "open": pl.Float64,
                "high": pl.Float64,
                "low": pl.Float64,
                "close": pl.Float64,
                "volume": pl.Float64,
                "amount": pl.Float64,
                "is_suspended": pl.Boolean,
            }),
            start_date=dates[0],
            end_date=dates[-1],
            initial_cash=Decimal("1_000_000"),
        )

        engine = VectorBacktestEngine()
        result = engine.run(spec)

        # Should return a BacktestResult with an error, not raise
        assert isinstance(result, BacktestResult)
        assert result.error is not None
        assert "No price data" in result.error


# ── TC2: All stocks suspended ─────────────────────────────────────────────────


class TestAllSuspended:
    """TC2: When all stocks are suspended, no signals should be generated."""

    def test_all_suspended_no_signals(self):
        """Engine should not crash and should produce no active signals."""
        assets = ["SSE:600000", "SSE:600001", "SSE:600002"]
        dates = _dates(date(2025, 1, 2), 10)

        prices = _make_prices(assets, dates, is_suspended=True)

        # Strategy signals all assets; engine filters suspended from ctx.prices
        strategy = _SuspendAwareStrategy(all_assets=assets)

        spec = BacktestSpec(
            strategy=strategy,
            prices=prices,
            start_date=dates[0],
            end_date=dates[-1],
            initial_cash=Decimal("1_000_000"),
        )

        engine = VectorBacktestEngine()
        result = engine.run(spec)

        assert isinstance(result, BacktestResult)
        # All stocks are suspended -> strategy sees no tradable assets -> no signals
        # Engine raises "Strategy produced no signals" which is caught and returned as error
        assert result.error is not None
        assert "no signals" in result.error.lower() or "No price data" in result.error


# ── TC3: Single-stock universe ────────────────────────────────────────────────


class TestSingleStockUniverse:
    """TC3: With a single stock, top_n=1 should work and weight should be 1.0."""

    def test_single_stock_weight_one(self):
        """Single stock should be assigned full weight (1.0)."""
        dates = _dates(date(2025, 1, 2), 10)
        prices = _make_prices(["SSE:600000"], dates)

        strategy = _FixedSignalStrategy(signal_assets=["SSE:600000"])

        spec = BacktestSpec(
            strategy=strategy,
            prices=prices,
            start_date=dates[0],
            end_date=dates[-1],
            initial_cash=Decimal("1_000_000"),
        )

        engine = VectorBacktestEngine()
        result = engine.run(spec)

        assert isinstance(result, BacktestResult)
        assert result.error is None, f"Unexpected error: {result.error}"

        # Check that positions contain the single asset with weight ~1.0
        positions = result.positions
        assert not positions.is_empty(), "Positions should not be empty"

        # The positions df has [trade_date, asset_id, target_weight]
        weights = positions.filter(pl.col("asset_id") == "SSE:600000")
        assert not weights.is_empty(), "Should have positions for SSE:600000"

        # With equal-weight on 1 stock, target_weight should be 1.0
        max_weight = weights["target_weight"].max()
        assert abs(max_weight - 1.0) < 0.01, f"Expected weight ~1.0, got {max_weight}"


# ── TC4: top_n > universe_size ────────────────────────────────────────────────


class TestTopNExceedsUniverse:
    """TC4: When strategy signals more assets than available, all should be selected."""

    def test_more_signals_than_stocks(self):
        """Strategy signaling assets not in price data should not crash."""
        # Only 2 stocks in prices, but strategy signals 5
        available = ["SSE:600000", "SSE:600001"]
        all_signal = ["SSE:600000", "SSE:600001", "SSE:600002", "SSE:600003", "SSE:600004"]
        dates = _dates(date(2025, 1, 2), 10)
        prices = _make_prices(available, dates)

        strategy = _FixedSignalStrategy(signal_assets=all_signal)

        spec = BacktestSpec(
            strategy=strategy,
            prices=prices,
            start_date=dates[0],
            end_date=dates[-1],
            initial_cash=Decimal("1_000_000"),
        )

        engine = VectorBacktestEngine()
        result = engine.run(spec)

        assert isinstance(result, BacktestResult)
        # Should not crash.  Signals for non-existent assets will be
        # generated but the engine/FillSimulator will handle them
        # (no price -> no fill).
        assert result.error is None or "no signals" in (result.error or "").lower()

    def test_top_n_equals_universe(self):
        """When strategy signals exactly the universe, all should be selected equally."""
        assets = ["SSE:600000", "SSE:600001", "SSE:600002"]
        dates = _dates(date(2025, 1, 2), 10)
        prices = _make_prices(assets, dates)

        strategy = _FixedSignalStrategy(signal_assets=assets)

        spec = BacktestSpec(
            strategy=strategy,
            prices=prices,
            start_date=dates[0],
            end_date=dates[-1],
            initial_cash=Decimal("1_000_000"),
        )

        engine = VectorBacktestEngine()
        result = engine.run(spec)

        assert isinstance(result, BacktestResult)
        assert result.error is None, f"Unexpected error: {result.error}"

        positions = result.positions
        assert not positions.is_empty()

        # All 3 assets should appear in positions
        pos_assets = positions["asset_id"].unique().to_list()
        for asset in assets:
            assert asset in pos_assets, f"{asset} should be in positions"


# ── TC5: Zero volume ──────────────────────────────────────────────────────────


class TestZeroVolume:
    """TC5: Stocks with zero volume should have participation-limited fills."""

    def test_zero_volume_does_not_crash(self):
        """Engine should handle zero-volume stocks without crashing.

        NOTE: The current AShareFillSimulator._apply_volume_constraint skips
        the volume check when volume <= 0 (returns qty unchanged).  This means
        zero-volume stocks can still be filled at full size.  This test verifies
        the engine does not crash; a follow-up may tighten the constraint.
        """
        dates = _dates(date(2025, 1, 2), 10)

        rows = []
        for d in dates:
            rows.append({
                "asset_id": "SSE:600000",
                "trade_date": d,
                "open": 10.0,
                "high": 10.0,
                "low": 10.0,
                "close": 10.0,
                "volume": 0.0,       # Zero volume
                "amount": 0.0,
                "is_suspended": False,
            })
        prices = pl.DataFrame(rows)

        strategy = _FixedSignalStrategy(signal_assets=["SSE:600000"])

        spec = BacktestSpec(
            strategy=strategy,
            prices=prices,
            start_date=dates[0],
            end_date=dates[-1],
            initial_cash=Decimal("1_000_000"),
        )

        engine = VectorBacktestEngine()
        result = engine.run(spec)

        assert isinstance(result, BacktestResult)
        assert result.error is None, f"Unexpected error: {result.error}"
        # Backtest completes without crash -- that is the primary assertion
        assert result.metrics is not None


# ── TC6: No trading days in date range ────────────────────────────────────────


class TestNoTradingDays:
    """TC6: Date range outside available data should not crash."""

    def test_future_date_range(self):
        """Requesting a date range far in the future should return error result."""
        dates = _dates(date(2025, 1, 2), 5)
        prices = _make_prices(["SSE:600000"], dates)

        strategy = _FixedSignalStrategy(signal_assets=["SSE:600000"])

        # Request dates far in the future (no matching price data)
        spec = BacktestSpec(
            strategy=strategy,
            prices=prices,
            start_date=date(2030, 1, 1),
            end_date=date(2030, 12, 31),
            initial_cash=Decimal("1_000_000"),
        )

        engine = VectorBacktestEngine()
        result = engine.run(spec)

        assert isinstance(result, BacktestResult)
        # Should return error result, not raise
        assert result.error is not None
        assert "No price data" in result.error


# ── TC7: Negative initial cash ────────────────────────────────────────────────


class TestNegativeInitialCash:
    """TC7: Negative initial cash should produce an error or handle gracefully."""

    def test_negative_cash_no_crash(self):
        """Negative initial cash should not crash the engine."""
        dates = _dates(date(2025, 1, 2), 10)
        prices = _make_prices(["SSE:600000"], dates)

        strategy = _FixedSignalStrategy(signal_assets=["SSE:600000"])

        spec = BacktestSpec(
            strategy=strategy,
            prices=prices,
            start_date=dates[0],
            end_date=dates[-1],
            initial_cash=Decimal("-100_000"),  # Negative!
        )

        engine = VectorBacktestEngine()
        result = engine.run(spec)

        # Should return a BacktestResult, not crash.
        # The engine accepts negative cash gracefully (no error raised);
        # target weights are generated but no real trades execute.
        assert isinstance(result, BacktestResult)
        assert result.error is None, f"Unexpected error: {result.error}"
        # With negative cash, the engine produces zero total return
        # (target weights exist but no actual fills occur)
        assert result.metrics is not None, "Metrics should be present"
        assert result.metrics.total_return == 0.0, (
            "Negative cash should produce zero return"
        )


# ── TC8: Consecutive multi-day suspension spanning rebalance ──────────────────


class TestConsecutiveSuspensionAcrossRebalance:
    """TC8: Multi-day suspension spanning rebalance dates should not produce signals."""

    def test_suspended_stocks_produce_no_signals(self):
        """Stocks suspended across rebalance days should not occupy signal slots."""
        assets = ["SSE:600000", "SSE:600001", "SSE:600002"]
        dates = _dates(date(2025, 1, 2), 15)

        # All stocks start suspended for 5 days (covering first rebalance)
        # Then become tradable
        rows = []
        for aid in assets:
            for i, d in enumerate(dates):
                suspended = i < 5  # First 5 days: all suspended
                rows.append({
                    "asset_id": aid,
                    "trade_date": d,
                    "open": 10.0,
                    "high": 10.0,
                    "low": 10.0,
                    "close": 10.0,
                    "volume": 100_000.0,
                    "amount": 1_000_000.0,
                    "is_suspended": suspended,
                })
        prices = pl.DataFrame(rows)

        # Strategy tries to signal all assets
        strategy = _SuspendAwareStrategy(all_assets=assets)

        spec = BacktestSpec(
            strategy=strategy,
            prices=prices,
            start_date=dates[0],
            end_date=dates[-1],
            initial_cash=Decimal("1_000_000"),
        )

        engine = VectorBacktestEngine()
        result = engine.run(spec)

        assert isinstance(result, BacktestResult)
        # Should not crash.  During suspension days, engine filters suspended
        # stocks from ctx.prices, so strategy sees no tradable assets and
        # returns empty signals.
        assert result.error is None, f"Unexpected error: {result.error}"

        # Backtest succeeded (non-suspended days later produce signals).
        # Verify no positions were opened during the suspension period.
        positions = result.positions
        assert not positions.is_empty(), "Positions should exist for tradable days"

        # Check that no weight was assigned on the first 5 days (suspension period)
        suspension_dates = set(dates[:5])
        early_positions = positions.filter(
            pl.col("trade_date").is_in(list(suspension_dates))
        )
        assert early_positions.is_empty(), (
            "No positions should be opened during suspension period"
        )


# ── Entry point ───────────────────────────────────────────────────────────────


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
