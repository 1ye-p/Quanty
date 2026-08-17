"""StrategyOptimizationJob — health-gated ML re-optimization loop orchestration.

Pipeline:
  1. Health check (reuse ``StrategyHealthChecker``) — healthy strategies skip.
  2. Derive a parameter grid from the strategy config (capped at ``max_grid``).
  3. Evaluate each candidate via walk-forward (reuse ``WalkForwardRefit``)
     and score by an OOS composite score (sharpe - 0.5 * maxdd).
  4. Re-train the ML component (PurgedKFold) when the config has ``ml_config``.
  5. Overfit review: PSR/DSR of the candidate must not be worse than baseline
     beyond tolerance (reuse ``SharpeMetrics``).
  6. Emit an ``OptimizationReport`` with status="needs_review".

SAFETY: this job NEVER applies new parameters automatically. Reports are
persisted to ``gold_optimization_reports`` for human review in the UI.
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

import polars as pl

from cquant.bt_analyzer.sharpe import SharpeMetrics
from cquant.bt_analyzer.walk_forward_refit import WalkForwardRefit
from cquant.ml_lab.purged_kfold import PurgedKFold
from cquant.scheduler.strategy_health import (
    HealthResult,
    StrategyHealthChecker,
)

logger = logging.getLogger(__name__)

STATUS_NEEDS_REVIEW = "needs_review"
STATUS_SKIPPED_HEALTHY = "skipped_healthy"
STATUS_SKIPPED_NO_GAIN = "skipped_no_gain"
STATUS_FAILED = "failed"

# Tunable params (from config) → candidate values explored by the grid.
_DEFAULT_GRID_SPEC: dict[str, list[Any]] = {
    "top_n": [5, 10, 15, 20],
    "rebalance_freq": ["weekly", "biweekly", "monthly"],
    "lookback_days": [20, 40, 60],
    "n_factors": [3, 5, 8],
}

_REPORTS_DDL = """
CREATE TABLE IF NOT EXISTS gold_optimization_reports (
    strategy_id VARCHAR,
    generated_at TIMESTAMPTZ,
    status VARCHAR,
    reason VARCHAR,
    health_json JSON,
    best_params_json JSON,
    baseline_metrics_json JSON,
    candidate_metrics_json JSON,
    overfit_check_json JSON
)
"""


def _composite_score(metrics: dict[str, float]) -> float:
    """OOS composite score: sharpe - 0.5 * max_drawdown (drawdown is positive)."""
    sharpe = metrics.get(
        "oos_sharpe_ratio_mean",
        metrics.get("oos_sharpe_mean", metrics.get("sharpe_ratio", 0.0)),
    )
    if sharpe is None or not math.isfinite(sharpe):
        sharpe = 0.0
    maxdd = metrics.get("oos_max_drawdown_mean", metrics.get("max_drawdown", 0.0))
    if maxdd is None or not math.isfinite(maxdd):
        maxdd = 0.0
    return float(sharpe - 0.5 * abs(maxdd))


@dataclass
class OptimizationReport:
    """Outcome of one optimization run for a strategy."""

    strategy_id: str
    status: str  # needs_review / skipped_healthy / skipped_no_gain / failed
    health: HealthResult | None = None
    best_params: dict | None = None
    baseline_metrics: dict | None = None  # baseline wf aggregates
    candidate_metrics: dict | None = None  # best candidate wf aggregates
    overfit_check: dict | None = None  # PSR/DSR comparison
    generated_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    reason: str | None = None
    ml_retrain: dict | None = None

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe serialization for persistence."""

        def _json(v: Any) -> Any:
            if v is None:
                return None
            if isinstance(v, HealthResult):
                return {
                    "status": v.status,
                    "reason": v.reason,
                    "baseline_sharpe": v.baseline_sharpe,
                    "recent_sharpe": v.recent_sharpe,
                    "baseline_ic": v.baseline_ic,
                    "recent_ic": v.recent_ic,
                }
            return v

        return {
            "strategy_id": self.strategy_id,
            "status": self.status,
            "reason": self.reason,
            "health": _json(self.health),
            "best_params": self.best_params,
            "baseline_metrics": self.baseline_metrics,
            "candidate_metrics": self.candidate_metrics,
            "overfit_check": self.overfit_check,
            "ml_retrain": self.ml_retrain,
            "generated_at": self.generated_at.isoformat(),
        }


