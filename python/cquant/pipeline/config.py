"""cquant.pipeline.config — Pipeline configuration dataclass."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PipelineConfig:
    """Configuration for the automated ML pipeline.

    Controls all five stages: factors -> ML -> backtest -> analysis -> promotion.
    """

    # --- Factor stage ---
    feature_set_version: str = "tdx_bulk_v1"
    factor_names: list[str] = field(default_factory=list)

    # --- ML stage ---
    model_types: list[str] = field(default_factory=lambda: ["lgbm"])
    n_splits: int = 3
    gap_days: int = 5

    # --- Backtest stage ---
    strategy_type: str = "ml_model"
    top_n: int = 10
    initial_cash: float = 1_000_000.0
    rebalance_frequency: str = "weekly"

    # --- Promotion stage ---
    promotion_threshold: float = 0.02
    auto_promote: bool = False

    # --- Scheduling ---
    retrain_day: int = 6  # Sunday (0=Monday)
    retrain_hour: int = 20  # 20:00 CST
