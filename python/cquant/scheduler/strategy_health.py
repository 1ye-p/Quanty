"""Strategy health checking — OOS decay detection over gold_wf_folds.

Compares recent walk-forward OOS performance against a configured baseline
run to decide whether a strategy needs re-optimization. The baseline run is
stored as ``baseline_run_id`` in the strategy's ``parsed_config`` JSON;
when absent, the earliest walk-forward run for the strategy is used.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from cquant.datahub.catalog import Catalog

STATUS_HEALTHY = "healthy"
STATUS_NEEDS_REOPT = "needs_reoptimization"
STATUS_INSUFFICIENT = "insufficient_data"

REASON_SHARPE_DECAY = "sharpe_decay"
REASON_IC_LOSS = "ic_loss"


def _load_parsed_config(catalog: Catalog, strategy_id: str) -> dict | None:
    df = catalog.query(
        "SELECT parsed_config FROM meta_strategy_configs WHERE strategy_id = ?",
        [strategy_id],
    )
    if df.is_empty():
        return None
    raw = df["parsed_config"][0]
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(str(raw))
    except (TypeError, ValueError):
        return {}


def get_baseline_run_id(catalog: Catalog, strategy_id: str) -> str | None:
    """Resolve the baseline walk-forward run for a strategy.

    Order of precedence:
    1. ``baseline_run_id`` in the strategy's parsed_config (if non-empty).
    2. The earliest completed walk-forward run in gold_backtest_runs.
    3. None when the strategy has no walk-forward history.
    """
    parsed = _load_parsed_config(catalog, strategy_id)
    if parsed is None:
        return None
    configured = parsed.get("baseline_run_id")
    if configured:
        return str(configured)

    df = catalog.query(
        "SELECT run_id FROM gold_backtest_runs "
        "WHERE strategy_id = ? AND is_walk_forward = TRUE AND status = 'completed' "
        "ORDER BY completed_at ASC, started_at ASC LIMIT 1",
        [strategy_id],
    )
    if df.is_empty():
        return None
    return str(df["run_id"][0])


def set_baseline_run_id(catalog: Catalog, strategy_id: str, run_id: str) -> None:
    """Store ``baseline_run_id`` in the strategy's parsed_config (merged)."""
    parsed = _load_parsed_config(catalog, strategy_id)
    if parsed is None:
        raise ValueError(f"Strategy '{strategy_id}' not found in meta_strategy_configs")
    parsed["baseline_run_id"] = run_id
    now = datetime.now(tz=timezone.utc).isoformat()
    catalog.execute(
        "UPDATE meta_strategy_configs SET parsed_config = ?, updated_at = ? "
        "WHERE strategy_id = ?",
        [json.dumps(parsed), now, strategy_id],
    )


def _agg_folds(catalog: Catalog, where_sql: str, params: list) -> tuple[float | None, float | None]:
    """Return (mean oos_sharpe, mean oos_ic) over folds matching the filter."""
    df = catalog.query(
        "SELECT AVG(oos_sharpe) AS avg_sharpe, AVG(oos_ic) AS avg_ic "
        f"FROM gold_wf_folds WHERE {where_sql}",
        params,
    )
    if df.is_empty():
        return None, None
    return df["avg_sharpe"][0], df["avg_ic"][0]


@dataclass
class HealthResult:
    """Outcome of a single strategy health check."""

    strategy_id: str
    status: str  # healthy / needs_reoptimization / insufficient_data
    reason: str | None
    baseline_sharpe: float | None
    recent_sharpe: float | None
    baseline_ic: float | None
    recent_ic: float | None


class StrategyHealthChecker:
    """Detect OOS performance decay vs a baseline walk-forward run.

    A strategy triggers re-optimization when either:
    - Sharpe decay: ``(baseline - recent) / baseline > decay_threshold``, or
    - IC loss: baseline IC above ``ic_floor`` while recent IC falls below it.
    """

    def __init__(
        self,
        catalog: Catalog,
        recent_window_days: int = 90,
        decay_threshold: float = 0.4,
        ic_floor: float = 0.02,
    ) -> None:
        self._catalog = catalog
        self._recent_window_days = recent_window_days
        self._decay_threshold = decay_threshold
        self._ic_floor = ic_floor

    def check(self, strategy_id: str) -> HealthResult:
        baseline_run_id = get_baseline_run_id(self._catalog, strategy_id)

        baseline_sharpe = baseline_ic = None
        if baseline_run_id:
            baseline_sharpe, baseline_ic = _agg_folds(
                self._catalog, "run_id = ?", [baseline_run_id]
            )

        cutoff = (datetime.now(tz=timezone.utc) - timedelta(days=self._recent_window_days)).isoformat()
        recent_sharpe, recent_ic = _agg_folds(
            self._catalog,
            "run_id IN (SELECT run_id FROM gold_backtest_runs "
            "WHERE strategy_id = ? AND is_walk_forward = TRUE "
            "AND completed_at >= ?)",
            [strategy_id, cutoff],
        )

        # Insufficient data: no baseline folds or no recent folds → skip.
        if (
            baseline_run_id is None
            or baseline_sharpe is None
            or recent_sharpe is None
        ):
            return HealthResult(
                strategy_id=strategy_id,
                status=STATUS_INSUFFICIENT,
                reason=None,
                baseline_sharpe=baseline_sharpe,
                recent_sharpe=recent_sharpe,
                baseline_ic=baseline_ic,
                recent_ic=recent_ic,
            )

        # Rule 1: sharpe decay (only meaningful for a positive baseline).
        if baseline_sharpe > 0:
            decay = (baseline_sharpe - recent_sharpe) / baseline_sharpe
            if decay > self._decay_threshold:
                return HealthResult(
                    strategy_id=strategy_id,
                    status=STATUS_NEEDS_REOPT,
                    reason=REASON_SHARPE_DECAY,
                    baseline_sharpe=baseline_sharpe,
                    recent_sharpe=recent_sharpe,
                    baseline_ic=baseline_ic,
                    recent_ic=recent_ic,
                )

        # Rule 2: IC loss — significant positive baseline collapses to ~zero.
        if (
            baseline_ic is not None
            and recent_ic is not None
            and baseline_ic > self._ic_floor
            and recent_ic < self._ic_floor
        ):
            return HealthResult(
                strategy_id=strategy_id,
                status=STATUS_NEEDS_REOPT,
                reason=REASON_IC_LOSS,
                baseline_sharpe=baseline_sharpe,
                recent_sharpe=recent_sharpe,
                baseline_ic=baseline_ic,
                recent_ic=recent_ic,
            )

        return HealthResult(
            strategy_id=strategy_id,
            status=STATUS_HEALTHY,
            reason=None,
            baseline_sharpe=baseline_sharpe,
            recent_sharpe=recent_sharpe,
            baseline_ic=baseline_ic,
            recent_ic=recent_ic,
        )