class StrategyOptimizationJob:
    """Health-gated auto re-optimization orchestrator (report-only).

    Produces ``OptimizationReport``s with status="needs_review"; never mutates
    strategy configs. Application of recommended params requires human
    confirmation via the UI.
    """

    def __init__(
        self,
        catalog,
        max_grid: int = 50,
        health_checker: StrategyHealthChecker | None = None,
        wf_evaluator=None,  # callable(strategy_id, params, data) -> metrics dict
        ml_trainer=None,  # callable(config) -> retrain info dict
    ) -> None:
        self._catalog = catalog
        self._max_grid = max_grid
        self._health_checker = health_checker or StrategyHealthChecker(catalog)
        # Injection points for tests; default to instance methods.
        self._wf_evaluator = wf_evaluator or self._evaluate_candidate
        self._ml_trainer = ml_trainer or self._retrain_ml_if_needed

    # ------------------------------------------------------------------ run

    def run(self, strategy_id: str, config: dict, data: Any = None) -> OptimizationReport:
        """Execute the full optimization pipeline for one strategy.

        ``config`` is the strategy's parsed_config dict (may include
        ``baseline_run_id`` and ``ml_config``). ``data`` is opaque context
        passed through to the walk-forward evaluator.
        """
        logger.info("OptimizationJob start: strategy=%s", strategy_id)
        try:
            return self._run_inner(strategy_id, config, data)
        except Exception as exc:  # never crash the scheduler
            logger.exception("OptimizationJob failed for %s", strategy_id)
            return OptimizationReport(
                strategy_id=strategy_id,
                status=STATUS_FAILED,
                reason=str(exc),
            )

    def _run_inner(
        self, strategy_id: str, config: dict, data: Any
    ) -> OptimizationReport:
        # 1) Health gate.
        health = self._health_checker.check(strategy_id)
        if health.status == "healthy":
            logger.info("Strategy %s healthy — skipping optimization", strategy_id)
            return self._finalize(
                OptimizationReport(
                    strategy_id=strategy_id,
                    status=STATUS_SKIPPED_HEALTHY,
                    health=health,
                )
            )
        if health.status == "insufficient_data":
            logger.info("Strategy %s insufficient data — skipping", strategy_id)
            return self._finalize(
                OptimizationReport(
                    strategy_id=strategy_id,
                    status=STATUS_SKIPPED_NO_GAIN,
                    health=health,
                    reason="insufficient_data",
                )
            )

        # 2) Param grid.
        grid = self._derive_param_grid(config)
        self._last_grid_size = grid
        if not grid:
            return self._finalize(
                OptimizationReport(
                    strategy_id=strategy_id,
                    status=STATUS_SKIPPED_NO_GAIN,
                    health=health,
                    reason="empty_param_grid",
                )
            )
        logger.info("Strategy %s: evaluating %d candidate param sets", strategy_id, len(grid))

        # Baseline metrics: reuse health aggregates as the wf baseline summary.
        baseline_metrics: dict[str, float] = {
            k: v
            for k, v in {
                "oos_sharpe_mean": health.baseline_sharpe,
                "oos_ic_mean": health.baseline_ic,
                "recent_sharpe_mean": health.recent_sharpe,
                "recent_ic_mean": health.recent_ic,
            }.items()
            if v is not None
        }

        # 3+4) Evaluate candidates via walk-forward, pick by composite score.
        best_params: dict | None = None
        best_metrics: dict | None = None
        best_score = -float("inf")
        for params in grid:
            metrics = self._wf_evaluator(strategy_id, params, data)
            if not metrics:
                continue
            score = _composite_score(metrics)
            if score > best_score:
                best_score = score
                best_params = params
                best_metrics = metrics

        if best_params is None or best_metrics is None:
            return self._finalize(
                OptimizationReport(
                    strategy_id=strategy_id,
                    status=STATUS_SKIPPED_NO_GAIN,
                    health=health,
                    baseline_metrics=baseline_metrics or None,
                    reason="all_candidates_failed",
                )
            )

        baseline_score = _composite_score(baseline_metrics) if baseline_metrics else -float("inf")
        if best_score <= baseline_score:
            logger.info(
                "Strategy %s: best candidate score %.4f <= baseline %.4f — no gain",
                strategy_id, best_score, baseline_score,
            )
            return self._finalize(
                OptimizationReport(
                    strategy_id=strategy_id,
                    status=STATUS_SKIPPED_NO_GAIN,
                    health=health,
                    best_params=best_params,
                    baseline_metrics=baseline_metrics or None,
                    candidate_metrics=best_metrics,
                    reason="no_improvement",
                )
            )

        # 5) ML retrain (only for ML strategies).
        ml_retrain = self._ml_trainer(config) if self._is_ml_strategy(config) else None

        # 6) Overfit review.
        overfit = self._overfit_review(baseline_metrics, best_metrics)

        # 7) Report — needs_review, never auto-applied.
        return self._finalize(
            OptimizationReport(
                strategy_id=strategy_id,
                status=STATUS_NEEDS_REVIEW,
                health=health,
                best_params=best_params,
                baseline_metrics=baseline_metrics or None,
                candidate_metrics=best_metrics,
                overfit_check=overfit,
                ml_retrain=ml_retrain,
            )
        )

    # ----------------------------------------------------------- param grid

    def _derive_param_grid(self, config: dict) -> list[dict]:
        """Derive candidate parameter sets from the strategy config.

        Uses ``grid_spec`` from the config when present; otherwise explores
        default tunables (top_n / rebalance_freq / lookback_days / n_factors)
        restricted to keys already present in the config. Total combinations
        are capped at ``max_grid``.
        """
        grid_spec = config.get("grid_spec") if isinstance(config, dict) else None
        if not grid_spec:
            grid_spec = {
                key: values
                for key, values in _DEFAULT_GRID_SPEC.items()
                if key in config
            }
        if not grid_spec:
            return []

        # Cartesian product, capped at max_grid.
        combos: list[dict] = [{}]
        for key, values in grid_spec.items():
            combos = [dict(c, **{key: v}) for c in combos for v in values]
            if len(combos) > self._max_grid:
                combos = combos[: self._max_grid]
                break
        return combos[: self._max_grid]

    # ------------------------------------------------------------- wf eval

    def _evaluate_candidate(self, strategy_id: str, params: dict, data: Any) -> dict:
        """Run walk-forward for a candidate parameter set (WalkForwardRefit).

        ``data`` must carry ``spec`` (a BacktestSpec) and optional
        ``n_folds`` / ``train_ratio``. Returns aggregated OOS metrics.
        """
        if not isinstance(data, dict) or "spec" not in data:
            raise ValueError(
                "candidate evaluation requires data={'spec': BacktestSpec, ...}"
            )
        spec = data["spec"]
        # Apply params via extra dict copy (same mechanism as GridSearchSensitivity).
        from cquant.backtest_vector.engine import BacktestSpec  # local import: avoid cycle

        extra = {**getattr(spec, "extra", {}), **params}
        merged = BacktestSpec(
            strategy=spec.strategy,
            prices=spec.prices,
            start_date=spec.start_date,
            end_date=spec.end_date,
            initial_cash=spec.initial_cash,
            cost_model=spec.cost_model,
            sizer=spec.sizer,
            risk_policies=spec.risk_policies,
            rebalance_frequency=params.get(
                "rebalance_freq", spec.rebalance_frequency
            ),
            benchmark_asset_id=spec.benchmark_asset_id,
            universe_id=spec.universe_id,
            features=spec.features,
            tags=spec.tags,
            optimizer=spec.optimizer,
            extra=extra,
        )
        refit = WalkForwardRefit(
            base_spec=merged,
            n_folds=int(data.get("n_folds", 5)),
            train_ratio=float(data.get("train_ratio", 0.7)),
            gap_days=int(data.get("gap_days", 0)),
        )
        result = refit.run()
        if result.successful_folds == 0:
            return {}
        return dict(result.aggregated_metrics)

    # ------------------------------------------------------------- ML retrain

    @staticmethod
    def _is_ml_strategy(config: dict) -> bool:
        return isinstance(config, dict) and bool(config.get("ml_config"))

    def _retrain_ml_if_needed(self, config: dict) -> dict | None:
        """Re-train an ML strategy with PurgedKFold CV; returns retrain info.

        Expects ``ml_config`` with ``dataset`` (pl.DataFrame), ``model_builder``
        (callable(train_df) -> fitted model with ``predict``), and optional
        ``n_splits`` / ``purge_window`` / ``embargo_days``. Returns None for
        non-ML strategies or when the dataset is missing (logged, non-fatal).
        """
        ml_config = config.get("ml_config") or {}
        dataset = ml_config.get("dataset")
        model_builder = ml_config.get("model_builder")
        if dataset is None or model_builder is None:
            logger.info("ML retrain skipped: no dataset/model_builder in ml_config")
            return None
        if not isinstance(dataset, pl.DataFrame):
            logger.warning("ML retrain skipped: dataset is not a DataFrame")
            return None

        cv = PurgedKFold(
            n_splits=int(ml_config.get("n_splits", 5)),
            purge_window=int(ml_config.get("purge_window", 0)),
            embargo_days=int(ml_config.get("embargo_days", 0)),
            date_column=ml_config.get("date_column", "trade_date"),
        )
        folds = cv.split(dataset)
        scores: list[float] = []
        for i, (train_df, valid_df) in enumerate(folds):
            try:
                model = model_builder(train_df)
                preds = model.predict(valid_df)
                target_col = ml_config.get("target_col", "target")
                if target_col in valid_df.columns:
                    actual = valid_df[target_col].to_list()
                    preds = list(preds)[: len(actual)]
                    n = len(preds)
                    if n:
                        rmse = (
                            sum((a - p) ** 2 for a, p in zip(actual, preds)) / n
                        ) ** 0.5
                        scores.append(rmse)
            except Exception as exc:
                logger.warning("ML retrain fold %d failed: %s", i, exc)

        result = {
            "n_folds": len(folds),
            "scored_folds": len(scores),
            "mean_rmse": sum(scores) / len(scores) if scores else None,
        }
        logger.info("ML retrain complete: %s", result)
        return result

    # --------------------------------------------------------- overfit check

    def _overfit_review(self, baseline: dict | None, candidate: dict) -> dict:
        """PSR/DSR review: candidate must not be worse than baseline (tolerance).

        Accepts metrics dicts either with fold-level return series
        (``returns`` key) or aggregated sharpe values; in the aggregated case
        a proxy PSR is computed from the sharpe difference.
        """
        tolerance = 0.05  # allowed PSR/DSR degradation

        def _psr_dsr(metrics: dict | None) -> tuple[float, float]:
            if not metrics:
                return 0.0, 0.0
            returns = metrics.get("returns")
            if returns is not None and len(returns) > 1:
                series = pl.Series("r", list(returns))
                psr = SharpeMetrics.probabilistic_sharpe_ratio(series)
                dsr = SharpeMetrics.deflated_sharpe_ratio(
                    series,
                    n_trials=max(len(self._last_grid_size or []), 1),
                )
                return psr, dsr
            # Proxy: map mean OOS sharpe through a logistic-like score.
            sharpe = metrics.get(
                "oos_sharpe_ratio_mean", metrics.get("oos_sharpe_mean", 0.0)
            ) or 0.0
            proxy = 1.0 / (1.0 + math.exp(-float(sharpe)))
            return proxy, proxy

        base_psr, base_dsr = _psr_dsr(baseline)
        cand_psr, cand_dsr = _psr_dsr(candidate)
        passed = (cand_psr >= base_psr - tolerance) and (
            cand_dsr >= base_dsr - tolerance
        )
        return {
            "baseline_psr": base_psr,
            "candidate_psr": cand_psr,
            "baseline_dsr": base_dsr,
            "candidate_dsr": cand_dsr,
            "tolerance": tolerance,
            "passed": passed,
        }

    # ---------------------------------------------------------- persistence

    def _finalize(self, report: OptimizationReport) -> OptimizationReport:
        try:
            self._persist(report)
        except Exception as exc:
            logger.warning("Failed to persist optimization report: %s", exc)
        logger.info(
            "OptimizationJob done: strategy=%s status=%s",
            report.strategy_id, report.status,
        )
        return report

    def _persist(self, report: OptimizationReport) -> None:
        self._catalog.execute(_REPORTS_DDL)
        d = report.to_dict()
        self._catalog.execute(
            "INSERT INTO gold_optimization_reports VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                d["strategy_id"],
                d["generated_at"],
                d["status"],
                d["reason"],
                json.dumps(d["health"]) if d["health"] is not None else None,
                json.dumps(d["best_params"]) if d["best_params"] is not None else None,
                json.dumps(d["baseline_metrics"]) if d["baseline_metrics"] is not None else None,
                json.dumps(d["candidate_metrics"]) if d["candidate_metrics"] is not None else None,
                json.dumps(d["overfit_check"]) if d["overfit_check"] is not None else None,
            ],
        )

    _last_grid_size: list | None = None  # populated in run() for DSR n_trials
