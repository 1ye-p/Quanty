"""cquant.cli.main — Main CLI entry point."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date

from cquant.datahub.catalog import Catalog


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for CLI."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def cmd_ingest(args: argparse.Namespace) -> None:
    """Handle 'ingest' command."""
    from cquant.datahub.ingest import MarketIngestionOrchestrator

    catalog = Catalog(args.catalog)
    orchestrator = MarketIngestionOrchestrator(catalog, [])

    if args.source == "tdx":
        version_id = orchestrator.ingest_bulk_tdx(
            db_path=args.tdx_db,
            start_date=date.fromisoformat(args.start),
            end_date=date.fromisoformat(args.end),
            chunk_days=args.chunk_days,
        )
        print(f"Ingestion complete: version_id={version_id}")
    else:
        print(f"Source '{args.source}' not yet supported", file=sys.stderr)
        sys.exit(1)


def cmd_bootstrap(args: argparse.Namespace) -> None:
    """Handle 'bootstrap' command."""
    from cquant.datahub.bootstrap import bootstrap_assets_from_tdx, bootstrap_calendar_from_tdx

    catalog = Catalog(args.catalog)

    if args.target == "assets":
        count = bootstrap_assets_from_tdx(catalog, args.tdx_db)
        print(f"Bootstrapped {count} assets")
    elif args.target == "calendar":
        count = bootstrap_calendar_from_tdx(catalog, args.tdx_db)
        print(f"Bootstrapped {count} calendar entries")
    elif args.target == "all":
        count_assets = bootstrap_assets_from_tdx(catalog, args.tdx_db)
        count_calendar = bootstrap_calendar_from_tdx(catalog, args.tdx_db)
        print(f"Bootstrapped {count_assets} assets, {count_calendar} calendar entries")
    else:
        print(f"Unknown target: {args.target}", file=sys.stderr)
        sys.exit(1)


def cmd_factors(args: argparse.Namespace) -> None:
    """Handle 'factors' command."""
    from cquant.factorlab.factor import FactorRegistry
    from cquant.factorlab.factors import BUILTIN_FACTORS
    from cquant.factorlab.materialize import FactorMaterializer, FactorMaterializationSpec

    catalog = Catalog(args.catalog)

    registry = FactorRegistry()
    if args.all:
        for factor in BUILTIN_FACTORS:
            registry.register(factor)
    else:
        for name in args.factor_names:
            for factor in BUILTIN_FACTORS:
                if factor.name == name:
                    registry.register(factor)
                    break
            else:
                print(f"Unknown factor: {name}", file=sys.stderr)
                sys.exit(1)

    materializer = FactorMaterializer(catalog, registry)
    spec = FactorMaterializationSpec(
        dataset_version=args.dataset_version,
        factor_names=registry.all_names(),
        start_date=date.fromisoformat(args.start),
        end_date=date.fromisoformat(args.end),
    )

    version_id = materializer.run(spec)
    print(f"Factor materialization complete: version_id={version_id}")
    print(f"Factors: {', '.join(registry.all_names())}")


def cmd_backtest(args: argparse.Namespace) -> None:
    """Handle 'backtest' command."""
    from cquant.backtest_vector.run import BacktestRunner, BacktestRunSpec

    catalog = Catalog(args.catalog)
    runner = BacktestRunner(catalog)

    spec = BacktestRunSpec(
        dataset_version=args.dataset_version,
        strategy_id=args.strategy_id,
        start_date=date.fromisoformat(args.start),
        end_date=date.fromisoformat(args.end),
        feature_set_version=args.feature_set_version or "",
        top_n=args.top_n,
        sort_factor=args.sort_factor,
    )

    run_id = runner.run(spec)
    print(f"Backtest complete: run_id={run_id}")


def cmd_analyze(args: argparse.Namespace) -> None:
    """Handle 'analyze' command."""
    from cquant.backtest_vector.engine import BacktestResult
    from cquant.bt_analyzer.run import AnalysisRunner, AnalysisRunSpec

    catalog = Catalog(args.catalog)

    # Load backtest result (simplified - in real usage, load from persisted data)
    print("Analysis command requires a BacktestResult object")
    print("Use the Python API directly for now")
    sys.exit(1)


def cmd_tca(args: argparse.Namespace) -> None:
    """Handle 'tca' command."""
    from cquant.backtest_vector.tca import TransactionCostAnalyzer
    import polars as pl

    catalog = Catalog(args.catalog)
    catalog.initialize()

    # Get fills for the specified run
    fills = catalog.query(
        "SELECT trade_date, asset_id, side, qty, price, notional,"
        " commission, stamp_duty, slippage, total_cost"
        " FROM gold_fills"
        " WHERE run_id = ?"
        " ORDER BY trade_date",
        [args.run_id],
    )

    if fills.is_empty():
        print(f"No fills found for run_id={args.run_id}")
        sys.exit(1)

    analyzer = TransactionCostAnalyzer()

    if args.by_asset:
        details = analyzer.analyze_by_asset(fills)
        print(f"\nTCA by Asset (run_id={args.run_id}):\n")
        print(f"{'Asset':<20} {'Turnover':>15} {'Cost':>15} {'Cost%':>8} {'Trades':>8}")
        print(f"{'-'*20} {'-'*15} {'-'*15} {'-'*8} {'-'*8}")
        for d in details[:args.top]:
            print(f"{d.asset_id:<20} {d.turnover:>15,.2f} {d.total_cost:>15,.2f} {d.cost_pct:>7.4f}% {d.num_trades:>8,}")
    elif args.by_date:
        details = analyzer.analyze_by_date(fills)
        print(f"\nTCA by Date (run_id={args.run_id}):\n")
        print(f"{'Date':<12} {'Turnover':>15} {'Cost':>15} {'Cost%':>8} {'Trades':>8}")
        print(f"{'-'*12} {'-'*15} {'-'*15} {'-'*8} {'-'*8}")
        for d in details[:args.top]:
            print(f"{d.trade_date:<12} {d.turnover:>15,.2f} {d.total_cost:>15,.2f} {d.cost_pct:>7.4f}% {d.num_trades:>8,}")
    else:
        report = analyzer.generate_report(fills)
        print(report)


def cmd_positions(args: argparse.Namespace) -> None:
    """Handle 'positions' command."""
    import json

    catalog = Catalog(args.catalog)
    catalog.initialize()

    if args.run_id:
        # Show positions for a specific run
        snaps = catalog.query(
            "SELECT trade_date, cash, nav, positions_count, gross_exposure, net_exposure"
            " FROM gold_portfolio_snapshots"
            " WHERE run_id = ?"
            " ORDER BY trade_date DESC"
            " LIMIT ?",
            [args.run_id, args.limit],
        )
        if snaps.is_empty():
            print(f"No snapshots found for run_id={args.run_id}")
            sys.exit(1)

        print(f"\nPortfolio Snapshots (run_id={args.run_id}):\n")
        print(f"{'Date':<12} {'Cash':>15} {'NAV':>15} {'Positions':>10} {'Gross Exp':>15}")
        print(f"{'-'*12} {'-'*15} {'-'*15} {'-'*10} {'-'*15}")
        for row in snaps.iter_rows(named=True):
            print(f"{str(row['trade_date']):<12} {row['cash']:>15,.2f} {row['nav']:>15,.2f} "
                  f"{row['positions_count']:>10,} {row['gross_exposure']:>15,.2f}")
    else:
        # Show latest run
        runs = catalog.query('''
            SELECT run_id, strategy_id, started_at, status
            FROM gold_backtest_runs
            ORDER BY started_at DESC
            LIMIT 5
        ''')
        print("\nRecent Backtest Runs:\n")
        print(f"{'Run ID':<40} {'Strategy':<20} {'Started':<20} {'Status':<10}")
        print(f"{'-'*40} {'-'*20} {'-'*20} {'-'*10}")
        for row in runs.iter_rows(named=True):
            print(f"{row['run_id']:<40} {row['strategy_id']:<20} "
                  f"{str(row['started_at']):<20} {row['status']:<10}")


def cmd_status(args: argparse.Namespace) -> None:
    """Handle 'status' command."""
    catalog = Catalog(args.catalog)
    catalog.initialize()
    conn = catalog._get_conn()

    print("=== cQuant Status ===\n")

    # Silver layer
    assets = conn.execute("SELECT COUNT(*) FROM silver_prices_1d").fetchone()
    print(f"Silver prices: {assets[0]:,} rows")

    asset_count = conn.execute("SELECT COUNT(DISTINCT asset_id) FROM silver_prices_1d").fetchone()
    print(f"Assets: {asset_count[0]:,}")

    date_range = conn.execute("SELECT MIN(trade_date), MAX(trade_date) FROM silver_prices_1d").fetchone()
    print(f"Date range: {date_range[0]} to {date_range[1]}\n")

    # Gold layer
    factors = conn.execute("SELECT COUNT(*) FROM gold_factor_values").fetchone()
    print(f"Factor values: {factors[0]:,}")

    factor_names = conn.execute("SELECT COUNT(DISTINCT factor_name) FROM gold_factor_values").fetchone()
    print(f"Unique factors: {factor_names[0]}")

    backtests = conn.execute("SELECT COUNT(*) FROM gold_backtest_runs").fetchone()
    print(f"Backtest runs: {backtests[0]}")

    analyses = conn.execute("SELECT COUNT(*) FROM gold_bt_analysis_runs").fetchone()
    print(f"Analysis runs: {analyses[0]}\n")

    # Available factors
    factor_list = conn.execute("SELECT DISTINCT factor_name FROM gold_factor_values ORDER BY factor_name").fetchdf()
    print("Available factors:")
    for _, row in factor_list.iterrows():
        print(f"  - {row['factor_name']}")


def cmd_quote(args: argparse.Namespace) -> None:
    """Handle 'quote' command."""
    from cquant.datahub.connectors.realtime_connector import QuoteFeed

    feed = QuoteFeed()

    if args.all:
        quotes = feed.get_all_quotes(limit=20)
    elif args.symbols:
        quotes = feed.get_quotes(args.symbols)
    else:
        print("Specify symbols or use --all", file=sys.stderr)
        sys.exit(1)

    if not quotes:
        print("No quotes retrieved")
        return

    if args.watch:
        # Watch mode
        print(f"Watching {list(quotes.keys())} (Ctrl+C to stop)...\n")
        _print_quotes_header()

        def _on_update(updated_quotes):
            _print_quotes(updated_quotes)

        import time
        try:
            _on_update(quotes)
            while True:
                time.sleep(args.interval)
                new_quotes = feed.get_quotes(list(quotes.keys()))
                if new_quotes:
                    print("\033[A" * len(new_quotes))  # Move cursor up
                    _on_update(new_quotes)
        except KeyboardInterrupt:
            print("\nStopped watching")
    else:
        _print_quotes_header()
        _print_quotes(quotes)


def _print_quotes_header() -> None:
    print(f"{'Symbol':<10} {'Price':>10} {'Change':>10} {'Change%':>8} {'Volume':>12} {'Bid1':>10} {'Ask1':>10}")
    print(f"{'-'*10} {'-'*10} {'-'*10} {'-'*8} {'-'*12} {'-'*10} {'-'*10}")


def _print_quotes(quotes: dict) -> None:
    for symbol, q in sorted(quotes.items()):
        sign = "+" if q.change >= 0 else ""
        print(f"{symbol:<10} {q.price:>10.2f} {sign}{q.change:>9.2f} {sign}{q.change_pct:>7.2f}% "
              f"{q.volume:>12,} {q.bid1:>10.2f} {q.ask1:>10.2f}")


def _get_broker(name: str):
    """Get broker instance by name."""
    if name == "paper":
        from cquant.execution.paper_broker import PaperBroker
        return PaperBroker()
    else:
        print(f"Error: Unsupported broker '{name}'. Only 'paper' is currently available.", file=sys.stderr)
        sys.exit(1)


def cmd_trade_account(args: argparse.Namespace) -> None:
    """Handle 'trade account' command."""
    broker = _get_broker(args.broker)
    account = broker.get_account()

    print(f"\n=== Account ({args.broker}) ===\n")
    print(f"  Cash:          {account.cash:>15,.2f}")
    print(f"  NAV:           {account.nav:>15,.2f}")
    print(f"  Gross Exposure:{account.gross_exposure:>15,.2f}")
    print(f"  Net Exposure:  {account.net_exposure:>15,.2f}")
    print(f"  Realized PnL:  {account.realized_pnl:>15,.2f}")
    print(f"  Unrealized PnL:{account.unrealized_pnl:>15,.2f}")
    print(f"  Positions:     {len(account.positions):>15,}")


def _detect_exchange(symbol: str) -> str:
    """Detect exchange from symbol prefix."""
    if symbol.startswith(("6", "5")):
        return "SSE"
    elif symbol.startswith(("0", "3", "1")):
        return "SZSE"
    elif symbol.startswith(("4", "8")):
        return "BSE"
    return "UNKNOWN"


def cmd_trade_buy(args: argparse.Namespace) -> None:
    """Handle 'trade buy' command."""
    import uuid
    from cquant.execution.broker import Order

    broker = _get_broker(args.broker)

    # Fetch current price
    from cquant.datahub.connectors.realtime_connector import QuoteFeed
    feed = QuoteFeed()
    quotes = feed.get_quotes([args.symbol])
    if args.symbol not in quotes and not args.limit:
        print(f"Cannot get price for {args.symbol}, use --limit", file=sys.stderr)
        sys.exit(1)

    price = args.limit or quotes[args.symbol].price
    exchange = _detect_exchange(args.symbol)
    order = Order(
        order_id=str(uuid.uuid4())[:8],
        asset_id=f"{exchange}:{args.symbol}",
        side="buy",
        qty=args.qty,
        order_type="limit" if args.limit else "market",
        limit_price=args.limit,
    )

    # Update broker prices
    if quotes:
        broker.update_prices({q.asset_id: q.price for q in quotes.values()})

    result = broker.submit_order(order)
    _print_order(result)


def cmd_trade_sell(args: argparse.Namespace) -> None:
    """Handle 'trade sell' command."""
    import uuid
    from cquant.execution.broker import Order

    broker = _get_broker(args.broker)

    from cquant.datahub.connectors.realtime_connector import QuoteFeed
    feed = QuoteFeed()
    quotes = feed.get_quotes([args.symbol])
    if args.symbol not in quotes and not args.limit:
        print(f"Cannot get price for {args.symbol}, use --limit", file=sys.stderr)
        sys.exit(1)

    exchange = _detect_exchange(args.symbol)
    order = Order(
        order_id=str(uuid.uuid4())[:8],
        asset_id=f"{exchange}:{args.symbol}",
        side="sell",
        qty=args.qty,
        order_type="limit" if args.limit else "market",
        limit_price=args.limit,
    )

    if quotes:
        broker.update_prices({q.asset_id: q.price for q in quotes.values()})

    result = broker.submit_order(order)
    _print_order(result)


def _print_order(order) -> None:
    print(f"\n=== Order {order.order_id} ===\n")
    print(f"  Asset:    {order.asset_id}")
    print(f"  Side:     {order.side}")
    print(f"  Qty:      {order.qty:,}")
    print(f"  Status:   {order.status.value}")
    if order.filled_qty > 0:
        print(f"  Filled:   {order.filled_qty:,} @ {order.filled_price:.2f}")
        print(f"  Cost:     {order.total_cost:.2f}")
    if order.reject_reason:
        print(f"  Reason:   {order.reject_reason}")


def cmd_trade_positions(args: argparse.Namespace) -> None:
    """Handle 'trade positions' command."""
    broker = _get_broker(args.broker)
    positions = broker.get_positions()

    if not positions:
        print("No positions")
        return

    print(f"\n=== Positions ({args.broker}) ===\n")
    print(f"{'Asset':<20} {'Qty':>10} {'Avg Cost':>12} {'Mkt Value':>15} {'PnL':>15}")
    print(f"{'-'*20} {'-'*10} {'-'*12} {'-'*15} {'-'*15}")
    for asset_id, pos in sorted(positions.items()):
        print(f"{asset_id:<20} {pos.qty:>10,} {pos.avg_cost:>12.2f} "
              f"{pos.market_value:>15,.2f} {pos.unrealized_pnl:>15,.2f}")


def cmd_trade_orders(args: argparse.Namespace) -> None:
    """Handle 'trade orders' command."""
    from cquant.execution.broker import OrderStatus

    broker = _get_broker(args.broker)
    status_filter = None
    if args.status:
        try:
            status_filter = OrderStatus(args.status)
        except ValueError:
            print(f"Invalid status: {args.status}", file=sys.stderr)
            sys.exit(1)

    orders = broker.get_orders(status=status_filter)

    if not orders:
        print("No orders")
        return

    print(f"\n=== Orders ({args.broker}) ===\n")
    print(f"{'ID':<10} {'Asset':<20} {'Side':<6} {'Qty':>8} {'Status':<15} {'Filled':>8} {'Price':>10}")
    print(f"{'-'*10} {'-'*20} {'-'*6} {'-'*8} {'-'*15} {'-'*8} {'-'*10}")
    for o in orders[-50:]:  # Last 50
        print(f"{o.order_id:<10} {o.asset_id:<20} {o.side:<6} {o.qty:>8,} "
              f"{o.status.value:<15} {o.filled_qty:>8,} {o.filled_price:>10.2f}")


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="cquant",
        description="cQuant: AI-powered quantitative analysis platform",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    parser.add_argument(
        "--catalog",
        default="data/catalog.duckdb",
        help="Path to catalog database (default: data/catalog.duckdb)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ingest command
    ingest_parser = subparsers.add_parser("ingest", help="Ingest market data")
    ingest_parser.add_argument("--source", required=True, choices=["tdx"], help="Data source")
    ingest_parser.add_argument("--tdx-db", default="tdx.db", help="Path to TDX database")
    ingest_parser.add_argument("--start", required=True, help="Start date (YYYY-MM-DD)")
    ingest_parser.add_argument("--end", required=True, help="End date (YYYY-MM-DD)")
    ingest_parser.add_argument("--chunk-days", type=int, default=365, help="Chunk size in days")
    ingest_parser.set_defaults(func=cmd_ingest)

    # bootstrap command
    bootstrap_parser = subparsers.add_parser("bootstrap", help="Bootstrap metadata tables")
    bootstrap_parser.add_argument("--target", required=True, choices=["assets", "calendar", "all"], help="What to bootstrap")
    bootstrap_parser.add_argument("--tdx-db", default="tdx.db", help="Path to TDX database")
    bootstrap_parser.set_defaults(func=cmd_bootstrap)

    # factors command
    factors_parser = subparsers.add_parser("factors", help="Materialize factors")
    factors_parser.add_argument("--dataset-version", required=True, help="Dataset version")
    factors_parser.add_argument("--start", required=True, help="Start date (YYYY-MM-DD)")
    factors_parser.add_argument("--end", required=True, help="End date (YYYY-MM-DD)")
    factors_parser.add_argument("--all", action="store_true", help="Use all built-in factors")
    factors_parser.add_argument("--factor-names", nargs="+", help="Specific factor names")
    factors_parser.set_defaults(func=cmd_factors)

    # backtest command
    backtest_parser = subparsers.add_parser("backtest", help="Run backtest")
    backtest_parser.add_argument("--dataset-version", required=True, help="Dataset version")
    backtest_parser.add_argument("--strategy-id", required=True, help="Strategy identifier")
    backtest_parser.add_argument("--start", required=True, help="Start date (YYYY-MM-DD)")
    backtest_parser.add_argument("--end", required=True, help="End date (YYYY-MM-DD)")
    backtest_parser.add_argument("--feature-set-version", help="Feature set version")
    backtest_parser.add_argument("--top-n", type=int, default=10, help="Top N assets")
    backtest_parser.add_argument("--sort-factor", default="ret_20d", help="Sort factor")
    backtest_parser.set_defaults(func=cmd_backtest)

    # analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Run backtest analysis")
    analyze_parser.add_argument("--backtest-run-id", required=True, help="Backtest run ID")
    analyze_parser.set_defaults(func=cmd_analyze)

    # tca command
    tca_parser = subparsers.add_parser("tca", help="Transaction Cost Analysis")
    tca_parser.add_argument("--run-id", required=True, help="Backtest run ID")
    tca_parser.add_argument("--by-asset", action="store_true", help="Group by asset")
    tca_parser.add_argument("--by-date", action="store_true", help="Group by date")
    tca_parser.add_argument("--top", type=int, default=20, help="Show top N entries")
    tca_parser.set_defaults(func=cmd_tca)

    # positions command
    positions_parser = subparsers.add_parser("positions", help="Show portfolio positions")
    positions_parser.add_argument("--run-id", help="Backtest run ID (shows recent runs if omitted)")
    positions_parser.add_argument("--limit", type=int, default=10, help="Number of entries to show")
    positions_parser.set_defaults(func=cmd_positions)

    # status command
    status_parser = subparsers.add_parser("status", help="Show system status")
    status_parser.set_defaults(func=cmd_status)

    # quote command
    quote_parser = subparsers.add_parser("quote", help="Real-time quotes")
    quote_parser.add_argument("symbols", nargs="*", help="Stock codes (e.g. 600036 000001)")
    quote_parser.add_argument("--all", action="store_true", help="Show market snapshot (top 20)")
    quote_parser.add_argument("--watch", action="store_true", help="Watch mode (polling)")
    quote_parser.add_argument("--interval", type=float, default=5.0, help="Poll interval in seconds")
    quote_parser.set_defaults(func=cmd_quote)

    # trade command
    trade_parser = subparsers.add_parser("trade", help="Trading operations")
    trade_sub = trade_parser.add_subparsers(dest="trade_cmd", help="Trade subcommands")

    # trade account
    trade_account = trade_sub.add_parser("account", help="Show account status")
    trade_account.add_argument("--broker", default="paper", help="Broker name (paper/qmt)")
    trade_account.set_defaults(func=cmd_trade_account)

    # trade buy
    trade_buy = trade_sub.add_parser("buy", help="Place buy order")
    trade_buy.add_argument("symbol", help="Stock code")
    trade_buy.add_argument("qty", type=int, help="Quantity (shares)")
    trade_buy.add_argument("--broker", default="paper", help="Broker name")
    trade_buy.add_argument("--limit", type=float, help="Limit price (omit for market order)")
    trade_buy.set_defaults(func=cmd_trade_buy)

    # trade sell
    trade_sell = trade_sub.add_parser("sell", help="Place sell order")
    trade_sell.add_argument("symbol", help="Stock code")
    trade_sell.add_argument("qty", type=int, help="Quantity (shares)")
    trade_sell.add_argument("--broker", default="paper", help="Broker name")
    trade_sell.add_argument("--limit", type=float, help="Limit price (omit for market order)")
    trade_sell.set_defaults(func=cmd_trade_sell)

    # trade positions
    trade_pos = trade_sub.add_parser("positions", help="Show positions")
    trade_pos.add_argument("--broker", default="paper", help="Broker name")
    trade_pos.set_defaults(func=cmd_trade_positions)

    # trade orders
    trade_orders = trade_sub.add_parser("orders", help="Show orders")
    trade_orders.add_argument("--broker", default="paper", help="Broker name")
    trade_orders.add_argument("--status", help="Filter by status (pending/filled/cancelled/rejected)")
    trade_orders.set_defaults(func=cmd_trade_orders)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    setup_logging(args.verbose)
    args.func(args)


if __name__ == "__main__":
    main()
