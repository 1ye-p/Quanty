"""cquant.execution.live_executor — Live execution engine.

Orchestrates daily strategy execution using APScheduler. Checks trading
day, loads active strategies, generates signals, converts to orders,
and executes via PaperBroker.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone

from cquant.datahub.catalog import Catalog
from cquant.execution.execution_persister import ExecutionPersister
from cquant.execution.paper_broker import PaperBroker
from cquant.execution.signal_converter import SignalConverter
from cquant.execution.strategy_loader import StrategyLoader

logger = logging.getLogger(__name__)


class LiveExecutor:
    """Live execution engine.

    Runs daily at a configured time (default 15:30 CST), checks if
    today is a trading day, loads active strategies, generates signals,
    converts to orders, executes via PaperBroker, and persists results.

    Usage::

        executor = LiveExecutor(catalog)
        executor.run_once()          # Execute once for today
        executor.start_scheduler()   # Start daily scheduler
    """

    def __init__(
        self,
        catalog: Catalog,
        lot_size: int = 100,
        min_strength: float = 0.01,
        max_position_pct: float = 0.10,
    ) -> None:
        self._catalog = catalog
        self._loader = StrategyLoader(catalog)
        self._converter = SignalConverter(
            lot_size=lot_size,
            min_strength=min_strength,
            max_position_pct=max_position_pct,
        )
        self._persister = ExecutionPersister(catalog)

    def run_once(self) -> dict:
        """Execute all active strategies once for today.

        Returns
        -------
        Summary dict with keys: date, executed, skipped, errors.
        """
        today = date.today()
        summary = {
            "date": today.isoformat(),
            "executed": 0,
            "skipped": 0,
            "errors": [],
        }

        # Check if today is a trading day
        if not self._is_trading_day(today):
            logger.info("Not a trading day (%s), skipping execution", today)
            summary["skipped"] += 1
            return summary

        # Load active strategies
        active = self._loader.load_active_strategies()
        if not active:
            logger.info("No active strategies found")
            return summary

        for deployment in active:
            live_id = deployment["live_id"]
            strategy_id = deployment["strategy_id"]

            try:
                self._execute_strategy(deployment, today)
                summary["executed"] += 1
                logger.info("Executed strategy %s (live_id=%s)", strategy_id, live_id)
            except Exception as exc:
                error_msg = f"Failed to execute {strategy_id}: {exc}"
                logger.error(error_msg, exc_info=True)
                summary["errors"].append(error_msg)

        return summary

    def _execute_strategy(self, deployment: dict, trade_date: date) -> None:
        """Execute a single strategy deployment.

        Steps:
        1. Instantiate strategy from config
        2. Create StrategyContext with today's data
        3. Generate signals
        4. Convert signals to orders
        5. Execute orders via PaperBroker
        6. Persist results
        """
        from cquant.backtest_vector.strategy import StrategyContext

        strategy_id = deployment["strategy_id"]
        live_id = deployment["live_id"]
        initial_cash = deployment.get("initial_cash", 1_000_000)

        # Load strategy
        strategy = self._loader.load(strategy_id)

        # Build context
        ctx = StrategyContext(
            as_of_date=trade_date,
            universe_id="all",
        )

        # Generate signals
        signals = strategy.generate_signals(ctx)
        if signals.is_empty():
            logger.info("No signals from strategy %s", strategy_id)
            return

        # Create broker
        broker = PaperBroker(initial_cash=initial_cash)

        # Get current prices for the universe
        prices = self._fetch_prices(signals["asset_id"].to_list())
        broker.update_prices(prices)

        # Get current positions (empty for fresh execution)
        current_positions = {}

        # Convert signals to orders
        orders = self._converter.convert(
            signals, current_positions, initial_cash, prices
        )

        if not orders:
            logger.info("No orders generated for strategy %s", strategy_id)
            return

        # Execute orders
        executed_orders = []
        for order in orders:
            result = broker.submit_order(order)
            executed_orders.append(result)

        # Persist results
        self._persister.persist_batch(live_id, strategy_id, executed_orders)

        filled = sum(1 for o in executed_orders if o.status.value == "filled")
        rejected = sum(1 for o in executed_orders if o.status.value == "rejected")
        logger.info(
            "Strategy %s: %d orders (%d filled, %d rejected)",
            strategy_id,
            len(executed_orders),
            filled,
            rejected,
        )

    def _fetch_prices(self, asset_ids: list[str]) -> dict[str, float]:
        """Fetch current prices for asset IDs from silver layer.

        Falls back to most recent available prices.
        """
        if not asset_ids:
            return {}

        placeholders = ",".join("?" for _ in asset_ids)
        df = self._catalog.query(
            f"SELECT asset_id, close FROM silver_prices_1d "
            f"WHERE asset_id IN ({placeholders}) "
            f"ORDER BY trade_date DESC LIMIT ?",
            [*asset_ids, len(asset_ids)],
        )

        if df.is_empty():
            return {}

        # Take the most recent price per asset
        prices: dict[str, float] = {}
        for row in df.to_dicts():
            aid = row["asset_id"]
            if aid not in prices:
                prices[aid] = float(row["close"])

        return prices

    def _is_trading_day(self, d: date) -> bool:
        """Check if a date is a trading day using the market calendar."""
        try:
            from cquant.market_calendar import MarketCalendarService
            from cquant.core.enums import Exchange

            service = MarketCalendarService()
            return service.is_trading_day(d, Exchange.SSE)
        except Exception:
            # Fallback: skip weekends
            return d.weekday() < 5

    def start_scheduler(self, hour: int = 15, minute: int = 30) -> None:
        """Start the APScheduler blocking scheduler.

        Runs ``run_once`` daily at the specified time.

        Parameters
        ----------
        hour:
            Hour to run (default 15, i.e., 3 PM).
        minute:
            Minute to run (default 30).
        """
        try:
            from apscheduler.schedulers.blocking import BlockingScheduler
        except ImportError:
            raise ImportError(
                "APScheduler is required for the live scheduler. "
                "Install it with: pip install apscheduler"
            )

        scheduler = BlockingScheduler()
        scheduler.add_job(
            self.run_once,
            "cron",
            hour=hour,
            minute=minute,
            day_of_week="mon-fri",
            id="live_executor_daily",
            name="Daily Live Execution",
        )

        logger.info(
            "Live executor scheduler started. Runs daily at %02d:%02d (Mon-Fri)",
            hour,
            minute,
        )

        try:
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            logger.info("Scheduler stopped")
            scheduler.shutdown()
