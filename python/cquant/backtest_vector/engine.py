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
from cquant.riskguard.policies.stop_loss import TrailingStopLossPolicy
from cquant.riskguard.policies.atr_stop_loss import ATRStopLossPolicy

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

    @staticmethod
    def _build_price_matrix(prices: pl.DataFrame) -> tuple[pl.DataFrame, dict[date, int]]:
        """Pre-compute price matrix for O(1) lookups.

        Pivots the long-format prices DataFrame into a wide matrix indexed by
        trade_date with one column per asset_id.

        Parameters
        ----------
        prices:
            Long-format DataFrame with ``[asset_id, trade_date, close]`` columns.

        Returns
        -------
        tuple[pl.DataFrame, dict[date, int]]
            ``(price_matrix, date_to_idx)`` where *price_matrix* has
            ``trade_date`` as the first column followed by asset columns,
            and *date_to_idx* maps each trade_date to its row index.
        """
        # Pivot to wide: rows = trade_dates, columns = asset_ids
        price_matrix = prices.pivot(
            index="trade_date", on="asset_id", values="close"
        ).sort("trade_date")

        trade_dates = price_matrix["trade_date"].to_list()
        date_to_idx = {d: i for i, d in enumerate(trade_dates)}

        return price_matrix, date_to_idx

    def _get_price_on_date(
        self,
        asset_id: str,
        td: date,
        date_to_idx: dict[date, int],
        price_matrix: pl.DataFrame,
    ) -> float | None:
        """Get close price for a single asset on a specific date. O(1).

        Parameters
        ----------
        asset_id:
            Asset identifier.
        td:
            Trade date.
        date_to_idx:
            Mapping from date to row index in *price_matrix*.
        price_matrix:
            Wide-format price matrix from :meth:`_build_price_matrix`.

        Returns
        -------
        float | None
            Close price, or ``None`` if asset/date not found.
        """
        idx = date_to_idx.get(td)
        if idx is None:
            return None
        if asset_id not in price_matrix.columns:
            return None
        val = price_matrix.row(idx, named=True).get(asset_id)
        return float(val) if val is not None else None

    def _get_prices_on_date(
        self,
        td: date,
        date_to_idx: dict[date, int],
        price_matrix: pl.DataFrame,
        asset_ids: list[str] | None = None,
    ) -> dict[str, float]:
        """Get prices for multiple assets on a specific date. O(1) per asset.

        Parameters
        ----------
        td:
            Trade date.
        date_to_idx:
            Mapping from date to row index in *price_matrix*.
        price_matrix:
            Wide-format price matrix from :meth:`_build_price_matrix`.
        asset_ids:
            Optional list of asset IDs to filter. If ``None``, returns all.

        Returns
        -------
        dict[str, float]
            Mapping ``{asset_id: close_price}`` for assets with valid prices.
        """
        idx = date_to_idx.get(td)
        if idx is None:
            return {}
        row = price_matrix.row(idx, named=True)
        if asset_ids is not None:
            return {
                aid: float(row[aid])
                for aid in asset_ids
                if aid in row and row[aid] is not None
            }
        return {
            k: float(v)
            for k, v in row.items()
            if k != "trade_date" and v is not None
        }

    def _get_prices_up_to(
        self,
        td: date,
        date_to_idx: dict[date, int],
        price_matrix: pl.DataFrame,
    ) -> pl.DataFrame:
        """Get price matrix slice up to and including *td*. O(1).

        Parameters
        ----------
        td:
            Trade date (inclusive upper bound).
        date_to_idx:
            Mapping from date to row index in *price_matrix*.
        price_matrix:
            Wide-format price matrix from :meth:`_build_price_matrix`.

        Returns
        -------
        pl.DataFrame
            Subset of *price_matrix* with rows ``<= idx``.
        """
        idx = date_to_idx.get(td)
        if idx is None:
            return price_matrix.clear()
        return price_matrix.head(idx + 1)

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

        # Pre-compute price matrices for O(1) lookups
        price_matrix, date_to_idx = self._build_price_matrix(prices)

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

        # Drawdown tracking (real NAV comes from FillSimulator after the loop)
        current_drawdown = 0.0
        nav_estimate = 1.0      # normalized NAV (starts at 1.0)
        peak_nav = 1.0          # running peak NAV

        # Forced exit tracking
        forced_exit_policies: list[ForcedExitPolicy] = [
            p for p in spec.risk_policies if isinstance(p, ForcedExitPolicy)
        ]
        forced_exit_log: list[dict] = []
        force_exited_assets: set[str] = set()  # cooldown until next rebalance
        pending_force_exits: set[str] = set()  # re-inject zero-weight for T+1 blocked sells
        entry_prices: dict[str, float] = {}  # asset_id -> entry price (first commit)

        # State dicts for forced exit policies
        trailing_state: dict = {"peak_prices": {}}
        atr_state: dict = {"atr_values": {}}

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
                # Exclude force-exited stocks (cooldown until next rebalance)
                if force_exited_assets:
                    signals = signals.filter(~pl.col("asset_id").is_in(list(force_exited_assets)))

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
                        # Build positions from previously committed weights (O(1) lookup)
                        accumulated_pos = self._build_positions_from_weights(
                            committed_weights, td, prices, spec.initial_cash,
                            date_to_idx=date_to_idx, price_matrix=price_matrix,
                        ) if committed_weights else pl.DataFrame()

                        weights_dict, decisions = self._apply_risk_checks(
                            weights_dict, spec, td, prices,
                            accumulated_positions=accumulated_pos,
                            daily_returns=daily_returns,
                            current_drawdown=current_drawdown,
                            date_to_idx=date_to_idx,
                            price_matrix=price_matrix,
                        )
                        pretrade_decisions.extend(decisions)

                    # Save old weights for turnover calculation
                    old_weights = committed_weights.copy() if committed_weights else {}

                    # Update committed weights
                    if weights_dict:
                        committed_weights = weights_dict.copy()

                    # Deduct estimated turnover cost from NAV estimate
                    if weights_dict and nav_estimate > 0:
                        all_assets = set(old_weights.keys()) | set(weights_dict.keys())
                        turnover = sum(
                            abs(weights_dict.get(a, 0) - old_weights.get(a, 0))
                            for a in all_assets
                        )
                        cost_model = spec.cost_model
                        est_cost_rate = float(cost_model.commission_rate) * 2 + float(cost_model.stamp_duty_rate) + float(cost_model.slippage_rate)
                        nav_estimate *= (1 - turnover * est_cost_rate)
                        peak_nav = max(peak_nav, nav_estimate)

                    # Always clear on rebalance, regardless of weights_dict
                    force_exited_assets.clear()
                    pending_force_exits.clear()

            # Track entry prices for new positions (O(1) per asset)
            for aid in committed_weights:
                if aid not in entry_prices:
                    price = self._get_price_on_date(aid, td, date_to_idx, price_matrix)
                    if price is not None:
                        entry_prices[aid] = price

            # Update peak prices for trailing stop
            for aid in committed_weights:
                price = self._get_price_on_date(aid, td, date_to_idx, price_matrix)
                if price is not None:
                    current_peak = trailing_state["peak_prices"].get(aid, price)
                    if price > current_peak:
                        trailing_state["peak_prices"][aid] = price

            # Forced exit check (runs every day, not just rebalance days)
            if forced_exit_policies and committed_weights:
                # Build current prices map for committed positions (O(N) batch)
                current_prices_map = self._get_prices_on_date(
                    td, date_to_idx, price_matrix, list(committed_weights.keys())
                )

                # Compute ATR for committed positions (if any ATR policy is active)
                if any(isinstance(p, ATRStopLossPolicy) for p in forced_exit_policies):
                    from cquant.riskguard.policies.atr_stop_loss import compute_atr
                    atr_prices = prices.filter(
                        (pl.col("trade_date") <= td)
                        & (pl.col("asset_id").is_in(list(committed_weights.keys())))
                    )
                    atr_state["atr_values"] = compute_atr(atr_prices)

                # Build a minimal positions dict (policies only need to iterate keys)
                positions_dict = {aid: {"weight": w} for aid, w in committed_weights.items()}

                for policy in forced_exit_policies:
                    # Determine state dict based on policy type
                    if isinstance(policy, TrailingStopLossPolicy):
                        state = trailing_state
                    elif isinstance(policy, ATRStopLossPolicy):
                        state = atr_state
                    else:
                        state = None

                    exits = policy.check_exits(
                        positions_dict, current_prices_map, entry_prices,
                        state=state,
                    )
                    for forced_exit in exits:
                        if forced_exit.asset_id in committed_weights:
                            # Execute forced exit: remove from committed weights
                            self._execute_forced_exit(
                                forced_exit.asset_id, committed_weights,
                                all_weights, td,
                            )
                            # Add to cooldown set
                            force_exited_assets.add(forced_exit.asset_id)
                            pending_force_exits.add(forced_exit.asset_id)
                            # Record the event (read entry price BEFORE popping)
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
                            # Clean up entry price after logging
                            entry_prices.pop(forced_exit.asset_id, None)
                            # Clean up state for force-exited asset
                            trailing_state["peak_prices"].pop(forced_exit.asset_id, None)
                            atr_state["atr_values"].pop(forced_exit.asset_id, None)

            # Track daily returns for risk decisions (approximate NAV removed;
            # real NAV comes from FillSimulator after the loop)
            if committed_weights and i > 0:
                # Batch fetch prices for all committed assets (O(N) instead of O(N*T))
                asset_list = list(committed_weights.keys())
                day_prices_map = self._get_prices_on_date(
                    td, date_to_idx, price_matrix, asset_list
                )
                prev_td = trade_dates[i - 1]
                prev_prices_map = self._get_prices_on_date(
                    prev_td, date_to_idx, price_matrix, asset_list
                )

                # Compute weighted return for the day
                day_ret = 0.0
                for aid, w in committed_weights.items():
                    p_cur = day_prices_map.get(aid)
                    p_prev = prev_prices_map.get(aid)
                    if p_cur and p_prev and p_prev > 0:
                        day_ret += w * (p_cur - p_prev) / p_prev
                daily_returns.append(day_ret)

                # Incremental NAV estimate (O(1) per day)
                nav_estimate *= (1 + day_ret)
                peak_nav = max(peak_nav, nav_estimate)
                current_drawdown = (nav_estimate - peak_nav) / peak_nav if peak_nav > 0 else 0.0

            # Re-inject zero-weight for pending force exits (handles T+1 blocked sells)
            if pending_force_exits and i + 1 < len(trade_dates):
                next_td = trade_dates[i + 1]
                for fe_asset in list(pending_force_exits):
                    all_weights.append({"trade_date": next_td, "asset_id": fe_asset, "target_weight": 0.0})

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
        date_to_idx: dict[date, int] | None = None,
        price_matrix: pl.DataFrame | None = None,
    ) -> tuple[dict[str, float], list[dict]]:
        """Apply risk policies to target weights. Returns adjusted weights and decisions.

        Args:
            weights_dict: Target weights for this rebalance date.
            spec: Backtest specification.
            trade_date: Current evaluation date.
            prices: Full prices DataFrame (used for position building if matrix not provided).
            accumulated_positions: Positions from prior fills (may be empty).
            daily_returns: Returns accumulated so far (for drawdown computation).
            date_to_idx: Optional pre-computed date-to-index mapping for O(1) lookups.
            price_matrix: Optional pre-computed price matrix for O(1) lookups.
        """
        adjusted_weights: dict[str, float] = {}
        decisions: list[dict] = []

        # Build positions from current target weights combined with prior holdings
        current_positions = self._build_positions_from_weights(
            weights_dict, trade_date, prices, spec.initial_cash,
            date_to_idx=date_to_idx, price_matrix=price_matrix,
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

        # Use incremental drawdown from NAV estimator (O(1) per call)
        drawdown = current_drawdown

        # Create a risk snapshot with real values
        snapshot = RiskSnapshot(
            snapshot_ts=datetime.combine(trade_date, datetime.min.time()),
            strategy_id=spec.strategy.strategy_id,
            gross_leverage=1.0,
            net_leverage=1.0,
            drawdown=drawdown,
        )

        for asset_id, weight in weights_dict.items():
            # Get current price for this asset (O(1) with matrix)
            if date_to_idx is not None and price_matrix is not None:
                price = self._get_price_on_date(asset_id, trade_date, date_to_idx, price_matrix) or 0.0
            else:
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
        date_to_idx: dict[date, int] | None = None,
        price_matrix: pl.DataFrame | None = None,
    ) -> pl.DataFrame:
        """Build a positions DataFrame from target weights and prices.

        Args:
            weights_dict: asset_id -> target weight (fraction of NAV).
            trade_date: Current date for price lookup.
            prices: Full prices DataFrame (fallback if matrix not provided).
            nav: Current portfolio NAV.
            date_to_idx: Optional pre-computed date-to-index mapping for O(1) lookups.
            price_matrix: Optional pre-computed price matrix for O(1) lookups.

        Returns:
            DataFrame with [asset_id, quantity, market_value].
        """
        rows = []
        nav_float = float(nav)

        # Use matrix for O(1) lookups if available
        if date_to_idx is not None and price_matrix is not None:
            prices_on_date = self._get_prices_on_date(
                trade_date, date_to_idx, price_matrix, list(weights_dict.keys())
            )
            for asset_id, weight in weights_dict.items():
                price = prices_on_date.get(asset_id)
                if price is None or price <= 0:
                    continue
                market_value = nav_float * weight
                quantity = market_value / price
                rows.append({
                    "asset_id": asset_id,
                    "quantity": quantity,
                    "market_value": market_value,
                })
        else:
            # Fallback to DataFrame filter
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
        all_weights: list[dict],
        exit_date: date,
    ) -> None:
        """Execute a forced exit: remove from committed weights and inject sell order.

        Note: static because it doesn't access instance state; it mutates
        the passed-in dicts directly.

        Removes the asset from *committed_weights* so it stops contributing to
        NAV, and appends a ``target_weight=0`` entry into *all_weights* so
        FillSimulator will generate a proper sell fill.

        Parameters
        ----------
        asset_id:
            Identifier of the asset to liquidate.
        committed_weights:
            Mutable mapping ``{asset_id: weight}`` — the entry for
            *asset_id* is deleted in-place.
        all_weights:
            Mutable list of weight dicts consumed by FillSimulator.
            A zero-weight entry is appended for the forced exit.
        exit_date:
            Trade date on which the forced exit is executed.
        """
        if asset_id in committed_weights:
            del committed_weights[asset_id]
            # Inject zero-weight entry so FillSimulator will sell
            all_weights.append({"trade_date": exit_date, "asset_id": asset_id, "target_weight": 0.0})

