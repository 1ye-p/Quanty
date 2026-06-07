"""cquant.qlib_bridge.backtest_bridge — Backtest execution bridge.

Routes backtest execution to Qlib's backtest framework when available,
or falls back to cQuant's native VectorBacktestEngine.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

import polars as pl

from cquant.qlib_bridge._compat import QLIB_AVAILABLE, qlib_or_fallback

logger = logging.getLogger(__name__)


@dataclass
class BacktestBridgeResult:
    """Result from backtest bridge execution."""

    run_id: str
    backend: str  # "qlib" or "native"
    strategy_id: str
    start_date: date
    end_date: date
    metrics: dict[str, float]
    portfolio_returns: pl.DataFrame
    positions: pl.DataFrame | None = None
    fills: pl.DataFrame | None = None
    completed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


def run_backtest_qlib(
    prices: pl.DataFrame,
    signals: pl.DataFrame,
    strategy_id: str = "default",
    start_date: date | None = None,
    end_date: date | None = None,
    initial_cash: Decimal = Decimal("1_000_000"),
    benchmark_asset_id: str = "",
    use_qlib: bool | None = None,
) -> BacktestBridgeResult:
    """Run a backtest using Qlib's backtest framework or native engine.

    When Qlib is available and ``use_qlib`` is not False, routes to
    Qlib's ``backtest`` module.  Otherwise falls back to cQuant's native
    VectorBacktestEngine.

    Parameters
    ----------
    prices:
        OHLCV price data with columns: ``asset_id``, ``trade_date``,
        ``open``, ``high``, ``low``, ``close``, ``volume``.
    signals:
        Position signals with columns: ``asset_id``, ``trade_date``,
        ``weight`` (target portfolio weight per asset).
    strategy_id:
        Identifier for the strategy being backtested.
    start_date:
        Backtest start date.  If None, uses first date in prices.
    end_date:
        Backtest end date.  If None, uses last date in prices.
    initial_cash:
        Initial portfolio cash (default 1,000,000).
    benchmark_asset_id:
        Benchmark asset ID for relative performance metrics.
    use_qlib:
        Force Qlib (True), force native (False), or auto-detect (None).

    Returns
    -------
    BacktestBridgeResult
        Backtest result with metrics and portfolio returns.
    """
    should_use_qlib = use_qlib if use_qlib is not None else QLIB_AVAILABLE

    if should_use_qlib:
        if not QLIB_AVAILABLE:
            logger.warning("Qlib not available, falling back to native backtest")
            return _run_native_backtest(
                prices, signals, strategy_id, start_date, end_date,
                initial_cash, benchmark_asset_id,
            )
        return _run_qlib_backtest(
            prices, signals, strategy_id, start_date, end_date,
            initial_cash, benchmark_asset_id,
        )
    else:
        return _run_native_backtest(
            prices, signals, strategy_id, start_date, end_date,
            initial_cash, benchmark_asset_id,
        )


def _run_qlib_backtest(
    prices: pl.DataFrame,
    signals: pl.DataFrame,
    strategy_id: str,
    start_date: date | None,
    end_date: date | None,
    initial_cash: Decimal,
    benchmark_asset_id: str,
) -> BacktestBridgeResult:
    """Run backtest using Qlib's backtest framework."""
    try:
        import qlib
        from qlib.contrib.evaluate import backtest_daily
        from qlib.contrib.strategy.signal_strategy import TopkDropoutStrategy

        logger.info("backtest_bridge: running via Qlib backtest for strategy=%s", strategy_id)

        # Determine date range
        dates = prices["trade_date"].unique().sort()
        if start_date is None:
            start_date = dates[0]
        if end_date is None:
            end_date = dates[-1]

        # Convert signals to Qlib format
        # Qlib expects a MultiIndex Series with (instrument, datetime) index
        signal_dict = {}
        for row in signals.iter_rows(named=True):
            asset = row["asset_id"]
            dt = str(row["trade_date"])
            weight = row["weight"]
            signal_dict[(asset, dt)] = weight

        # Create Qlib strategy
        strategy = TopkDropoutStrategy(
            signal=signal_dict,
            topk=10,
            n_drop=0,
        )

        # Run backtest
        portfolio_metric, indicator = backtest_daily(
            start_time=str(start_date),
            end_time=str(end_date),
            strategy=strategy,
        )

        # Extract metrics
        metrics = _extract_qlib_metrics(portfolio_metric)

        # Convert to Polars DataFrame
        portfolio_returns = _qlib_to_polars_returns(portfolio_metric)

        run_id = f"qlib_{strategy_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

        logger.info("backtest_bridge: Qlib backtest complete, metrics=%s", metrics)

        return BacktestBridgeResult(
            run_id=run_id,
            backend="qlib",
            strategy_id=strategy_id,
            start_date=start_date,
            end_date=end_date,
            metrics=metrics,
            portfolio_returns=portfolio_returns,
            metadata={"indicator": str(indicator)},
        )

    except Exception as exc:
        logger.warning("backtest_bridge: Qlib backtest failed: %s, falling back", exc)
        return _run_native_backtest(
            prices, signals, strategy_id, start_date, end_date,
            initial_cash, benchmark_asset_id,
        )


