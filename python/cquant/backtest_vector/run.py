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

import numpy as np
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

_schema_ensured_for: set[int] = set()


def _ensure_run_schema_extensions(conn) -> None:
    """Add optional columns to gold_backtest_runs once per connection."""
    conn_id = id(conn)
    if conn_id in _schema_ensured_for:
        return
    for ddl in [
        "ALTER TABLE gold_backtest_runs ADD COLUMN IF NOT EXISTS benchmark_asset_id VARCHAR DEFAULT ''",
        "ALTER TABLE gold_backtest_runs ADD COLUMN IF NOT EXISTS is_walk_forward BOOLEAN DEFAULT FALSE",
        "ALTER TABLE gold_backtest_runs ADD COLUMN IF NOT EXISTS n_folds INTEGER",
        "ALTER TABLE gold_backtest_runs ADD COLUMN IF NOT EXISTS aggregated_metrics_json JSON",
    ]:
        try:
            conn.execute(ddl)
        except Exception as exc:
            logger.debug("_ensure_run_schema_extensions: %s", exc)
    _schema_ensured_for.add(conn_id)


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
    # ML strategy support
    strategy_type: str = "StaticTopN"
    model_version: str = ""
    label_name: str = "ret_5d"
    # Walk-forward / eval config
    eval_mode: str | None = None  # "train" | "valid" | "test" | "all"
    walk_forward: object | None = None  # WalkForwardConfig | None (avoid import cycle)
    # MarketNeutral params
    short_n: int = 10
    # SectorRotation params
    sector_map: dict[str, str] = field(default_factory=dict)
    top_sectors: int = 3
    top_n_per_sector: int = 3
    # Combo params
    sub_strategy_configs: list[dict] = field(default_factory=list)
    combo_method: str = "equal_weight"
    # Universe filtering
    universe_id: str = "all"
    # Cross-sectional scoring integration
    scoring_run_id: str = ""
    # CustomWeightStrategy
    custom_weights: dict = field(default_factory=dict)


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


def _compute_beta(
    portfolio_returns: list[float],
    benchmark_returns: list[float],
    window: int = 60,
) -> float | None:
    """Compute rolling beta from portfolio and benchmark returns."""
    if len(portfolio_returns) < window or len(benchmark_returns) < window:
        return None
    port = np.array(portfolio_returns[-window:])
    bench = np.array(benchmark_returns[-window:])
    cov_matrix = np.cov(port, bench)
    var = cov_matrix[1][1]
    return float(cov_matrix[0][1] / var) if var > 0 else None


def _compute_sector_exposure(
    positions_on_date: pl.DataFrame,
    sector_map: dict[str, str],
) -> dict[str, float]:
    """Compute sector exposure from positions and sector map."""
    if positions_on_date.is_empty() or not sector_map:
        return {}
    exposure: dict[str, float] = {}
    for row in positions_on_date.iter_rows(named=True):
        sector = sector_map.get(row["asset_id"], "Unknown")
        exposure[sector] = exposure.get(sector, 0.0) + abs(row["target_weight"])
    return exposure


def _extract_benchmark_returns(spec: BacktestSpec) -> list[float]:
    """Extract daily benchmark returns from spec prices."""
    if not spec.benchmark_asset_id or spec.prices.is_empty():
        return []
    bench_prices = spec.prices.filter(
        pl.col("asset_id") == spec.benchmark_asset_id
    ).sort("trade_date")
    if len(bench_prices) < 2:
        return []
    closes = bench_prices["close"].to_list()
    return [closes[i] / closes[i - 1] - 1 for i in range(1, len(closes))]


