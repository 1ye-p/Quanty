"""cquant.bt_analyzer.models — Shared data models for backtest robustness analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from cquant.backtest_vector.tca import TCADetail, TCASummary
    from cquant.bt_analyzer.attribution import BrinsonResult


@dataclass
class AnalysisSpec:
    """Configuration for a bt_analyzer run."""

    # Walk-forward out-of-sample validation
    n_oos_windows: int = 5
    oos_fraction: float = 0.2
    gap_days: int = 5

    # CPCV (Combinatorial Purged Cross-Validation)
    n_splits: int = 6
    n_test_splits: int = 2

    # Sharpe significance
    benchmark_sharpe: float = 0.0    # H0: true SR > this value
    n_trials: int = 1                # Number of backtest trials for DSR correction

    # Multiple testing
    alpha: float = 0.05

    # Parameter sensitivity grid (key → list of values tested)
    param_grid: dict[str, list[Any]] = field(default_factory=dict)

    trading_days_per_year: int = 252


@dataclass
class ValidationWindow:
    """Metrics for a single train/test split in OOS or CPCV analysis."""

    window_id: int
    train_start: date
    train_end: date
    test_start: date
    test_end: date
    metrics: dict[str, float]   # keys: sharpe, total_return, max_drawdown, annualized_return, etc.


@dataclass
class OverfitScore:
    """Composite overfit risk score."""

    score: float                          # [0, 1]; higher = more overfit evidence
    confidence: str                       # 'low' | 'medium' | 'high'
    contributing_factors: list[str]       # Human-readable explanations


@dataclass
class AnalysisReport:
    """Full output of AnalysisEngine.run()."""

    analysis_run_id: str
    backtest_run_id: str
    spec: AnalysisSpec
    overall_overfit_score: OverfitScore
    dsr: float                                         # Deflated Sharpe Ratio (probability)
    psr: float                                         # Probabilistic Sharpe Ratio (probability)
    walk_forward_windows: list[ValidationWindow]
    cpcv_windows: list[ValidationWindow] | None
    multiple_testing_result: dict[str, Any]
    stability_metrics: dict[str, float]
    summary: str                                       # Human-readable, consumable by ai_advisor
    brinson_attribution: "BrinsonResult | None" = None
    # TCA fields
    tca_summary: "TCASummary | None" = None
    tca_by_asset: "list[TCADetail] | None" = None
    tca_by_date: "list[TCADetail] | None" = None
    # Enhanced attribution fields
    brinson_daily: list[dict[str, Any]] | None = None
    benchmark_return: float | None = None
    active_return: float | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
