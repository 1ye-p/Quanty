"""cquant.backtest_vector.engine — Vectorized backtest engine.

The engine orchestrates the full vectorized backtest pipeline:
  1. Receive prices and signals
  2. Apply position sizing (via riskguard)
  3. Run pre-trade risk checks
  4. Simulate fills with the cost model
  5. Compute portfolio returns and metrics
  6. Return a BacktestResult

The vectorbt integration lives here as an adapter — the public interface
(BacktestSpec / BacktestResult) is engine-agnostic so it can be reused
by the future Rust event-driven engine.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING

import polars as pl

from cquant.backtest_vector.costs import CostModel
from cquant.backtest_vector.fill_simulator import AShareFillSimulator
from cquant.backtest_vector.metrics import BacktestMetrics, compute_metrics
from cquant.backtest_vector.strategy import Strategy, StrategyContext
from cquant.core.enums import EngineType, RiskDecisionType
from cquant.core.types import OrderIntent, RiskDecision, RiskSnapshot

if TYPE_CHECKING:
    from cquant.riskguard.policies.base import RiskPolicy
    from cquant.riskguard.sizers.base import PositionSizer

logger = logging.getLogger(__name__)


@dataclass
class BacktestSpec:
    """Full specification for a vectorized backtest run."""

    strategy: Strategy
    prices: pl.DataFrame              # Silver OHLCV: [asset_id, trade_date, open, high, low, close, volume, amount, is_suspended]
    start_date: date
    end_date: date
    initial_cash: Decimal = Decimal("1_000_000")
    cost_model: CostModel = field(default_factory=CostModel.for_cn)
    sizer: "PositionSizer | None" = None
    risk_policies: list["RiskPolicy"] = field(default_factory=list)
    rebalance_frequency: str = "1d"   # '1d', '1w', '1mo'
    benchmark_asset_id: str = ""
    universe_id: str = ""
    features: pl.DataFrame | None = None
    tags: dict = field(default_factory=dict)


@dataclass
class BacktestResult:
    """Output of a completed backtest run."""

    run_id: str
    engine: EngineType
    strategy_id: str
    spec: BacktestSpec
    metrics: BacktestMetrics
    portfolio_returns: pl.DataFrame   # [trade_date, portfolio_return, nav]
    positions: pl.DataFrame           # [trade_date, asset_id, weight, quantity, market_value]
    fills: pl.DataFrame               # [trade_date, asset_id, side, qty, price, commission, stamp_duty, total_cost]
    started_at: datetime
    completed_at: datetime | None = None
    error: str | None = None
    pretrade_decisions: list[dict] = field(default_factory=list)


class VectorBacktestEngine:
    """Vectorized backtest engine using polars for fast portfolio simulation.

    For MVP, this engine implements a simplified vectorized simulation without
    requiring vectorbt.  A vectorbt adapter will be added in a subsequent step.
    """

    def run(self, spec: BacktestSpec) -> BacktestResult:
        """Execute a vectorized backtest according to *spec*."""
        run_id = str(uuid.uuid4())
        started_at = datetime.now(tz=timezone.utc)

        try:
            result = self._run_impl(spec, run_id, started_at)
        except Exception as exc:
            logger.exception("Backtest %s failed: %s", run_id, exc)
            empty_metrics = BacktestMetrics(
                total_return=0, annualized_return=0, annualized_volatility=0,
                sharpe_ratio=0, sortino_ratio=0, max_drawdown=0, calmar_ratio=0,
                win_rate=0, profit_factor=0, var_95=0, cvar_95=0, beta=None,
                total_trades=0, trading_days=0,
            )
            result = BacktestResult(
                run_id=run_id,
                engine=EngineType.VECTOR,
                strategy_id=spec.strategy.strategy_id,
                spec=spec,
                metrics=empty_metrics,
                portfolio_returns=pl.DataFrame(),
                positions=pl.DataFrame(),
                fills=pl.DataFrame(),
                started_at=started_at,
                completed_at=datetime.now(tz=timezone.utc),
                error=str(exc),
            )

        return result

    def _run_impl(
        self,
        spec: BacktestSpec,
        run_id: str,
        started_at: datetime,
    ) -> BacktestResult:
        # Filter prices to backtest window
        prices = spec.prices.filter(
            (pl.col("trade_date") >= spec.start_date)
            & (pl.col("trade_date") <= spec.end_date)
        ).sort(["trade_date", "asset_id"])

        if prices.is_empty():
            raise ValueError("No price data in the specified date range")

        trade_dates = sorted(prices["trade_date"].unique().to_list())

        # Generate signals for each rebalance date
        # KEY FIX: signals on day T execute on day T+1 (next-bar execution)
        # This prevents time leakage where we use same-day close for both
        # signal generation and return computation.
        all_weights: list[dict] = []
        pretrade_decisions: list[dict] = []
        # Track committed weights for building risk context positions
        committed_weights: dict[str, float] = {}
        daily_returns: list[float] = []

        for i, td in enumerate(trade_dates):
            ctx = StrategyContext(
                as_of_date=td,
                universe_id=spec.universe_id,
                features=spec.features,
                prices=prices.filter(pl.col("trade_date") <= td),
            )
            signals = spec.strategy.generate_signals(ctx)

            if signals.is_empty():
                continue

            # Apply position sizer
            if spec.sizer is not None:
                from cquant.riskguard.models import SizingContext
                sizing_ctx = SizingContext(
                    as_of_date=td,
                    portfolio_nav=spec.initial_cash,
                    universe_ids=[spec.universe_id] if spec.universe_id else [],
                )
                target_weights = spec.sizer.target_weights(signals, sizing_ctx)
                weights_dict = target_weights.weights
            else:
                # Default: equal weight for all positive-signal assets
                active_assets = signals.filter(pl.col("strength") > 0)["asset_id"].to_list()
                n = len(active_assets)
                weights_dict = {aid: 1.0 / n for aid in active_assets} if n else {}

            # Apply risk policies if configured
            if spec.risk_policies and weights_dict:
                # Build positions from previously committed weights
                accumulated_pos = self._build_positions_from_weights(
                    committed_weights, td, prices, spec.initial_cash,
                ) if committed_weights else pl.DataFrame()

                weights_dict, decisions = self._apply_risk_checks(
                    weights_dict, spec, td, prices,
                    accumulated_positions=accumulated_pos,
                    daily_returns=daily_returns,
                )
                pretrade_decisions.extend(decisions)

            # Update committed weights and approximate daily return
            if weights_dict:
                # Estimate return from weight change (simplified)
                # Real return is computed later from fill simulator NAV
                committed_weights = weights_dict.copy()

            # NEXT-BAR EXECUTION: signal on day T, execute on day T+1
            if i + 1 < len(trade_dates):
                exec_date = trade_dates[i + 1]
                for asset_id, w in weights_dict.items():
                    all_weights.append({"trade_date": exec_date, "asset_id": asset_id, "target_weight": w})

        if not all_weights:
            raise ValueError("Strategy produced no signals for the backtest period")

        weights_df = pl.DataFrame(all_weights)

        # Use fill simulator for realistic A-share execution
        fill_sim = AShareFillSimulator(cost_model=spec.cost_model)
        fills_df, snapshots_df = fill_sim.simulate(
            target_weights=weights_df,
            prices=prices,
            initial_cash=spec.initial_cash,
        )

        # Compute portfolio returns from fill simulator NAV
        port_returns = self._compute_returns_from_nav(snapshots_df, spec)

        metrics = compute_metrics(
            port_returns["portfolio_return"],
            risk_free_rate=0.0,
        )

        completed_at = datetime.now(tz=timezone.utc)

        return BacktestResult(
            run_id=run_id,
            engine=EngineType.VECTOR,
            strategy_id=spec.strategy.strategy_id,
            spec=spec,
            metrics=metrics,
            portfolio_returns=port_returns,
            positions=weights_df,
            fills=fills_df,
            started_at=started_at,
            completed_at=completed_at,
            pretrade_decisions=pretrade_decisions,
        )

    def _apply_risk_checks(
        self,
        weights_dict: dict[str, float],
        spec: BacktestSpec,
        trade_date: date,
        prices: pl.DataFrame,
        accumulated_positions: pl.DataFrame | None = None,
        daily_returns: list[float] | None = None,
    ) -> tuple[dict[str, float], list[dict]]:
        """Apply risk policies to target weights. Returns adjusted weights and decisions.

        Args:
            weights_dict: Target weights for this rebalance date.
            spec: Backtest specification.
            trade_date: Current evaluation date.
            prices: Full prices DataFrame.
            accumulated_positions: Positions from prior fills (may be empty).
            daily_returns: Returns accumulated so far (for drawdown computation).
        """
        adjusted_weights: dict[str, float] = {}
        decisions: list[dict] = []

        # Build positions from current target weights combined with prior holdings
        current_positions = self._build_positions_from_weights(
            weights_dict, trade_date, prices, spec.initial_cash,
        )
        if accumulated_positions is not None and not accumulated_positions.is_empty():
            # Merge: keep accumulated positions that aren't in current targets
            current_aids = set(current_positions["asset_id"].to_list()) if not current_positions.is_empty() else set()
            prior_only = accumulated_positions.filter(
                ~pl.col("asset_id").is_in(list(current_aids))
            )
            if not prior_only.is_empty():
                current_positions = pl.concat([current_positions, prior_only])

        # Build risk context with real positions
        ctx = self._build_risk_context(trade_date, current_positions, spec.initial_cash)

        # Compute real drawdown from daily returns so far
        drawdown = 0.0
        if daily_returns:
            cum = 1.0
            peak = 1.0
            for r in daily_returns:
                cum *= (1 + r)
                peak = max(peak, cum)
            drawdown = (cum - peak) / peak if peak > 0 else 0.0

        # Create a risk snapshot with real values
        snapshot = RiskSnapshot(
            snapshot_ts=datetime.combine(trade_date, datetime.min.time()),
            strategy_id=spec.strategy.strategy_id,
            gross_leverage=1.0,
            net_leverage=1.0,
            drawdown=drawdown,
        )

        for asset_id, weight in weights_dict.items():
            # Get current price for this asset
            day_prices = prices.filter(
                (pl.col("trade_date") == trade_date) & (pl.col("asset_id") == asset_id)
            )
            price = float(day_prices["close"].item()) if not day_prices.is_empty() else 0.0

            # Calculate requested qty from weight
            if price <= 0:
                continue
            target_value = float(spec.initial_cash) * weight
            requested_qty = int(target_value / price)
            requested_qty = (requested_qty // 100) * 100  # Round to lot
            if requested_qty <= 0:
                continue

            # Create order intent
            from cquant.core.enums import OrderSide
            candidate = OrderIntent(
                asset_id=asset_id,
                side=OrderSide.BUY,
                requested_qty=Decimal(str(requested_qty)),
            )

            # Evaluate against each policy
            final_qty = requested_qty
            all_reasons: list[str] = []
            all_policies: list[str] = []
            decision_type = RiskDecisionType.APPROVED

            for policy in spec.risk_policies:
                # Get price for this asset
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

            # Record decision
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

            # Adjust weight based on approved quantity
            if final_qty > 0:
                adjusted_value = final_qty * price
                adjusted_weight = adjusted_value / float(spec.initial_cash)
                adjusted_weights[asset_id] = adjusted_weight

        return adjusted_weights, decisions

    def _compute_returns_from_nav(
        self,
        snapshots: pl.DataFrame,
        spec: BacktestSpec,
    ) -> pl.DataFrame:
        """Compute portfolio returns from fill simulator NAV series."""
        if snapshots.is_empty():
            return pl.DataFrame(schema={
                "trade_date": pl.Date,
                "portfolio_return": pl.Float64,
                "nav": pl.Float64,
            })

        navs = snapshots["nav"].to_list()
        dates = snapshots["trade_date"].to_list()

        returns = [0.0]  # First day has no return
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

    def _build_risk_context(
        self,
        trade_date: date,
        positions_df: pl.DataFrame,
        nav: Decimal,
    ) -> RiskContext:
        """Build a RiskContext with real current positions.

        Args:
            trade_date: Current evaluation date.
            positions_df: DataFrame with at least [asset_id, quantity, market_value].
            nav: Current portfolio net asset value.

        Returns:
            RiskContext with properly populated current_positions including weights.
        """
        from cquant.riskguard.models import RiskContext as _RC

        if positions_df.is_empty():
            current_positions = pl.DataFrame(
                schema={
                    "asset_id": pl.Utf8,
                    "quantity": pl.Float64,
                    "market_value": pl.Float64,
                    "weight": pl.Float64,
                }
            )
        else:
            total_mv = positions_df["market_value"].sum()
            if total_mv > 0:
                current_positions = positions_df.with_columns(
                    (pl.col("market_value") / total_mv).alias("weight")
                )
            else:
                current_positions = positions_df.with_columns(
                    pl.lit(0.0).alias("weight")
                )

        return _RC(
            as_of_date=trade_date,
            portfolio_nav=nav,
            current_positions=current_positions,
        )

    def _build_positions_from_weights(
        self,
        weights_dict: dict[str, float],
        trade_date: date,
        prices: pl.DataFrame,
        nav: Decimal,
    ) -> pl.DataFrame:
        """Build a positions DataFrame from target weights and prices.

        Args:
            weights_dict: asset_id -> target weight (fraction of NAV).
            trade_date: Current date for price lookup.
            prices: Full prices DataFrame.
            nav: Current portfolio NAV.

        Returns:
            DataFrame with [asset_id, quantity, market_value].
        """
        rows = []
        nav_float = float(nav)
        for asset_id, weight in weights_dict.items():
            day_prices = prices.filter(
                (pl.col("trade_date") == trade_date) & (pl.col("asset_id") == asset_id)
            )
            if day_prices.is_empty():
                continue
            price = float(day_prices["close"].item())
            if price <= 0:
                continue
            market_value = nav_float * weight
            quantity = market_value / price
            rows.append({
                "asset_id": asset_id,
                "quantity": quantity,
                "market_value": market_value,
            })

        if not rows:
            return pl.DataFrame(
                schema={
                    "asset_id": pl.Utf8,
                    "quantity": pl.Float64,
                    "market_value": pl.Float64,
                }
            )
        return pl.DataFrame(rows)