def _detect_drawdown_periods(
    nav_series: list[tuple],
) -> list[dict]:
    """Detect drawdown periods from NAV time series."""
    if len(nav_series) < 2:
        return []

    periods = []
    peak_nav = nav_series[0][1]
    peak_date = nav_series[0][0]
    in_drawdown = False
    trough_nav = peak_nav
    trough_date = peak_date
    dd_start_date = None

    for i, (td, nav) in enumerate(nav_series):
        if i == 0:
            # Initialize with first point
            peak_nav = nav
            peak_date = td
            continue

        if nav >= peak_nav:
            if in_drawdown:
                periods.append({
                    "start_date": dd_start_date,
                    "trough_date": trough_date,
                    "recovery_date": td,
                    "max_drawdown": (trough_nav - peak_nav) / peak_nav,
                    "duration_days": (td - dd_start_date).days,
                    "recovery_days": (td - trough_date).days,
                    "underwater_days": (td - dd_start_date).days,
                })
                in_drawdown = False
            peak_nav = nav
            peak_date = td
        else:
            if not in_drawdown:
                dd_start_date = peak_date
                trough_nav = nav
                trough_date = td
                in_drawdown = True
            elif nav < trough_nav:
                trough_nav = nav
                trough_date = td

    if in_drawdown:
        last_date = nav_series[-1][0]
        periods.append({
            "start_date": dd_start_date,
            "trough_date": trough_date,
            "recovery_date": None,
            "max_drawdown": (trough_nav - peak_nav) / peak_nav,
            "duration_days": (last_date - dd_start_date).days,
            "recovery_days": -1,
            "underwater_days": (last_date - dd_start_date).days,
        })

    return periods


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
        if spec.walk_forward:
            return self._run_walk_forward(spec)
        return self._run_single(spec)

    def _run_single(self, spec: BacktestRunSpec) -> str:
        """Run a single backtest (existing logic extracted)."""
        prices = self._load_prices(spec)
        if prices.is_empty():
            raise ValueError(f"No price data for {spec.start_date} to {spec.end_date}")

        features = self._load_features(spec)

        # When using scoring results, auto-set sort_factor to 'score'
        if spec.scoring_run_id and spec.sort_factor != "score":
            from dataclasses import replace
            spec = replace(spec, sort_factor="score")

        strategy = self._build_strategy(spec)
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
            extra={"catalog": self._catalog},
        )

        result = self._engine.run(bt_spec)
        run_id = self._persist_run(result, spec)
        self._persist_signals(result, run_id, spec)
        self._persist_fills(result, run_id)
        self._persist_positions(result, run_id)
        self._persist_rolling_risk_metrics(result, run_id)
        self._persist_drawdown_periods(result, run_id)
        self._persist_portfolio_snapshots(result, run_id)
        self._persist_risk_snapshots(result, run_id)
        if result.pretrade_decisions:
            self._persist_pretrade_decisions(result, run_id)
        return run_id

    def _run_walk_forward(self, spec: BacktestRunSpec) -> str:
        """Run walk-forward backtest: train on each fold, test on OOS."""
        from dataclasses import replace

        dates = self._get_trade_dates(spec)
        if len(dates) < spec.walk_forward.n_splits + 1:
            raise ValueError(
                f"Not enough dates ({len(dates)}) for {spec.walk_forward.n_splits} splits"
            )

        splits = self._generate_splits_static(dates, spec.walk_forward)

        fold_results = []
        for i, (train_start, train_end, test_start, test_end) in enumerate(splits):
            logger.info(
                "Walk-forward fold %d: train=[%s, %s] test=[%s, %s]",
                i, train_start, train_end, test_start, test_end,
            )

            model_id = self._train_fold_model(spec, train_start, train_end, i)

            fold_spec = replace(
                spec,
                start_date=test_start,
                end_date=test_end,
                model_version=model_id,
                eval_mode="test",
                walk_forward=None,  # prevent recursion
            )

            fold_run_id = self._run_single(fold_spec)
            fold_results.append({
                "fold_id": i,
                "train_start": train_start.isoformat(),
                "train_end": train_end.isoformat(),
                "test_start": test_start.isoformat(),
                "test_end": test_end.isoformat(),
                "run_id": fold_run_id,
            })

        aggregated = self._aggregate_fold_metrics(fold_results)
        run_id = self._persist_walk_forward_result(spec, fold_results, aggregated)
        return run_id

    def _get_trade_dates(self, spec: BacktestRunSpec) -> list[date]:
        """Get sorted unique trade dates for the spec's date range."""
        df = self._catalog.query(
            "SELECT DISTINCT trade_date FROM silver_prices_1d "
            "WHERE trade_date >= ? AND trade_date <= ? ORDER BY trade_date",
            [spec.start_date.isoformat(), spec.end_date.isoformat()],
        )
        if df.is_empty():
            return []
        return [d if isinstance(d, date) else date.fromisoformat(str(d))
                for d in df["trade_date"].to_list()]

    @staticmethod
    def _generate_splits_static(
        dates: list[date],
        wf,  # WalkForwardConfig
        min_train_size: int = 2,
    ) -> list[tuple[date, date, date, date]]:
        """Generate (train_start, train_end, test_start, test_end) tuples."""
        n = len(dates)
        n_splits = wf.n_splits
        gap_days = wf.gap_days

        if wf.window_type == "expanding":
            test_size = max(1, (n - min_train_size) // n_splits)
            splits = []
            for i in range(n_splits):
                test_end_idx = n - (n_splits - i) * test_size
                test_start_idx = max(test_end_idx - test_size, min_train_size)
                train_end_idx = test_start_idx - 1

                if gap_days > 0 and train_end_idx > 0:
                    train_end = dates[train_end_idx]
                    gap_target = date.fromordinal(train_end.toordinal() + gap_days)
                    for j in range(test_start_idx, n):
                        if dates[j] >= gap_target:
                            test_start_idx = j
                            break

                if test_start_idx >= n or train_end_idx < 0:
                    continue

                splits.append((
                    dates[0],
                    dates[train_end_idx],
                    dates[test_start_idx],
                    dates[min(test_start_idx + test_size, n - 1)],
                ))
            return splits
        else:
            train_size = max(min_train_size, n // (n_splits + 1))
            test_size = max(1, (n - train_size) // n_splits)
            splits = []
            for i in range(n_splits):
                train_start_idx = i * test_size
                train_end_idx = train_start_idx + train_size - 1
                test_start_idx = train_end_idx + 1

                if gap_days > 0:
                    train_end = dates[train_end_idx]
                    gap_target = date.fromordinal(train_end.toordinal() + gap_days)
                    for j in range(test_start_idx, n):
                        if dates[j] >= gap_target:
                            test_start_idx = j
                            break

                if test_start_idx >= n:
                    continue

                splits.append((
                    dates[train_start_idx],
                    dates[train_end_idx],
                    dates[test_start_idx],
                    dates[min(test_start_idx + test_size, n - 1)],
                ))
            return splits

    def _train_fold_model(
        self, spec: BacktestRunSpec, train_start: date, train_end: date, fold_id: int
    ) -> str:
        """Train a model for a walk-forward fold."""
        from cquant.ml_lab.pipeline import run_ml_prediction_pipeline

        features = self._load_features_for_range(spec, train_start, train_end)
        if features.is_empty():
            raise ValueError(f"No features for training period {train_start} to {train_end}")

        model_id = run_ml_prediction_pipeline(
            catalog=self._catalog,
            features=features,
            target_col=spec.label_name,
            model_id_prefix=f"{spec.strategy_id}_fold{fold_id}",
            n_splits=1,
            gap_days=0,
        )
        return model_id

    def _load_features_for_range(
        self, spec: BacktestRunSpec, start: date, end: date
    ) -> pl.DataFrame:
        """Load factor values for a specific date range."""
        if not spec.feature_set_version:
            return pl.DataFrame()
        df = self._catalog.query(
            "SELECT asset_id, trade_date, factor_name, value "
            "FROM gold_factor_values "
            "WHERE feature_set_version = ? AND trade_date >= ? AND trade_date <= ?",
            [spec.feature_set_version, start.isoformat(), end.isoformat()],
        )
        if df.is_empty():
            return pl.DataFrame()
        if df["trade_date"].dtype == pl.Utf8:
            df = df.with_columns(pl.col("trade_date").str.to_date())
        return df.pivot(
            index=["asset_id", "trade_date"],
            on="factor_name",
            values="value",
        )

    def _aggregate_fold_metrics(self, fold_results: list[dict]) -> dict:
        """Aggregate metrics across walk-forward folds."""
        all_metrics = []
        for fold in fold_results:
            metrics = self.get_run_metrics(fold["run_id"])
            if metrics:
                all_metrics.append(metrics)

        if not all_metrics:
            return {}

        keys = ["sharpe_ratio", "total_return", "max_drawdown", "win_rate", "calmar_ratio"]
        aggregated = {}
        for k in keys:
            vals = [m.get(k, 0) for m in all_metrics if m.get(k) is not None]
            if vals:
                aggregated[f"avg_{k}"] = sum(vals) / len(vals)
                aggregated[f"min_{k}"] = min(vals)
                aggregated[f"max_{k}"] = max(vals)
        aggregated["n_folds"] = len(all_metrics)
        return aggregated

    def _persist_walk_forward_result(
        self, spec: BacktestRunSpec, fold_results: list[dict], aggregated: dict
    ) -> str:
        """Persist walk-forward result to gold_backtest_runs + gold_wf_folds."""
        run_id = str(uuid.uuid4())
        now = datetime.now(tz=timezone.utc).isoformat()

        conn = self._catalog._get_conn()
        _ensure_run_schema_extensions(conn)

        conn.execute(
            "INSERT INTO gold_backtest_runs "
            "(run_id, engine, strategy_id, dataset_version, started_at, completed_at, status, "
            " is_walk_forward, n_folds, aggregated_metrics_json) "
            "VALUES (?, ?, ?, ?, ?, ?, 'completed', ?, ?, ?)",
            [
                run_id, "walk_forward", spec.strategy_id, spec.dataset_version,
                now, now, True, len(fold_results), json.dumps(aggregated),
            ],
        )

        conn.execute("""
            CREATE TABLE IF NOT EXISTS gold_wf_folds (
                run_id VARCHAR, fold_id INTEGER,
                train_start VARCHAR, train_end VARCHAR,
                test_start VARCHAR, test_end VARCHAR,
                fold_run_id VARCHAR, PRIMARY KEY (run_id, fold_id)
            )
        """)
        for fold in fold_results:
            conn.execute(
                "INSERT OR REPLACE INTO gold_wf_folds "
                "(run_id, fold_id, train_start, train_end, test_start, test_end, fold_run_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                [run_id, fold["fold_id"], fold["train_start"], fold["train_end"],
                 fold["test_start"], fold["test_end"], fold["run_id"]],
            )

        return run_id

    def run_engine(
        self,
        strategy,
        start_date,
        end_date,
        initial_cash=None,
        dataset_version: str = "custom",
        benchmark_asset_id: str = "",
        risk_policies=None,
        tags=None,
    ) -> str:
        """使用自定义策略运行回测并持久化结果。

        与 ``run()`` 不同，此方法接受任意 ``Strategy`` 对象，
        绕过内置的 ``StaticTopNStrategy`` 限制。

        Parameters
        ----------
        strategy:
            任意实现了 ``Strategy`` ABC 的策略实例。
        start_date, end_date:
            回测日期范围（``date`` 类型）。
        initial_cash:
            初始资金 ``Decimal``，默认从 backtest.toml 加载（100 万）。
        dataset_version:
            写入 ``gold_backtest_runs.dataset_version`` 的标识。
        benchmark_asset_id:
            基准资产 ID，用于计算 IR/TE/Alpha。
        risk_policies:
            可选的风控 Policy 列表。
        tags:
            额外标签 dict。

        Returns
        -------
        回测运行 ID（``run_id``）。
        """
        from decimal import Decimal
        from cquant.backtest_vector.engine import BacktestSpec
        from cquant.core.toml_config import get_backtest_defaults

        if initial_cash is None:
            defaults = get_backtest_defaults()
            initial_cash = Decimal(str(defaults.get("initial_cash", 1_000_000)))

        self._catalog.initialize()

        # 构建最小化 BacktestRunSpec 用于持久化（不实际用于策略构建）
        persist_spec = BacktestRunSpec(
            dataset_version=dataset_version,
            strategy_id=strategy.strategy_id,
            start_date=start_date,
            end_date=end_date,
            initial_cash=initial_cash,
            tags=tags or {},
        )

        prices = self._load_prices(persist_spec)
        if prices.is_empty():
            raise ValueError(f"No price data for {start_date} to {end_date}")

        cost_model = self._detect_cost_model(prices)

        bt_spec = BacktestSpec(
            strategy=strategy,
            prices=prices,
            start_date=start_date,
            end_date=end_date,
            initial_cash=initial_cash,
            cost_model=cost_model,
            risk_policies=risk_policies or [],
            benchmark_asset_id=benchmark_asset_id,
            tags=tags or {},
        )

        result = self._engine.run(bt_spec)
        run_id = self._persist_run(result, persist_spec)
        self._persist_signals(result, run_id, persist_spec)
        self._persist_fills(result, run_id)
        self._persist_positions(result, run_id)
        self._persist_rolling_risk_metrics(result, run_id)
        self._persist_drawdown_periods(result, run_id)
        self._persist_portfolio_snapshots(result, run_id)
        self._persist_risk_snapshots(result, run_id)
        if result.pretrade_decisions:
            self._persist_pretrade_decisions(result, run_id)

        logger.info("run_engine 完成: run_id=%s strategy=%s", run_id, strategy.strategy_id)
        return run_id

    def get_run_metrics(self, run_id: str) -> dict | None:
        """从 DuckDB 和 JSON 文件加载指定回测运行的完整指标字典。

        Parameters
        ----------
        run_id:
            回测运行 ID（来自 ``gold_backtest_runs.run_id``）。

        Returns
        -------
        包含所有持久化指标的字典，如果 run_id 不存在则返回 ``None``。
        """
        result = self._catalog.query(
            "SELECT metrics_uri FROM gold_backtest_runs WHERE run_id = ?",
            [run_id],
        )
        if result.is_empty():
            return None

        metrics_uri = result["metrics_uri"][0]
        if not metrics_uri:
            return None

        metrics_path = Path(metrics_uri)
        if not metrics_path.exists():
            logger.warning("指标文件不存在：%s", metrics_path)
            return None

        return json.loads(metrics_path.read_text(encoding="utf-8"))

    def list_runs(
        self,
        limit: int = 20,
        strategy_id: str | None = None,
    ) -> "pl.DataFrame":
        """查询最近的回测运行历史。

        Parameters
        ----------
        limit:
            返回最多 N 条记录，按开始时间降序排列。
        strategy_id:
            按策略 ID 过滤，None 则返回所有策略的运行记录。

        Returns
        -------
        包含 run_id、strategy_id、status、started_at 等字段的 DataFrame。
        """
        if strategy_id is not None:
            return self._catalog.query(
                """
                SELECT run_id, engine, strategy_id, dataset_version,
                       status, started_at, completed_at, tags
                FROM gold_backtest_runs
                WHERE strategy_id = ?
                ORDER BY started_at DESC
                LIMIT ?
                """,
                [strategy_id, limit],
            )
        return self._catalog.query(
            """
            SELECT run_id, engine, strategy_id, dataset_version,
                   status, started_at, completed_at, tags
            FROM gold_backtest_runs
            ORDER BY started_at DESC
            LIMIT ?
            """,
            [limit],
        )

    def compute_kelly_win_rates(
        self,
        run_id: str,
        min_trades: int = 5,
    ) -> dict[str, float]:
        """从指定回测运行的成交记录计算 Kelly 历史胜率。

        结果可直接传入 ``KellySizer`` 的 ``ctx.extra["win_rates"]`` 字段。

        Parameters
        ----------
        run_id:
            已完成回测运行的 ID。
        min_trades:
            计入结果的最小配对成交笔数。

        Returns
        -------
        ``dict[asset_id, win_rate]``，空字典表示无成交记录或数据不足。
        """
        from cquant.ml_lab.win_rate_utils import compute_win_rates_from_fills

        fills = self._catalog.query(
            "SELECT asset_id, side, qty, price, trade_date, total_cost "
            "FROM gold_fills WHERE run_id = ?",
            [run_id],
        )
        if fills.is_empty():
            return {}
        return compute_win_rates_from_fills(fills, min_trades=min_trades)

    def _load_prices(self, spec: BacktestRunSpec) -> pl.DataFrame:
        from cquant.backtest_vector.universe import resolve_universe

        universe_id = getattr(spec, 'universe_id', None) or "all"
        asset_ids = resolve_universe(self._catalog, universe_id)

        query = (
            "SELECT asset_id, trade_date, open, high, low, close, volume, amount, "
            "adj_factor, adj_close, is_suspended "
            "FROM silver_prices_1d "
            "WHERE trade_date >= ? AND trade_date <= ?"
        )
        params: list = [spec.start_date.isoformat(), spec.end_date.isoformat()]

        if asset_ids is not None:
            if not asset_ids:
                return pl.DataFrame()
            placeholders = ",".join(["?" for _ in asset_ids])
            query += f" AND asset_id IN ({placeholders})"
            params.extend(asset_ids)

        query += " ORDER BY asset_id, trade_date"
        df = self._catalog.query(query, params)
        if not df.is_empty() and df["trade_date"].dtype == pl.Utf8:
            df = df.with_columns(pl.col("trade_date").str.to_date())
        return df

    def _load_features(self, spec: BacktestRunSpec) -> pl.DataFrame | None:
        # If scoring_run_id is set, load from cross-sectional scores
        if spec.scoring_run_id:
            df = self._catalog.query(
                "SELECT asset_id, trade_date, score FROM gold_cross_section_scores "
                "WHERE run_id = ? AND trade_date >= ? AND trade_date <= ?",
                [spec.scoring_run_id, spec.start_date.isoformat(), spec.end_date.isoformat()],
            )
            if df.is_empty():
                return None
            if df["trade_date"].dtype == pl.Utf8:
                df = df.with_columns(pl.col("trade_date").str.to_date())
            return df

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
        if spec.strategy_type == "MLModelStrategy":
            if not spec.model_version:
                raise ValueError(
                    "model_version is required for MLModelStrategy. "
                    "Please train a model in ML Lab first."
                )
            from cquant.backtest_vector.strategies.ml_strategy import MLModelStrategy
            return MLModelStrategy(
                strategy_id=spec.strategy_id,
                model_version=spec.model_version,
                top_n=spec.top_n,
                label_name=spec.label_name,
            )
        if spec.strategy_type == "MultiFactor":
            from cquant.backtest_vector.strategies.multi_factor import MultiFactorStrategy
            return MultiFactorStrategy(
                strategy_id=spec.strategy_id,
                factor_weights={spec.sort_factor: 1.0},
                top_n=spec.top_n,
            )
        if spec.strategy_type == "MarketNeutral":
            from cquant.backtest_vector.strategies.market_neutral import MarketNeutralStrategy
            return MarketNeutralStrategy(
                strategy_id=spec.strategy_id,
                factor_col=spec.sort_factor,
                top_n=spec.top_n,
                short_n=spec.short_n,
            )
        if spec.strategy_type == "SectorRotation":
            from cquant.backtest_vector.strategies.sector_rotation import SectorRotationStrategy
            return SectorRotationStrategy(
                strategy_id=spec.strategy_id,
                factor_col=spec.sort_factor,
                sector_map=spec.sector_map or None,
                top_sectors=spec.top_sectors,
                top_n_per_sector=spec.top_n_per_sector,
            )
        if spec.strategy_type == "Combo":
            from cquant.backtest_vector.strategies.combo import CompositeStrategy
            sub_strategies = [
                self._build_strategy_from_config(cfg, idx)
                for idx, cfg in enumerate(spec.sub_strategy_configs)
            ]
            return CompositeStrategy(
                strategy_id=spec.strategy_id,
                strategies=sub_strategies,
                method=spec.combo_method,
            )
        if spec.strategy_type == "CustomWeightStrategy":
            from cquant.backtest_vector.strategies.custom_weight_strategy import CustomWeightStrategy
            return CustomWeightStrategy(
                strategy_id=spec.strategy_id,
                weights=spec.custom_weights or {},
            )
        return StaticTopNStrategy(
            strategy_id=spec.strategy_id,
            top_n=spec.top_n,
            sort_factor=spec.sort_factor,
        )

    def _build_strategy_from_config(self, cfg: dict, idx: int) -> Strategy:
        """Build a sub-strategy from a config dict (used by Combo)."""
        stype = cfg.get("strategy_type", "StaticTopN")
        sid = f"{cfg.get('strategy_id', 'sub')}_{idx}"
        sub_spec = BacktestRunSpec(
            dataset_version="",
            strategy_id=sid,
            start_date=date.today(),
            end_date=date.today(),
            strategy_type=stype,
            top_n=cfg.get("top_n", 10),
            sort_factor=cfg.get("sort_factor", "ret_20d"),
            model_version=cfg.get("model_version", ""),
            label_name=cfg.get("label_name", "ret_5d"),
            short_n=cfg.get("short_n", 10),
            sector_map=cfg.get("sector_map", {}),
            top_sectors=cfg.get("top_sectors", 3),
            top_n_per_sector=cfg.get("top_n_per_sector", 3),
        )
        return self._build_strategy(sub_spec)

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

    @staticmethod
    def _compute_turnover(result) -> float | None:
        """安全计算换手率，无 positions 数据时返回 None。"""
        try:
            from cquant.backtest_vector.metrics import compute_portfolio_turnover
            if result.positions.is_empty():
                return None
            return compute_portfolio_turnover(result.positions)
        except Exception as exc:
            logger.debug("Turnover computation failed: %s", exc)
            return None

    @staticmethod
    def _compute_hhi(result) -> float | None:
        """安全计算 HHI，无 positions 数据时返回 None。"""
        try:
            from cquant.backtest_vector.metrics import compute_hhi
            if result.positions.is_empty():
                return None
            return compute_hhi(result.positions)
        except Exception as exc:
            logger.debug("HHI computation failed: %s", exc)
            return None

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
            "information_ratio": result.metrics.information_ratio,
            "tracking_error": result.metrics.tracking_error,
            "alpha": result.metrics.alpha,
            "turnover_pct": self._compute_turnover(result),
            "hhi": self._compute_hhi(result),
        }

        # Write metrics to a JSON artifact
        metrics_dir = Path("data/backtest_artifacts")
        metrics_dir.mkdir(parents=True, exist_ok=True)
        metrics_path = metrics_dir / f"{result.run_id}.json"
        metrics_path.write_text(json.dumps(metrics_dict, indent=2))

        conn = self._catalog._get_conn()
        _ensure_run_schema_extensions(conn)
        conn.execute(
            """
            INSERT INTO gold_backtest_runs
                (run_id, engine, strategy_id, dataset_version, signal_set_version,
                 cost_model_config, started_at, completed_at, status, metrics_uri, tags,
                 benchmark_asset_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                spec.benchmark_asset_id or "",
            ],
        )

        logger.info("Persisted backtest run %s → %s", result.run_id, metrics_path)
        return result.run_id

    def _persist_signals(self, result, run_id: str, spec: BacktestRunSpec) -> None:
        """Write trading signals to gold_signals."""
        positions = result.positions
        if positions.is_empty():
            return

        conn = self._catalog._get_conn()
        rows = []
        for row in positions.iter_rows(named=True):
            rows.append((
                run_id,
                result.strategy_id,
                str(row["trade_date"]),
                row["asset_id"],
                float(row.get("target_weight", 0) or 0),
                "long",
                1.0,
                float(row.get("target_weight", 0) or 0),
            ))
        assert not rows or len(rows[0]) == 8, (
            f"Column mismatch: {len(rows[0])} values vs 8 placeholders"
        )
        try:
            conn.executemany("""
                INSERT OR REPLACE INTO gold_signals
                    (signal_set_version, strategy_id, trade_date, asset_id,
                     signal, direction, confidence, target_weight)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, rows)
            logger.info("Persisted %d signals to gold_signals", len(rows))
        except Exception as exc:
            logger.warning("Failed to persist signals: %s", exc)

    def _persist_fills(self, result, run_id: str) -> None:
        """Write order fills to gold_fills."""
        fills = result.fills
        if fills.is_empty():
            return

        import uuid as _uuid

        conn = self._catalog._get_conn()
        rows = []
        for row in fills.iter_rows(named=True):
            rows.append((
                str(_uuid.uuid4()),
                run_id,
                str(row["trade_date"]),
                row["asset_id"],
                row["side"],
                int(row["qty"]),
                float(row["price"]),
                float(row["notional"]),
                float(row.get("commission", 0) or 0),
                float(row.get("stamp_duty", 0) or 0),
                float(row.get("slippage", 0) or 0),
                float(row.get("total_cost", 0) or 0),
            ))
        assert not rows or len(rows[0]) == 12, (
            f"Column mismatch: {len(rows[0])} values vs 12 placeholders"
        )
        try:
            conn.executemany("""
                INSERT OR REPLACE INTO gold_fills
                    (fill_id, run_id, trade_date, asset_id, side, qty,
                     price, notional, commission, stamp_duty, slippage, total_cost)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, rows)
            logger.info("Persisted %d fills to gold_fills", len(rows))
        except Exception as exc:
            logger.warning("Failed to persist fills: %s", exc)

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

            # Compute actual positions data for this date
            day_positions = pl.DataFrame()
            if not result.positions.is_empty() and "trade_date" in result.positions.columns:
                day_positions = result.positions.filter(
                    pl.col("trade_date") == row["trade_date"]
                )

            if not day_positions.is_empty() and "target_weight" in day_positions.columns:
                weights = day_positions["target_weight"].to_list()
                gross_exp = sum(abs(w) for w in weights if w is not None) * nav
                net_exp = sum(w for w in weights if w is not None) * nav
                pos_count = sum(1 for w in weights if w is not None and abs(w) > 0.001)
            else:
                gross_exp = 0.0
                net_exp = 0.0
                pos_count = 0

            snapshots.append({
                "snapshot_id": f"{run_id}_{row['trade_date']}",
                "run_id": run_id,
                "trade_date": row["trade_date"],
                "cash": max(0.0, nav - gross_exp),
                "nav": nav,
                "positions_count": pos_count,
                "gross_exposure": gross_exp,
                "net_exposure": net_exp,
            })

        if not snapshots:
            return

        conn = self._catalog._get_conn()
        rows = []
        for s in snapshots:
            rows.append((
                s["snapshot_id"], s["run_id"], str(s["trade_date"]),
                s["cash"], s["nav"], s["positions_count"],
                s["gross_exposure"], s["net_exposure"],
            ))
        assert not rows or len(rows[0]) == 8, (
            f"Column mismatch: {len(rows[0])} values vs 8 placeholders"
        )
        try:
            conn.executemany("""
                INSERT OR REPLACE INTO gold_portfolio_snapshots
                    (snapshot_id, run_id, trade_date, cash, nav,
                     positions_count, gross_exposure, net_exposure)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, rows)
            logger.info("Persisted %d portfolio snapshots", len(rows))
        except Exception as exc:
            logger.warning("Failed to persist portfolio snapshots: %s", exc)

    def _persist_positions(self, result, run_id: str) -> None:
        """Write portfolio positions to gold_risk_snapshots as point-in-time snapshots."""
        if result.portfolio_returns.is_empty():
            return

        # Get benchmark returns for beta calculation
        benchmark_returns = _extract_benchmark_returns(result.spec)

        # Get sector map
        sector_map = result.spec.extra.get("sector_map", {}) if hasattr(result.spec, 'extra') and result.spec.extra else {}

        # Build per-date positions lookup — O(P) via partition_by
        positions_by_date: dict = {}
        if not result.positions.is_empty():
            positions_by_date = result.positions.partition_by("trade_date", as_dict=True)

        snapshots = []
        nav = float(result.spec.initial_cash)
        peak_nav = nav
        all_returns: list[float] = []
        bench_returns_so_far: list[float] = []

        for i, row in enumerate(result.portfolio_returns.iter_rows(named=True)):
            ret = row.get("portfolio_return", 0.0) or 0.0
            all_returns.append(ret)
            if i < len(benchmark_returns):
                bench_returns_so_far.append(benchmark_returns[i])

            nav *= (1 + ret)
            peak_nav = max(peak_nav, nav)
            dd = (nav - peak_nav) / peak_nav if peak_nav > 0 else 0.0

            # VaR/CVaR
            var_95 = None
            cvar_95 = None
            if len(all_returns) > 1:
                rets = np.array(all_returns)
                sorted_rets = np.sort(rets)
                var_idx = max(0, int(np.floor(0.05 * len(sorted_rets))))
                var_95 = float(sorted_rets[var_idx])
                cvar_95 = float(np.mean(sorted_rets[:var_idx + 1])) if var_idx > 0 else var_95

            td = row["trade_date"]

            # Real leverage from positions
            gross_lev = 1.0
            net_lev = 1.0
            if td in positions_by_date:
                pos = positions_by_date[td]
                weights = pos["target_weight"].to_list()
                gross_lev = sum(abs(w) for w in weights)
                net_lev = sum(weights)

            # Real beta
            beta = _compute_beta(all_returns, bench_returns_so_far, window=60)

            # Real sector exposure
            sec_exp = None
            if td in positions_by_date and sector_map:
                exp = _compute_sector_exposure(positions_by_date[td], sector_map)
                sec_exp = exp if exp else None

            snapshots.append({
                "snapshot_id": f"{run_id}_{td}",
                "run_id": run_id,
                "snapshot_ts": f"{td}T15:00:00Z",
                "strategy_id": result.strategy_id,
                "gross_leverage": gross_lev,
                "net_leverage": net_lev,
                "beta": beta,
                "drawdown": dd,
                "var_95": var_95,
                "cvar_95": cvar_95,
                "sector_exposure": sec_exp,
                "factor_exposure": None,
            })

        if not snapshots:
            return

        conn = self._catalog._get_conn()
        rows = []
        for s in snapshots:
            rows.append((
                s["snapshot_id"], s["run_id"], s["snapshot_ts"],
                s["strategy_id"], s["gross_leverage"], s["net_leverage"],
                s["beta"], s["drawdown"], s["var_95"], s["cvar_95"],
                s["sector_exposure"], s["factor_exposure"],
            ))
        assert not rows or len(rows[0]) == 12, (
            f"Column mismatch: {len(rows[0])} values vs 12 placeholders"
        )
        try:
            conn.executemany("""
                INSERT OR REPLACE INTO gold_risk_snapshots
                    (snapshot_id, run_id, snapshot_ts, strategy_id,
                     gross_leverage, net_leverage, beta, drawdown,
                     var_95, cvar_95, sector_exposure, factor_exposure)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, rows)
            logger.info("Persisted %d risk snapshots", len(rows))
        except Exception as exc:
            logger.warning("Failed to persist risk snapshots: %s", exc)

    def _persist_rolling_risk_metrics(self, result, run_id: str) -> None:
        """Compute and persist rolling risk metrics for multiple windows."""
        if result.portfolio_returns.is_empty():
            return

        windows = [20, 60, 252]
        returns = result.portfolio_returns.sort("trade_date")

        # Get benchmark returns
        benchmark_returns = _extract_benchmark_returns(result.spec)

        ret_list = returns["portfolio_return"].to_list()
        date_list = returns["trade_date"].to_list()
        rows = []

        for w in windows:
            for i in range(len(ret_list)):
                if i < w - 1:
                    continue

                window_returns = ret_list[i - w + 1: i + 1]
                rets = np.array(window_returns)

                rolling_var = float(np.percentile(rets, 5))
                var_mask = rets <= rolling_var
                rolling_cvar = float(np.mean(rets[var_mask])) if var_mask.any() else rolling_var
                rolling_vol = float(np.std(rets) * np.sqrt(252))
                mean_ret = float(np.mean(rets))
                std_ret = float(np.std(rets))
                rolling_sharpe = (mean_ret / std_ret * np.sqrt(252)) if std_ret > 0 else 0.0

                rolling_beta = None
                if len(benchmark_returns) > i:
                    bench_window = benchmark_returns[i - w + 1: i + 1]
                    if len(bench_window) == w:
                        cov_matrix = np.cov(rets, np.array(bench_window))
                        var_bench = cov_matrix[1][1]
                        if var_bench > 0:
                            rolling_beta = float(cov_matrix[0][1] / var_bench)

                rows.append((
                    run_id, date_list[i], w,
                    rolling_var, rolling_cvar, rolling_vol,
                    rolling_sharpe, rolling_beta,
                ))

        if not rows:
            return

        conn = self._catalog._get_conn()
        try:
            conn.executemany(
                """
                INSERT OR REPLACE INTO gold_risk_rolling
                    (run_id, trade_date, window, rolling_var, rolling_cvar,
                     rolling_vol, rolling_sharpe, rolling_beta)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            logger.info("Persisted %d rolling risk metric rows", len(rows))
        except Exception as exc:
            logger.warning("Failed to persist rolling risk metrics: %s", exc)

    def _persist_drawdown_periods(self, result, run_id: str) -> None:
        """Detect and persist drawdown periods."""
        if result.portfolio_returns.is_empty():
            return

        returns = result.portfolio_returns.sort("trade_date")
        nav_series = list(zip(
            returns["trade_date"].to_list(),
            returns["nav"].to_list(),
        ))

        periods = _detect_drawdown_periods(nav_series)
        if not periods:
            return

        conn = self._catalog._get_conn()
        rows = []
        for i, p in enumerate(periods):
            rows.append((
                run_id, i,
                p["start_date"].isoformat() if p["start_date"] else None,
                p["trough_date"].isoformat() if p["trough_date"] else None,
                p["recovery_date"].isoformat() if p["recovery_date"] else None,
                p["max_drawdown"],
                p["duration_days"],
                p["recovery_days"],
                p["underwater_days"],
            ))

        try:
            conn.executemany(
                """
                INSERT OR REPLACE INTO gold_drawdown_periods
                    (run_id, period_id, start_date, trough_date, recovery_date,
                     max_drawdown, duration_days, recovery_days, underwater_days)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            logger.info("Persisted %d drawdown periods", len(rows))
        except Exception as exc:
            logger.warning("Failed to persist drawdown periods: %s", exc)

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

        conn = self._catalog._get_conn()
        rows = []
        for d in result.pretrade_decisions:
            rows.append((
                d.get("decision_id", str(uuid.uuid4())),
                run_id,
                "vector",
                str(d["trade_date"]),
                d["strategy_id"],
                d["asset_id"],
                d.get("requested_qty"),
                d.get("approved_qty"),
                d["decision"],
                json.dumps(d.get("reasons", [])),
                json.dumps(d.get("policy_names", [])),
            ))
        assert not rows or len(rows[0]) == 11, (
            f"Column mismatch: {len(rows[0])} values vs 11 placeholders"
        )
        try:
            conn.executemany("""
                INSERT OR REPLACE INTO gold_pretrade_decisions
                    (decision_id, run_id, engine, trade_date, strategy_id,
                     asset_id, requested_qty, approved_qty, decision,
                     reasons, policy_names)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, rows)
            logger.info("Persisted %d pretrade decisions", len(rows))
        except Exception as exc:
            logger.warning("Failed to persist pretrade decisions: %s", exc)
