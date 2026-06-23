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
from cquant.core.enums import EngineType, OrderSide, RiskDecisionType
from cquant.core.types import OrderIntent, RiskDecision, RiskSnapshot
from cquant.riskguard.policies.forced_exit import ForcedExit, ForcedExitPolicy

if TYPE_CHECKING:
    from cquant.portfolio_opt.base import PortfolioOptimizer
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
    optimizer: "PortfolioOptimizer | None" = None
    extra: dict = field(default_factory=dict)


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
    rebalance_dates: list[date] = field(default_factory=list)
    forced_exits: list[dict] = field(default_factory=list)

    def to_summary_dict(self) -> dict:
        """返回回测结果的核心指标摘要字典。

        Returns
        -------
        dict
            包含 run_id、strategy_id 和所有 BacktestMetrics 字段的字典。
        """
        m = self.metrics
        return {
            "run_id": self.run_id,
            "strategy_id": self.strategy_id,
            "total_return": m.total_return,
            "annualized_return": m.annualized_return,
            "annualized_volatility": m.annualized_volatility,
            "sharpe_ratio": m.sharpe_ratio,
            "sortino_ratio": m.sortino_ratio,
            "max_drawdown": m.max_drawdown,
            "calmar_ratio": m.calmar_ratio,
            "win_rate": m.win_rate,
            "profit_factor": m.profit_factor,
            "var_95": m.var_95,
            "cvar_95": m.cvar_95,
            "beta": m.beta,
            "information_ratio": m.information_ratio,
            "tracking_error": m.tracking_error,
            "alpha": m.alpha,
            "omega_ratio": m.omega_ratio,
            "tail_ratio": m.tail_ratio,
            "total_trades": m.total_trades,
            "trading_days": m.trading_days,
            "error": self.error,
        }


