"""cquant.backtest_vector.run — Backtest runner with DuckDB persistence.

Loads data from silver/gold layers, runs VectorBacktestEngine, persists
results to gold_backtest_runs.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import polars as pl

from cquant.backtest_vector.costs import CostModel
from cquant.backtest_vector.engine import BacktestSpec, VectorBacktestEngine
from cquant.backtest_vector.strategy import Strategy, StrategyContext
from cquant.core.enums import EngineType, Market
from cquant.core.types import SignalFrame
from cquant.datahub.catalog import Catalog
from cquant.riskguard.policies.base import RiskPolicy
from cquant.riskguard.policies.position_limits import PositionLimitPolicy

logger = logging.getLogger(__name__)


@dataclass
class BacktestRunSpec:
    """Specification for a backtest run with DuckDB persistence."""

    dataset_version: str
    strategy_id: str
    start_date: date
    end_date: date
    feature_set_version: str = ""
    benchmark_asset_id: str = ""
    initial_cash: Decimal = Decimal("1_000_000")
    top_n: int = 10
    sort_factor: str = "ret_20d"
    tags: dict = field(default_factory=dict)
    risk_policies: list[RiskPolicy] = field(default_factory=list)


class StaticTopNStrategy(Strategy):
    """Simple cross-sectional momentum strategy: long top N by factor rank.

    Each rebalance date, ranks assets by `sort_factor` descending,
    takes the top `n` assets, and assigns equal signal strength.
    """

    def __init__(self, strategy_id: str, top_n: int = 10, sort_factor: str = "ret_20d") -> None:
        self._strategy_id = strategy_id
        self._top_n = top_n
        self._sort_factor = sort_factor

    @property
    def strategy_id(self) -> str:
        return self._strategy_id

    def generate_signals(self, ctx: StrategyContext) -> SignalFrame:
        import polars as pl

        if ctx.features is None or ctx.features.is_empty():
            return pl.DataFrame(
                schema={"asset_id": pl.Utf8, "signal_date": pl.Date,
                        "direction": pl.Utf8, "strength": pl.Float64, "confidence": pl.Float64}
            )

        # Get the latest factor values for this date
        day_features = ctx.features.filter(pl.col("trade_date") == ctx.as_of_date)
        if day_features.is_empty():
            return pl.DataFrame(
                schema={"asset_id": pl.Utf8, "signal_date": pl.Date,
                        "direction": pl.Utf8, "strength": pl.Float64, "confidence": pl.Float64}
            )

        if self._sort_factor not in day_features.columns:
            return pl.DataFrame(
                schema={"asset_id": pl.Utf8, "signal_date": pl.Date,
                        "direction": pl.Utf8, "strength": pl.Float64, "confidence": pl.Float64}
            )

        # Rank by factor, take top N
        ranked = (
            day_features
            .drop_nulls([self._sort_factor])
            .sort(self._sort_factor, descending=True)
            .head(self._top_n)
        )

        if ranked.is_empty():
            return pl.DataFrame(
                schema={"asset_id": pl.Utf8, "signal_date": pl.Date,
                        "direction": pl.Utf8, "strength": pl.Float64, "confidence": pl.Float64}
            )

        return ranked.select([
            pl.col("asset_id"),
            pl.lit(ctx.as_of_date).alias("signal_date"),
            pl.lit("long").alias("direction"),
            pl.lit(1.0).alias("strength"),
            pl.lit(1.0).alias("confidence"),
        ])


class BacktestRunner:
    """Run backtests with data from DuckDB and persist results.

    Usage::

        runner = BacktestRunner(catalog)
        run_id = runner.run(BacktestRunSpec(
            dataset_version="...",
            strategy_id="top10_momentum",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        ))
    """

    def __init__(self, catalog: Catalog) -> None:
        self._catalog = catalog
        self._engine = VectorBacktestEngine()

    def run(self, spec: BacktestRunSpec) -> str:
        """Execute a backtest and persist results. Returns run_id."""
        self._catalog.initialize()

        prices = self._load_prices(spec)
        if prices.is_empty():
            raise ValueError(f"No price data for {spec.start_date} to {spec.end_date}")

        features = self._load_features(spec)
        strategy = self._build_strategy(spec)

        # Determine cost model based on asset_id patterns
        cost_model = self._detect_cost_model(prices)

        bt_spec = BacktestSpec(
            strategy=strategy,
            prices=prices,
            start_date=spec.start_date,
            end_date=spec.end_date,
            initial_cash=spec.initial_cash,
            cost_model=cost_model,
            features=features,
            tags=spec.tags,
            risk_policies=spec.risk_policies,
        )

        result = self._engine.run(bt_spec)
        run_id = self._persist_run(result, spec)
        self._persist_signals(result, run_id, spec)
        self._persist_fills(result, run_id)
        self._persist_positions(result, run_id)
        self._persist_portfolio_snapshots(result, run_id)
        self._persist_risk_snapshots(result, run_id)
        if result.pretrade_decisions:
            self._persist_pretrade_decisions(result, run_id)
        return run_id

    def _load_prices(self, spec: BacktestRunSpec) -> pl.DataFrame:
        df = self._catalog.query(
            """
            SELECT asset_id, trade_date, open, high, low, close, volume, amount,
                   adj_factor, adj_close, is_suspended
            FROM silver_prices_1d
            WHERE trade_date >= ? AND trade_date <= ?
            ORDER BY asset_id, trade_date
            """,
            [spec.start_date.isoformat(), spec.end_date.isoformat()],
        )
        if not df.is_empty() and df["trade_date"].dtype == pl.Utf8:
            df = df.with_columns(pl.col("trade_date").str.to_date())
        return df

    def _load_features(self, spec: BacktestRunSpec) -> pl.DataFrame | None:
        if not spec.feature_set_version:
            return None
        df = self._catalog.query(
            """
            SELECT asset_id, trade_date, factor_name, value
            FROM gold_factor_values
            WHERE feature_set_version = ?
              AND trade_date >= ? AND trade_date <= ?
            """,
            [spec.feature_set_version, spec.start_date.isoformat(), spec.end_date.isoformat()],
        )
        if df.is_empty():
            return None

        # Pivot to wide format: asset_id, trade_date, factor1, factor2, ...
        if df["trade_date"].dtype == pl.Utf8:
            df = df.with_columns(pl.col("trade_date").str.to_date())

        wide = df.pivot(
            index=["asset_id", "trade_date"],
            on="factor_name",
            values="value",
        )
        return wide

    def _build_strategy(self, spec: BacktestRunSpec) -> Strategy:
        return StaticTopNStrategy(
            strategy_id=spec.strategy_id,
            top_n=spec.top_n,
            sort_factor=spec.sort_factor,
        )

    def _detect_cost_model(self, prices: pl.DataFrame) -> CostModel:
        """Detect cost model based on asset_id exchange prefix."""
        if prices.is_empty():
            return CostModel.for_cn()
        sample_ids = prices["asset_id"].head(5).to_list()
        for aid in sample_ids:
            if aid and aid.startswith(("NYSE:", "NASDAQ:", "AMEX:")):
                return CostModel.for_us()
            if aid and aid.startswith("HKEX:"):
                return CostModel.for_hk()
        return CostModel.for_cn()

    def _persist_run(self, result, spec: BacktestRunSpec) -> str:
        """Write backtest run metadata to gold_backtest_runs."""
        metrics_dict = {
            "total_return": result.metrics.total_return,
            "annualized_return": result.metrics.annualized_return,
            "annualized_volatility": result.metrics.annualized_volatility,
            "sharpe_ratio": result.metrics.sharpe_ratio,
            "sortino_ratio": result.metrics.sortino_ratio,
            "max_drawdown": result.metrics.max_drawdown,
            "calmar_ratio": result.metrics.calmar_ratio,
            "win_rate": result.metrics.win_rate,
            "profit_factor": result.metrics.profit_factor,
            "var_95": result.metrics.var_95,
            "cvar_95": result.metrics.cvar_95,
            "beta": result.metrics.beta,
            "total_trades": result.metrics.total_trades,
            "trading_days": result.metrics.trading_days,
        }

        # Write metrics to a JSON artifact
        metrics_dir = Path("data/backtest_artifacts")
        metrics_dir.mkdir(parents=True, exist_ok=True)
        metrics_path = metrics_dir / f"{result.run_id}.json"
        metrics_path.write_text(json.dumps(metrics_dict, indent=2))

        conn = self._catalog._get_conn()
        conn.execute(
            """
            INSERT INTO gold_backtest_runs
                (run_id, engine, strategy_id, dataset_version, signal_set_version,
                 cost_model_config, started_at, completed_at, status, metrics_uri, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                result.run_id,
                "vector",
                result.strategy_id,
                spec.dataset_version,
                spec.feature_set_version or None,
                json.dumps({"model": "default"}),
                result.started_at.isoformat(),
                (result.completed_at or datetime.now(tz=timezone.utc)).isoformat(),
                "completed" if result.error is None else "failed",
                str(metrics_path),
                json.dumps(spec.tags),
            ],
        )

        logger.info("Persisted backtest run %s → %s", result.run_id, metrics_path)
        return result.run_id

    def _persist_signals(self, result, run_id: str, spec: BacktestRunSpec) -> None:
        """Write trading signals to gold_signals."""
        positions = result.positions
        if positions.is_empty():
            return

        # positions contains [trade_date, asset_id, target_weight]
        # Convert to signal format
        signals_df = positions.select([
            pl.lit(run_id).alias("signal_set_version"),
            pl.lit(result.strategy_id).alias("strategy_id"),
            pl.col("trade_date"),
            pl.col("asset_id"),
            pl.col("target_weight").alias("signal"),
            pl.lit("long").alias("direction"),
            pl.lit(1.0).alias("confidence"),
            pl.col("target_weight"),
        ])

        conn = self._catalog._get_conn()
        stage = "_signals_stage"
        conn.register(stage, signals_df.to_arrow())
        try:
            conn.execute("""
                INSERT OR REPLACE INTO gold_signals
                    (signal_set_version, strategy_id, trade_date, asset_id,
                     signal, direction, confidence, target_weight)
                SELECT * FROM {stage}
            """.format(stage=stage))
        except Exception as exc:
            logger.warning("Failed to persist signals: %s", exc)
        finally:
            try:
                conn.unregister(stage)
            except Exception:
                pass

    def _persist_fills(self, result, run_id: str) -> None:
        """Write order fills to gold_fills."""
        fills = result.fills
        if fills.is_empty():
            return

        import uuid as _uuid

        # Add fill_id and run_id columns
        fills_df = fills.with_columns([
            pl.lit(run_id).alias("run_id"),
            pl.Series("fill_id", [str(_uuid.uuid4()) for _ in range(len(fills))]),
        ]).select([
            "fill_id", "run_id", "trade_date", "asset_id", "side", "qty",
            "price", "notional", "commission", "stamp_duty", "slippage", "total_cost",
        ])

        conn = self._catalog._get_conn()
        stage = "_fills_stage"
        conn.register(stage, fills_df.to_arrow())
        try:
            conn.execute(f"""
                INSERT OR REPLACE INTO gold_fills
                    (fill_id, run_id, trade_date, asset_id, side, qty,
                     price, notional, commission, stamp_duty, slippage, total_cost)
                SELECT fill_id, run_id, trade_date, asset_id, side, qty,
                       price, notional, commission, stamp_duty, slippage, total_cost
                FROM {stage}
            """)
            logger.info("Persisted %d fills to gold_fills", len(fills_df))
        except Exception as exc:
            logger.warning("Failed to persist fills: %s", exc)
        finally:
            try:
                conn.unregister(stage)
            except Exception:
                pass

    def _persist_portfolio_snapshots(self, result, run_id: str) -> None:
        """Write portfolio snapshots to gold_portfolio_snapshots."""
        if result.portfolio_returns.is_empty():
            return

        import uuid as _uuid

        snapshots = []
        nav = float(result.spec.initial_cash)
        peak_nav = nav

        for row in result.portfolio_returns.iter_rows(named=True):
            ret = row.get("portfolio_return", 0.0) or 0.0
            nav *= (1 + ret)
            peak_nav = max(peak_nav, nav)

            snapshots.append({
                "snapshot_id": f"{run_id}_{row['trade_date']}",
                "run_id": run_id,
                "trade_date": row["trade_date"],
                "cash": nav * 0.1,  # Simplified: 10% cash
                "nav": nav,
                "positions_count": 0,
                "gross_exposure": nav * 0.9,
                "net_exposure": nav * 0.9,
            })

        if not snapshots:
            return

        snap_df = pl.DataFrame(snapshots)
        conn = self._catalog._get_conn()
        stage = "_portfolio_snapshots_stage"
        conn.register(stage, snap_df.to_arrow())
        try:
            conn.execute(f"""
                INSERT OR REPLACE INTO gold_portfolio_snapshots
                    (snapshot_id, run_id, trade_date, cash, nav,
                     positions_count, gross_exposure, net_exposure)
                SELECT snapshot_id, run_id, trade_date, cash, nav,
                       positions_count, gross_exposure, net_exposure
                FROM {stage}
            """)
            logger.info("Persisted %d portfolio snapshots", len(snapshots))
        except Exception as exc:
            logger.warning("Failed to persist portfolio snapshots: %s", exc)
        finally:
            try:
                conn.unregister(stage)
            except Exception:
                pass

    def _persist_positions(self, result, run_id: str) -> None:
        """Write portfolio positions to gold_risk_snapshots as point-in-time snapshots."""
        if result.portfolio_returns.is_empty():
            return

        import numpy as np

        # Create a risk snapshot per trade date from portfolio returns
        snapshots = []
        nav = float(result.spec.initial_cash)
        peak_nav = nav
        all_returns: list[float] = []

        for i, row in enumerate(result.portfolio_returns.iter_rows(named=True)):
            ret = row.get("portfolio_return", 0.0) or 0.0
            all_returns.append(ret)
            nav *= (1 + ret)
            peak_nav = max(peak_nav, nav)
            dd = (nav - peak_nav) / peak_nav if peak_nav > 0 else 0.0

            # Compute VaR/CVaR from returns up to this point
            var_95 = None
            cvar_95 = None
            if len(all_returns) > 1:
                rets = np.array(all_returns)
                sorted_rets = np.sort(rets)
                var_idx = max(0, int(np.floor(0.05 * len(sorted_rets))))
                var_95 = float(sorted_rets[var_idx])
                cvar_95 = float(np.mean(sorted_rets[:var_idx + 1])) if var_idx > 0 else var_95

            snapshots.append({
                "snapshot_id": f"{run_id}_{row['trade_date']}",
                "run_id": run_id,
                "snapshot_ts": f"{row['trade_date']}T15:00:00Z",
                "strategy_id": result.strategy_id,
                "gross_leverage": 1.0,
                "net_leverage": 1.0,
                "beta": None,
                "drawdown": dd,
                "var_95": var_95,
                "cvar_95": cvar_95,
                "sector_exposure": None,
                "factor_exposure": None,
            })

        if not snapshots:
            return

        snap_df = pl.DataFrame(snapshots)
        conn = self._catalog._get_conn()
        stage = "_risk_snapshots_stage"
        conn.register(stage, snap_df.to_arrow())
        try:
            conn.execute(f"""
                INSERT OR REPLACE INTO gold_risk_snapshots
                SELECT * FROM {stage}
            """)
        except Exception as exc:
            logger.warning("Failed to persist risk snapshots: %s", exc)
        finally:
            try:
                conn.unregister(stage)
            except Exception:
                pass

    def _persist_risk_snapshots(self, result, run_id: str) -> None:
        """Persist portfolio_returns as a Parquet artifact for tearsheet."""
        if result.portfolio_returns.is_empty():
            return

        artifact_dir = Path("data/backtest_artifacts")
        artifact_dir.mkdir(parents=True, exist_ok=True)
        nav_path = artifact_dir / f"{run_id}_nav.parquet"
        result.portfolio_returns.write_parquet(nav_path)
        logger.info("Persisted NAV series → %s", nav_path)

    def _persist_pretrade_decisions(self, result, run_id: str) -> None:
        """Write pre-trade risk decisions to gold_pretrade_decisions."""
        if not result.pretrade_decisions:
            return

        # Pre-convert list fields to JSON strings before creating DataFrame
        for d in result.pretrade_decisions:
            d["reasons"] = json.dumps(d.get("reasons", []))
            d["policy_names"] = json.dumps(d.get("policy_names", []))

        decisions_df = pl.DataFrame(result.pretrade_decisions)
        decisions_df = decisions_df.with_columns([
            pl.lit(run_id).alias("run_id"),
            pl.lit("vector").alias("engine"),
        ]).select([
            "decision_id", "run_id", "engine", "trade_date", "strategy_id",
            "asset_id", "requested_qty", "approved_qty", "decision",
            "reasons", "policy_names",
        ])

        conn = self._catalog._get_conn()
        stage = "_pretrade_decisions_stage"
        conn.register(stage, decisions_df.to_arrow())
        try:
            conn.execute(f"""
                INSERT OR REPLACE INTO gold_pretrade_decisions
                    (decision_id, run_id, engine, trade_date, strategy_id,
                     asset_id, requested_qty, approved_qty, decision,
                     reasons, policy_names)
                SELECT decision_id, run_id, engine, trade_date, strategy_id,
                       asset_id, requested_qty, approved_qty, decision,
                       reasons, policy_names
                FROM {stage}
            """)
            logger.info("Persisted %d pretrade decisions", len(decisions_df))
        except Exception as exc:
            logger.warning("Failed to persist pretrade decisions: %s", exc)
        finally:
            try:
                conn.unregister(stage)
            except Exception:
                pass