def _run_native_backtest(
    prices: pl.DataFrame,
    signals: pl.DataFrame,
    strategy_id: str,
    start_date: date | None,
    end_date: date | None,
    initial_cash: Decimal,
    benchmark_asset_id: str,
) -> BacktestBridgeResult:
    """Run backtest using cQuant's native VectorBacktestEngine."""
    logger.info("backtest_bridge: running via native VectorBacktestEngine for strategy=%s", strategy_id)

    from cquant.backtest_vector.engine import BacktestSpec, VectorBacktestEngine

    # Determine date range
    dates = prices["trade_date"].unique().sort()
    if start_date is None:
        start_date = dates[0]
    if end_date is None:
        end_date = dates[-1]

    # Create a concrete strategy from signals
    from cquant.backtest_vector.strategy import Strategy, StrategyContext
    from cquant.core.types import SignalFrame

    class _SignalStrategy(Strategy):
        """Concrete strategy that returns pre-computed signals."""

        def __init__(self, signals_df: pl.DataFrame):
            self._signals = signals_df

        @property
        def strategy_id(self) -> str:
            return strategy_id

        def generate_signals(self, ctx: StrategyContext) -> SignalFrame:
            # Filter signals for the as_of_date
            filtered = self._signals.filter(
                pl.col("trade_date") == ctx.as_of_date
            )
            # Convert weight-based signals to SignalFrame format
            return filtered.select([
                pl.col("asset_id"),
                pl.lit(ctx.as_of_date).alias("signal_date"),
                pl.when(pl.col("weight") > 0).then(pl.lit("buy")).otherwise(pl.lit("sell")).alias("direction"),
                pl.col("weight").abs().alias("strength"),
                pl.lit(1.0).alias("confidence"),
            ])

    strategy = _SignalStrategy(signals)

    # Create backtest spec
    spec = BacktestSpec(
        strategy=strategy,
        prices=prices,
        start_date=start_date,
        end_date=end_date,
        initial_cash=initial_cash,
        benchmark_asset_id=benchmark_asset_id,
    )

    # Run backtest
    engine = VectorBacktestEngine()
    result = engine.run(spec)

    # Extract metrics
    metrics = {
        "total_return": result.metrics.total_return,
        "annualized_return": result.metrics.annualized_return,
        "annualized_volatility": result.metrics.annualized_volatility,
        "sharpe_ratio": result.metrics.sharpe_ratio,
        "sortino_ratio": result.metrics.sortino_ratio,
        "max_drawdown": result.metrics.max_drawdown,
        "calmar_ratio": result.metrics.calmar_ratio,
        "win_rate": result.metrics.win_rate,
    }

    run_id = f"native_{strategy_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

    logger.info("backtest_bridge: native backtest complete, metrics=%s", metrics)

    return BacktestBridgeResult(
        run_id=run_id,
        backend="native",
        strategy_id=strategy_id,
        start_date=start_date,
        end_date=end_date,
        metrics=metrics,
        portfolio_returns=result.portfolio_returns,
        positions=result.positions,
        fills=result.fills,
    )


def _extract_qlib_metrics(portfolio_metric) -> dict[str, float]:
    """Extract key metrics from Qlib backtest result."""
    metrics = {}

    try:
        # Qlib returns metrics as a dict-like structure
        if hasattr(portfolio_metric, "items"):
            for key, value in portfolio_metric.items():
                if isinstance(value, (int, float)):
                    metrics[str(key)] = float(value)
        elif isinstance(portfolio_metric, dict):
            for key, value in portfolio_metric.items():
                if isinstance(value, (int, float)):
                    metrics[str(key)] = float(value)
    except Exception as exc:
        logger.warning("backtest_bridge: failed to extract Qlib metrics: %s", exc)

    return metrics


def _qlib_to_polars_returns(portfolio_metric) -> pl.DataFrame:
    """Convert Qlib backtest result to Polars DataFrame."""
    try:
        if hasattr(portfolio_metric, "reset_index"):
            df = portfolio_metric.reset_index()
            return pl.from_pandas(df)
        elif isinstance(portfolio_metric, dict):
            # Try to create a simple returns DataFrame
            if "return" in portfolio_metric:
                returns = portfolio_metric["return"]
                if hasattr(returns, "reset_index"):
                    return pl.from_pandas(returns.reset_index())
    except Exception as exc:
        logger.warning("backtest_bridge: failed to convert Qlib returns: %s", exc)

    # Return empty DataFrame as fallback
    return pl.DataFrame({
        "trade_date": [],
        "portfolio_return": [],
        "nav": [],
    })
