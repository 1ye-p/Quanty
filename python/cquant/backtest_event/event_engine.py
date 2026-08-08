"""cquant.backtest_event.event_engine — Event-driven backtest engine.

Implements the full backtest pipeline:
  bar → signal → order_intent → risk_check → order → fill → portfolio_update

This engine processes events sequentially, providing more granular control
and realistic simulation compared to the vectorized engine.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import polars as pl

from cquant.backtest_event.events import (
    BarEvent,
    EventType,
    FillEvent,
    OrderEvent,
    OrderIntentEvent,
    PortfolioUpdateEvent,
    RiskDecisionEvent,
    SignalEvent,
)
from cquant.backtest_vector.costs import CostModel
from cquant.backtest_vector.fill_simulator import AShareFillSimulator
from cquant.backtest_vector.metrics import BacktestMetrics, compute_metrics
from cquant.backtest_vector.strategy import Strategy, StrategyContext
from cquant.core.enums import EngineType, OrderSide, RiskDecisionType
from cquant.core.types import OrderIntent, RiskDecision, RiskSnapshot
from cquant.riskguard.models import RiskContext

logger = logging.getLogger(__name__)


class EventDrivenEngine:
    """Event-driven backtest engine.

    Processes market data bar-by-bar, generating signals, checking risk,
    simulating fills, and tracking portfolio state at each step.

    Usage::

        engine = EventDrivenEngine()
        result = engine.run(spec)
    """

    def run(self, spec) -> "BacktestResult":
        """Execute an event-driven backtest."""
        from cquant.backtest_vector.engine import BacktestResult

        run_id = str(uuid.uuid4())
        started_at = datetime.now(tz=timezone.utc)

        try:
            result = self._run_impl(spec, run_id, started_at)
        except Exception as exc:
            logger.exception("Event backtest %s failed: %s", run_id, exc)
            empty_metrics = BacktestMetrics(
                total_return=0, annualized_return=0, annualized_volatility=0,
                sharpe_ratio=0, sortino_ratio=0, max_drawdown=0, calmar_ratio=0,
                win_rate=0, profit_factor=0, var_95=0, cvar_95=0, beta=None,
                total_trades=0, trading_days=0,
            )
            result = BacktestResult(
                run_id=run_id,
                engine=EngineType.EVENT,
                strategy_id=spec.strategy.strategy_id,
                spec=spec,
                metrics=empty_metrics,
                portfolio_returns=pl.DataFrame(),
                net_returns=pl.DataFrame(),
                positions=pl.DataFrame(),
                fills=pl.DataFrame(),
                started_at=started_at,
                completed_at=datetime.now(tz=timezone.utc),
                error=str(exc),
            )

        return result

    def _run_impl(self, spec, run_id: str, started_at: datetime):
        """Core event-driven backtest implementation."""
        from cquant.backtest_vector.engine import BacktestResult

        # Filter prices to backtest window
        prices = spec.prices.filter(
            (pl.col("trade_date") >= spec.start_date)
            & (pl.col("trade_date") <= spec.end_date)
        ).sort(["trade_date", "asset_id"])

        if prices.is_empty():
            raise ValueError("No price data in the specified date range")

        trade_dates = sorted(prices["trade_date"].unique().to_list())

        # Build price lookup for efficient access
        price_lookup = self._build_price_lookup(prices)

        # Event processing state
        all_signals: list[SignalEvent] = []
        all_order_intents: list[OrderIntentEvent] = []
        all_risk_decisions: list[RiskDecisionEvent] = []
        all_orders: list[OrderEvent] = []
        all_fills: list[FillEvent] = []
        all_portfolio_updates: list[PortfolioUpdateEvent] = []
        pretrade_decisions: list[dict] = []

        # Track positions and cash
        cash = float(spec.initial_cash)
        positions: dict[str, int] = {}  # asset_id -> qty
        buy_dates: dict[str, date] = {}  # asset_id -> last buy date (for T+1)
        peak_nav = cash

        # Process each trade date
        for i, td in enumerate(trade_dates):
            # Step 1: Get bar events for this date
            day_bars = self._get_day_bars(td, price_lookup)

            # Step 2: Generate signals
            ctx = StrategyContext(
                as_of_date=td,
                universe_id=spec.universe_id,
                features=spec.features,
                prices=prices.filter(pl.col("trade_date") <= td),
            )
            signals = spec.strategy.generate_signals(ctx)

            if signals.is_empty():
                continue

            # Convert to signal events
            for row in signals.iter_rows(named=True):
                sig_event = SignalEvent(
                    asset_id=row["asset_id"],
                    trade_date=td,
                    direction=row.get("direction", "long"),
                    strength=row.get("strength", 1.0),
                    confidence=row.get("confidence", 1.0),
                    strategy_id=spec.strategy.strategy_id,
                )
                all_signals.append(sig_event)

            # Step 3: Generate order intents from signals
            active_assets = signals.filter(pl.col("strength") > 0)["asset_id"].to_list()
            n = len(active_assets)
            target_weights = {aid: 1.0 / n for aid in active_assets} if n else {}

            # Apply risk policies if configured
            if spec.risk_policies and target_weights:
                target_weights, decisions = self._apply_risk_checks(
                    target_weights, spec, td, prices, cash, positions, price_lookup,
                )
                pretrade_decisions.extend(decisions)

            # Create order intents
            for asset_id, weight in target_weights.items():
                price = price_lookup.get((td, asset_id), {}).get("close", 0.0)
                if price <= 0:
                    continue

                target_value = cash * weight
                current_qty = positions.get(asset_id, 0)
                current_value = current_qty * price
                buy_value = target_value - current_value

                if buy_value > 0:
                    # Buy
                    buy_qty = int(buy_value / price)
                    buy_qty = (buy_qty // 100) * 100  # Round to lot
                    if buy_qty > 0:
                        intent = OrderIntentEvent(
                            asset_id=asset_id,
                            trade_date=td,
                            side="buy",
                            requested_qty=buy_qty,
                            strategy_id=spec.strategy.strategy_id,
                        )
                        all_order_intents.append(intent)

            # Step 4: Process sells first (to free cash)
            for asset_id in list(positions.keys()):
                if positions[asset_id] <= 0:
                    continue
                if asset_id not in target_weights:
                    # Sell entire position
                    price = price_lookup.get((td, asset_id), {}).get("close", 0.0)
                    if price > 0:
                        # Check T+1
                        last_buy = buy_dates.get(asset_id)
                        if last_buy is not None and last_buy >= td:
                            continue  # Can't sell today

                        sell_qty = positions[asset_id]
                        intent = OrderIntentEvent(
                            asset_id=asset_id,
                            trade_date=td,
                            side="sell",
                            requested_qty=sell_qty,
                            strategy_id=spec.strategy.strategy_id,
                        )
                        all_order_intents.append(intent)

            # Step 5: Execute orders and generate fills
            for intent in all_order_intents:
                if intent.trade_date != td:
                    continue

                price = price_lookup.get((td, intent.asset_id), {}).get("close", 0.0)
                if price <= 0:
                    continue

                # Check market constraints
                if intent.side == "buy":
                    if self._is_suspended(td, intent.asset_id, price_lookup):
                        continue
                    if self._is_at_limit_up(td, intent.asset_id, price_lookup):
                        continue
                elif intent.side == "sell":
                    if self._is_suspended(td, intent.asset_id, price_lookup):
                        continue
                    if self._is_at_limit_down(td, intent.asset_id, price_lookup):
                        continue

                # Execute fill
                fill = self._execute_fill(intent, price, spec.cost_model)
                if fill:
                    all_fills.append(fill)

                    # Update positions and cash
                    if fill.side == "buy":
                        cash -= fill.notional + fill.total_cost
                        positions[fill.asset_id] = positions.get(fill.asset_id, 0) + fill.qty
                        buy_dates[fill.asset_id] = td
                    elif fill.side == "sell":
                        cash += fill.notional - fill.total_cost
                        positions[fill.asset_id] = positions.get(fill.asset_id, 0) - fill.qty
                        if positions[fill.asset_id] <= 0:
                            del positions[fill.asset_id]

            # Step 6: Portfolio update
            nav = cash + sum(
                qty * price_lookup.get((td, aid), {}).get("close", 0.0)
                for aid, qty in positions.items()
            )
            peak_nav = max(peak_nav, nav)

            portfolio_update = PortfolioUpdateEvent(
                trade_date=td,
                cash=cash,
                nav=nav,
                positions_count=len(positions),
                gross_exposure=sum(
                    qty * price_lookup.get((td, aid), {}).get("close", 0.0)
                    for aid, qty in positions.items()
                ),
            )
            all_portfolio_updates.append(portfolio_update)

        # Build result
        fills_df = self._build_fills_df(all_fills)
        snapshots_df = self._build_snapshots_df(all_portfolio_updates)
        port_returns = self._compute_returns(snapshots_df, spec)

        metrics = compute_metrics(
            port_returns["portfolio_return"],
            risk_free_rate=0.0,
        )

        completed_at = datetime.now(tz=timezone.utc)

        # Build weights_df from fills for positions
        weights_data = []
        for fill in all_fills:
            if fill.side == "buy":
                weights_data.append({
                    "trade_date": fill.trade_date,
                    "asset_id": fill.asset_id,
                    "target_weight": fill.notional / float(spec.initial_cash),
                })
        weights_df = pl.DataFrame(weights_data) if weights_data else pl.DataFrame()

        return BacktestResult(
            run_id=run_id,
            engine=EngineType.EVENT,
            strategy_id=spec.strategy.strategy_id,
            spec=spec,
            metrics=metrics,
            portfolio_returns=port_returns,
            net_returns=pl.DataFrame(),
            positions=weights_df,
            fills=fills_df,
            started_at=started_at,
            completed_at=completed_at,
            pretrade_decisions=pretrade_decisions,
        )

    def _build_price_lookup(self, prices: pl.DataFrame) -> dict:
        """Build price lookup dict: (trade_date, asset_id) -> price data."""
        lookup = {}
        for row in prices.iter_rows(named=True):
            td = row["trade_date"]
            aid = row["asset_id"]
            lookup[(td, aid)] = {
                "open": float(row.get("open", 0) or 0),
                "high": float(row.get("high", 0) or 0),
                "low": float(row.get("low", 0) or 0),
                "close": float(row.get("close", 0) or 0),
                "volume": float(row.get("volume", 0) or 0),
                "is_suspended": bool(row.get("is_suspended", False)),
            }

        # Compute prev_close — O(n) via sorted per-asset scan
        asset_dates: dict[str, list[date]] = {}
        for (td, aid) in lookup:
            asset_dates.setdefault(aid, []).append(td)

        for aid, dates in asset_dates.items():
            dates.sort()
            for i, td in enumerate(dates):
                data = lookup[(td, aid)]
                if i > 0:
                    prev_date = dates[i - 1]
                    data["prev_close"] = lookup.get((prev_date, aid), {}).get("close", 0.0)
                else:
                    data["prev_close"] = data["close"]

        return lookup

    def _get_day_bars(self, td: date, lookup: dict) -> list[BarEvent]:
        """Get bar events for a specific date."""
        bars = []
        for (t, aid), data in lookup.items():
            if t == td:
                bars.append(BarEvent(
                    asset_id=aid,
                    trade_date=td,
                    open=data["open"],
                    high=data["high"],
                    low=data["low"],
                    close=data["close"],
                    volume=data["volume"],
                    is_suspended=data.get("is_suspended", False),
                    prev_close=data.get("prev_close", 0.0),
                ))
        return bars

    def _is_suspended(self, td: date, asset_id: str, lookup: dict) -> bool:
        """Check if stock is suspended."""
        data = lookup.get((td, asset_id), {})
        return data.get("is_suspended", False)

    def _is_at_limit_up(self, td: date, asset_id: str, lookup: dict) -> bool:
        """Check if stock is at price limit up."""
        data = lookup.get((td, asset_id), {})
        if not data:
            return False
        close = data.get("close", 0)
        high = data.get("high", 0)
        prev_close = data.get("prev_close", 0)
        if prev_close <= 0:
            return False
        return close >= prev_close * 1.095 and close == high

    def _is_at_limit_down(self, td: date, asset_id: str, lookup: dict) -> bool:
        """Check if stock is at price limit down."""
        data = lookup.get((td, asset_id), {})
        if not data:
            return False
        close = data.get("close", 0)
        low = data.get("low", 0)
        prev_close = data.get("prev_close", 0)
        if prev_close <= 0:
            return False
        return close <= prev_close * 0.905 and close == low

    def _execute_fill(
        self, intent: OrderIntentEvent, price: float, cost_model: CostModel
    ) -> FillEvent | None:
        """Execute a fill from an order intent."""
        if intent.requested_qty <= 0 or price <= 0:
            return None

        notional = intent.requested_qty * price
        commission = float(cost_model.commission(Decimal(str(notional))))
        stamp_duty = float(cost_model.stamp_duty(
            Decimal(str(notional)),
            is_sell=(intent.side == "sell"),
        ))
        slippage = float(cost_model.slippage(Decimal(str(notional))))
        total_cost = commission + stamp_duty + slippage

        return FillEvent(
            fill_id=str(uuid.uuid4()),
            order_id=str(uuid.uuid4()),
            asset_id=intent.asset_id,
            trade_date=intent.trade_date,
            side=intent.side,
            qty=intent.requested_qty,
            price=price,
            notional=notional,
            commission=commission,
            stamp_duty=stamp_duty,
            slippage=slippage,
            total_cost=total_cost,
        )

    def _apply_risk_checks(
        self,
        weights_dict: dict[str, float],
        spec,
        trade_date: date,
        prices: pl.DataFrame,
        cash: float,
        positions: dict[str, int],
        price_lookup: dict,
    ) -> tuple[dict[str, float], list[dict]]:
        """Apply risk policies to target weights."""
        adjusted_weights: dict[str, float] = {}
        decisions: list[dict] = []

        ctx = RiskContext(
            as_of_date=trade_date,
            portfolio_nav=Decimal(str(cash)),
            current_positions=pl.DataFrame(),
        )

        snapshot = RiskSnapshot(
            snapshot_ts=datetime.combine(trade_date, datetime.min.time()),
            strategy_id=spec.strategy.strategy_id,
        )

        for asset_id, weight in weights_dict.items():
            price = price_lookup.get((trade_date, asset_id), {}).get("close", 0.0)
            if price <= 0:
                continue

            target_value = cash * weight
            requested_qty = int(target_value / price)
            requested_qty = (requested_qty // 100) * 100
            if requested_qty <= 0:
                continue

            candidate = OrderIntent(
                asset_id=asset_id,
                side=OrderSide.BUY,
                requested_qty=Decimal(str(requested_qty)),
            )

            final_qty = requested_qty
            all_reasons: list[str] = []
            all_policies: list[str] = []
            decision_type = RiskDecisionType.APPROVED

            for policy in spec.risk_policies:
                decision = policy.evaluate(candidate, snapshot, ctx, price=price)
                all_reasons.extend(decision.reasons)
                all_policies.extend(decision.policy_names)

                if decision.decision == RiskDecisionType.REJECTED:
                    decision_type = RiskDecisionType.REJECTED
                    final_qty = 0
                    break
                elif decision.decision == RiskDecisionType.CLIPPED:
                    decision_type = RiskDecisionType.CLIPPED
                    final_qty = int(decision.approved_qty)

            decisions.append({
                "decision_id": str(uuid.uuid4()),
                "trade_date": trade_date,
                "strategy_id": spec.strategy.strategy_id,
                "asset_id": asset_id,
                "requested_qty": requested_qty,
                "approved_qty": final_qty,
                "decision": decision_type.value,
                "reasons": all_reasons,
                "policy_names": all_policies,
            })

            if final_qty > 0:
                adjusted_value = final_qty * price
                adjusted_weight = adjusted_value / cash
                adjusted_weights[asset_id] = adjusted_weight

        return adjusted_weights, decisions

    def _build_fills_df(self, fills: list[FillEvent]) -> pl.DataFrame:
        """Convert fill events to DataFrame."""
        if not fills:
            return pl.DataFrame(schema={
                "trade_date": pl.Date,
                "asset_id": pl.Utf8,
                "side": pl.Utf8,
                "qty": pl.Int64,
                "price": pl.Float64,
                "notional": pl.Float64,
                "commission": pl.Float64,
                "stamp_duty": pl.Float64,
                "slippage": pl.Float64,
                "total_cost": pl.Float64,
            })

        return pl.DataFrame([{
            "trade_date": f.trade_date,
            "asset_id": f.asset_id,
            "side": f.side,
            "qty": f.qty,
            "price": f.price,
            "notional": f.notional,
            "commission": f.commission,
            "stamp_duty": f.stamp_duty,
            "slippage": f.slippage,
            "total_cost": f.total_cost,
        } for f in fills])

    def _build_snapshots_df(self, updates: list[PortfolioUpdateEvent]) -> pl.DataFrame:
        """Convert portfolio updates to DataFrame."""
        if not updates:
            return pl.DataFrame(schema={
                "trade_date": pl.Date,
                "cash": pl.Float64,
                "nav": pl.Float64,
                "positions_count": pl.Int64,
                "gross_exposure": pl.Float64,
            })

        return pl.DataFrame([{
            "trade_date": u.trade_date,
            "cash": u.cash,
            "nav": u.nav,
            "positions_count": u.positions_count,
            "gross_exposure": u.gross_exposure,
        } for u in updates])

    def _compute_returns(self, snapshots: pl.DataFrame, spec) -> pl.DataFrame:
        """Compute portfolio returns from NAV series."""
        if snapshots.is_empty():
            return pl.DataFrame(schema={
                "trade_date": pl.Date,
                "portfolio_return": pl.Float64,
                "nav": pl.Float64,
            })

        navs = snapshots["nav"].to_list()
        dates = snapshots["trade_date"].to_list()

        returns = [0.0]
        for i in range(1, len(navs)):
            if navs[i - 1] > 0:
                returns.append((navs[i] - navs[i - 1]) / navs[i - 1])
            else:
                returns.append(0.0)

        return pl.DataFrame({
            "trade_date": dates,
            "portfolio_return": returns,
            "nav": navs,
        })