class VectorBacktestEngine:
    """Vectorized backtest engine using polars for fast portfolio simulation.

    For MVP, this engine implements a simplified vectorized simulation without
    requiring vectorbt.  A vectorbt adapter will be added in a subsequent step.
    """

    def _compute_expected_returns(
        self,
        signals: pl.DataFrame,
        prices: pl.DataFrame,
        td: date,
        ml_predictions: dict[str, float] | None = None,
        lookback: int = 60,
    ) -> dict[str, float]:
        """Compute expected returns for signal assets.

        Priority order:
          1. ML predictions (if provided) — highest fidelity.
          2. Historical annualized return over the lookback window.
          3. Strength-based fallback (strength * 0.05).

        Parameters
        ----------
        signals:
            DataFrame with at least ``[asset_id, strength]`` columns.
        prices:
            DataFrame with ``[asset_id, trade_date, close]`` columns.
        td:
            As-of date; only price data on or before this date is used.
        ml_predictions:
            Optional mapping ``{asset_id: expected_annual_return}``.
        lookback:
            Number of most-recent trading days to use for historical return.

        Returns
        -------
        dict[str, float]
            Mapping ``{asset_id: expected_annual_return}``.
        """
        asset_ids = signals["asset_id"].to_list()

        # --- Layer 1: ML predictions ---
        if ml_predictions:
            result = {aid: ml_predictions[aid] for aid in asset_ids if aid in ml_predictions}
            if len(result) == len(asset_ids):
                return result
        else:
            result = {}

        # --- Layer 2: Historical annualized returns ---
        missing = [aid for aid in asset_ids if aid not in result]
        if missing:
            hist = prices.filter(
                (pl.col("asset_id").is_in(missing)) & (pl.col("trade_date") <= td)
            ).sort(["asset_id", "trade_date"])

            unique_dates = sorted(hist["trade_date"].unique().to_list())
            if len(unique_dates) >= 10:
                cutoff = unique_dates[-min(lookback, len(unique_dates))]
                hist = hist.filter(pl.col("trade_date") >= cutoff)

                returns = (
                    hist.group_by("asset_id")
                    .agg([
                        (pl.col("close").last() / pl.col("close").first() - 1).alias("raw_return"),
                        pl.col("trade_date").n_unique().alias("days"),
                    ])
                    .with_columns(
                        (pl.col("raw_return") * 252 / pl.col("days")).alias("annualized_return")
                    )
                )
                for row in returns.iter_rows(named=True):
                    result[row["asset_id"]] = float(row["annualized_return"])

        # --- Layer 3: Strength-based fallback ---
        # strength is in [0, 1]; map to 0~5% annualized return as a soft prior
        STRENGTH_ANNUALIZED_SCALE = 0.05
        for aid in asset_ids:
            if aid not in result:
                strength = float(signals.filter(pl.col("asset_id") == aid)["strength"].item())
                result[aid] = strength * STRENGTH_ANNUALIZED_SCALE

        return result

    def _compute_covariance(
        self,
        asset_ids: list[str],
        prices: pl.DataFrame,
        td: date,
    ) -> dict[str, dict[str, float]]:
        """Compute annualized covariance matrix for the given assets.

        Delegates to :class:`CovarianceEstimator` (historical method, 252-day
        window, min 10 periods).  Returns a square nested dict covering only
        the requested *asset_ids*.

        Parameters
        ----------
        asset_ids:
            Assets to include in the covariance matrix.
        prices:
            DataFrame with ``[asset_id, trade_date, close]`` columns.
        td:
            As-of date; only data on or before this date is used.

        Returns
        -------
        dict[str, dict[str, float]]
            ``{asset_id_a: {asset_id_b: cov_value}}``.
        """
        from cquant.portfolio_opt.covariance import CovarianceEstimator

        # Pre-filter to requested assets only — avoids O(N²) computation on full universe
        id_set = set(asset_ids)
        prices_filtered = prices.filter(pl.col("asset_id").is_in(id_set))

        estimator = CovarianceEstimator(method="historical", window=252, min_periods=10)
        cov = estimator.estimate(prices_filtered, as_of_date=td)

        return {
            a: {b: cov.get(a, {}).get(b, 0.0) for b in asset_ids}
            for a in asset_ids
        }

    def _is_rebalance_date(
        self,
        current_date: date,
        prev_date: date | None,
        rebalance_frequency: str,
    ) -> bool:
        """Check if current_date is a rebalance day based on frequency.

        Parameters
        ----------
        current_date:
            The current trading date being evaluated.
        prev_date:
            The previous trading date (None for the first date).
        rebalance_frequency:
            One of '1d'/'daily', '1w'/'weekly', '1mo'/'monthly'.

        Returns
        -------
        bool
            True if signals should be generated on this date.
        """
        if rebalance_frequency in ("1d", "daily"):
            return True

        if rebalance_frequency in ("1w", "weekly"):
            # First trading day of the week: weekday decreased (Mon=0 < Fri=4)
            if prev_date is None:
                return True
            return current_date.weekday() < prev_date.weekday()

        if rebalance_frequency in ("1mo", "monthly"):
            # First trading day of the month
            if prev_date is None:
                return True
            return current_date.month != prev_date.month

        # Unknown frequency: default to daily
        logger.warning("Unknown rebalance_frequency '%s', defaulting to daily", rebalance_frequency)
        return True

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
        rebalance_dates: list[date] = []
        # Track committed weights for building risk context positions
        committed_weights: dict[str, float] = {}
        daily_returns: list[float] = []

        # High-water mark NAV for accurate drawdown calculation
        _peak_nav = float(spec.initial_cash)
        _current_nav = float(spec.initial_cash)
        _current_drawdown = 0.0

        # Forced exit tracking
        forced_exit_policies: list[ForcedExitPolicy] = [
            p for p in spec.risk_policies if isinstance(p, ForcedExitPolicy)
        ]
        forced_exit_log: list[dict] = []
        entry_prices: dict[str, float] = {}  # asset_id -> entry price (first commit)

        for i, td in enumerate(trade_dates):
            prev_date = trade_dates[i - 1] if i > 0 else None
            is_rebalance = self._is_rebalance_date(td, prev_date, spec.rebalance_frequency)

            weights_dict: dict[str, float] = {}

            if is_rebalance:
                rebalance_dates.append(td)
                ctx = StrategyContext(
                    as_of_date=td,
                    universe_id=spec.universe_id,
                    features=spec.features,
                    prices=prices.filter(pl.col("trade_date") <= td),
                    extra=spec.extra,
                )
                signals = spec.strategy.generate_signals(ctx)

                if not signals.is_empty():
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

                    # Apply portfolio optimizer if set (overrides sizer weights)
                    if spec.optimizer is not None and weights_dict:
                        try:
                            expected_returns = self._compute_expected_returns(
                                signals, prices, td,
                                ml_predictions=spec.extra.get("ml_predictions"),
                            )
                            covariance = self._compute_covariance(
                                list(weights_dict.keys()), prices, td,
                            )
                            opt_result = spec.optimizer.optimize(expected_returns, covariance)
                            if opt_result.weights:
                                weights_dict = opt_result.weights
                        except Exception as _exc:
                            logger.warning("Optimizer skipped for %s: %s", td, _exc)

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
                            current_drawdown=_current_drawdown,
                        )
                        pretrade_decisions.extend(decisions)

                    # Update committed weights
                    if weights_dict:
                        committed_weights = weights_dict.copy()

            # Track entry prices for new positions
            for aid in committed_weights:
                if aid not in entry_prices:
                    ep = prices.filter(
                        (pl.col("trade_date") == td) & (pl.col("asset_id") == aid)
                    )
                    if not ep.is_empty():
                        entry_prices[aid] = float(ep["close"].item())

            # Forced exit check (runs every day, not just rebalance days)
            if forced_exit_policies and committed_weights:
                # Build current prices map for committed positions
                current_prices_map: dict[str, float] = {}
                for aid in committed_weights:
                    dp = prices.filter(
                        (pl.col("trade_date") == td) & (pl.col("asset_id") == aid)
                    )
                    if not dp.is_empty():
                        current_prices_map[aid] = float(dp["close"].item())

                # Build a minimal positions dict (policies only need to iterate keys)
                positions_dict = {aid: {"weight": w} for aid, w in committed_weights.items()}

                for policy in forced_exit_policies:
                    exits = policy.check_exits(
                        positions_dict, current_prices_map, entry_prices,
                    )
                    for forced_exit in exits:
                        if forced_exit.asset_id in committed_weights:
                            # Execute forced exit: remove from committed weights
                            self._execute_forced_exit(
                                forced_exit.asset_id, committed_weights,
                            )
                            # Record the event
                            ep = entry_prices.get(forced_exit.asset_id, 0)
                            cp = current_prices_map.get(forced_exit.asset_id, 0)
                            forced_exit_log.append({
                                "date": td,
                                "asset_id": forced_exit.asset_id,
                                "reason": forced_exit.reason,
                                "urgency": forced_exit.urgency,
                                "entry_price": ep,
                                "exit_price": cp,
                                "loss_pct": (cp - ep) / ep if ep else 0,
                            })

            # Always: update NAV using committed weights and today's prices
            if committed_weights:
                day_prices_map: dict[str, float] = {}
                prev_prices_map: dict[str, float] = {}
                for aid in committed_weights:
                    dp = prices.filter(
                        (pl.col("trade_date") == td) & (pl.col("asset_id") == aid)
                    )
                    if not dp.is_empty():
                        day_prices_map[aid] = float(dp["close"].item())
                    if i > 0:
                        prev_td = trade_dates[i - 1]
                        pp = prices.filter(
                            (pl.col("trade_date") == prev_td) & (pl.col("asset_id") == aid)
                        )
                        if not pp.is_empty():
                            prev_prices_map[aid] = float(pp["close"].item())

                # Compute weighted return for the day
                day_ret = 0.0
                if i > 0:
                    for aid, w in committed_weights.items():
                        p_cur = day_prices_map.get(aid)
                        p_prev = prev_prices_map.get(aid)
                        if p_cur and p_prev and p_prev > 0:
                            day_ret += w * (p_cur - p_prev) / p_prev
                    daily_returns.append(day_ret)
                    _current_nav *= (1 + day_ret)

            # 更新高水位 NAV 和当前回撤
            if _current_nav > _peak_nav:
                _peak_nav = _current_nav
            _current_drawdown = float((_current_nav - _peak_nav) / _peak_nav) if _peak_nav > 0 else 0.0

            # NEXT-BAR EXECUTION: signal on day T, execute on day T+1
            # Only add weights on rebalance days when new signals were generated
            if is_rebalance and weights_dict and i + 1 < len(trade_dates):
                exec_date = trade_dates[i + 1]
                for asset_id, w in weights_dict.items():
                    all_weights.append({"trade_date": exec_date, "asset_id": asset_id, "target_weight": w})

        if not all_weights:
            raise ValueError("Strategy produced no signals for the backtest period")

        weights_df = pl.DataFrame(all_weights)

        # Use fill simulator for realistic A-share execution
        # Pass max_volume_pct from spec.extra if configured
        max_volume_pct = spec.extra.get("max_volume_pct", 0.1)
        fill_sim = AShareFillSimulator(
            cost_model=spec.cost_model,
            max_volume_pct=max_volume_pct,
        )
        fills_df, snapshots_df = fill_sim.simulate(
            target_weights=weights_df,
            prices=prices,
            initial_cash=spec.initial_cash,
        )

        # Compute portfolio returns from fill simulator NAV
        port_returns = self._compute_returns_from_nav(snapshots_df, spec)

        # Compute benchmark returns if a benchmark asset is specified
        benchmark_returns = None
        if spec.benchmark_asset_id:
            bm_prices = spec.prices.filter(
                (pl.col("asset_id") == spec.benchmark_asset_id)
                & (pl.col("trade_date") >= spec.start_date)
                & (pl.col("trade_date") <= spec.end_date)
            ).sort("trade_date")
            if not bm_prices.is_empty():
                bm_rets = (
                    bm_prices
                    .with_columns(
                        pl.col("close").log().diff().alias("_bm_ret")
                    )
                    .drop_nulls("_bm_ret")
                )
                if not bm_rets.is_empty():
                    benchmark_returns = bm_rets["_bm_ret"]

        # 计算真实成交笔数
        total_fills = len(fills_df) if not fills_df.is_empty() else 0

        metrics = compute_metrics(
            port_returns["portfolio_return"],
            risk_free_rate=0.0,
            benchmark_returns=benchmark_returns,
            total_fills=total_fills,
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
            rebalance_dates=rebalance_dates,
            forced_exits=forced_exit_log,
        )

    def _apply_risk_checks(
        self,
        weights_dict: dict[str, float],
        spec: BacktestSpec,
        trade_date: date,
        prices: pl.DataFrame,
        accumulated_positions: pl.DataFrame | None = None,
        daily_returns: list[float] | None = None,
        current_drawdown: float = 0.0,
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

        # Use the accurate drawdown passed from _run_impl (tracked via _peak_nav)
        # Fall back to computing from daily_returns if current_drawdown is default 0.0
        # and daily_returns are available (backward compatibility)
        drawdown = current_drawdown
        if drawdown == 0.0 and daily_returns:
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
                decision = policy.evaluate(candidate, snapshot, ctx)
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

    @staticmethod
    def _execute_forced_exit(
        asset_id: str,
        committed_weights: dict[str, float],
    ) -> None:
        """Execute a forced exit by removing the asset from committed weights.

        This immediately stops tracking the position so it no longer
        contributes to NAV calculations on subsequent days.

        Parameters
        ----------
        asset_id:
            Identifier of the asset to liquidate.
        committed_weights:
            Mutable mapping ``{asset_id: weight}`` — the entry for
            *asset_id* is deleted in-place.
        """
        if asset_id in committed_weights:
            del committed_weights[asset_id]

