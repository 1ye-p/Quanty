"""cquant.bt_analyzer.models — Shared data models for backtest robustness analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


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
    created_at: datetime
