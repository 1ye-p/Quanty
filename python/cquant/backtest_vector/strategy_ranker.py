"""cquant.backtest_vector.strategy_ranker — Multi-dimensional strategy ranking framework.

Provides StrategyRanker for comprehensive strategy comparison across multiple
performance dimensions with configurable weights.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import polars as pl

logger = logging.getLogger(__name__)


@dataclass
class StrategyMetrics:
    """Metrics for a single strategy run."""

    strategy_id: str
    run_id: str
    sharpe_ratio: float
    max_drawdown: float
    sortino_ratio: float
    calmar_ratio: float
    turnover: float
    oos_ratio: float  # Out-of-sample performance ratio
    cost_sensitivity: float  # Performance degradation with higher costs
    total_return: float = 0.0
    annualized_return: float = 0.0
    win_rate: float = 0.0
    total_trades: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "strategy_id": self.strategy_id,
            "run_id": self.run_id,
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown": self.max_drawdown,
            "sortino_ratio": self.sortino_ratio,
            "calmar_ratio": self.calmar_ratio,
            "turnover": self.turnover,
            "oos_ratio": self.oos_ratio,
            "cost_sensitivity": self.cost_sensitivity,
            "total_return": self.total_return,
            "annualized_return": self.annualized_return,
            "win_rate": self.win_rate,
        }


@dataclass
class RankingWeights:
    """Weights for each ranking dimension.

    Weights should sum to 1.0 for normalized ranking.
    Higher weight means more importance in the final score.
    """

    sharpe_ratio: float = 0.25
    max_drawdown: float = 0.20
    sortino_ratio: float = 0.15
    calmar_ratio: float = 0.10
    turnover: float = 0.10
    oos_ratio: float = 0.15
    cost_sensitivity: float = 0.05

    def __post_init__(self) -> None:
        """Validate and normalize weights."""
        total = (
            self.sharpe_ratio
            + self.max_drawdown
            + self.sortino_ratio
            + self.calmar_ratio
            + self.turnover
            + self.oos_ratio
            + self.cost_sensitivity
        )
        if abs(total) < 1e-10:
            logger.warning("All weights are zero, using equal weights")
            self.sharpe_ratio = self.max_drawdown = self.sortino_ratio = 1 / 7
            self.calmar_ratio = self.turnover = self.oos_ratio = self.cost_sensitivity = 1 / 7
        elif abs(total - 1.0) > 0.01:
            logger.warning("Weights sum to %.3f, normalizing to 1.0", total)
            self.sharpe_ratio /= total
            self.max_drawdown /= total
            self.sortino_ratio /= total
            self.calmar_ratio /= total
            self.turnover /= total
            self.oos_ratio /= total
            self.cost_sensitivity /= total

    def to_dict(self) -> dict[str, float]:
        """Convert to dictionary."""
        return {
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown": self.max_drawdown,
            "sortino_ratio": self.sortino_ratio,
            "calmar_ratio": self.calmar_ratio,
            "turnover": self.turnover,
            "oos_ratio": self.oos_ratio,
            "cost_sensitivity": self.cost_sensitivity,
        }


@dataclass
class RankingResult:
    """Result of strategy ranking."""

    # Ranked strategies (best to worst)
    ranked_strategies: list[dict[str, Any]]
    # Individual dimension scores (0-1) for each strategy
    dimension_scores: dict[str, dict[str, float]]
    # Final composite scores
    composite_scores: dict[str, float]
    # Weights used
    weights: dict[str, float]
    # DataFrame with all rankings
    rankings_df: pl.DataFrame

    def top_n(self, n: int = 5) -> list[dict[str, Any]]:
        """Get top N strategies."""
        return self.ranked_strategies[:n]

    def summary(self) -> dict:
        """Return ranking summary."""
        return {
            "total_strategies": len(self.ranked_strategies),
            "top_strategy": self.ranked_strategies[0] if self.ranked_strategies else None,
            "weights": self.weights,
        }


class StrategyRanker:
    """Multi-dimensional strategy ranking framework.

    Ranks strategies across 7 dimensions:
    1. sharpe_ratio: Risk-adjusted return
    2. max_drawdown: Worst peak-to-trough decline (inverted, lower is better)
    3. sortino_ratio: Downside risk-adjusted return
    4. calmar_ratio: Return vs max drawdown
    5. turnover: Trading frequency (lower is better for most strategies)
    6. oos_ratio: Out-of-sample performance consistency
    7. cost_sensitivity: Robustness to transaction costs

    Usage::

        ranker = StrategyRanker(weights=RankingWeights(sharpe_ratio=0.3))

        strategies = [
            StrategyMetrics(strategy_id="A", run_id="1", ...),
            StrategyMetrics(strategy_id="B", run_id="2", ...),
        ]

        result = ranker.rank(strategies)
        print(result.top_n(3))
    """

    def __init__(
        self,
        weights: RankingWeights | None = None,
        percentile_method: str = "min_max",
    ) -> None:
        """Initialize strategy ranker.

        Args:
            weights: Ranking weights (uses defaults if None).
            percentile_method: Method for normalizing scores ("min_max" or "z_score").
        """
        self._weights = weights or RankingWeights()
        self._percentile_method = percentile_method

    def _normalize_scores_min_max(self, values: list[float], invert: bool = False) -> list[float]:
        """Normalize scores to 0-1 range using min-max scaling.

        Args:
            values: Raw metric values.
            invert: If True, lower values get higher scores.

        Returns:
            Normalized scores between 0 and 1.
        """
        if not values:
            return []

        min_val = min(values)
        max_val = max(values)
        range_val = max_val - min_val

        if range_val < 1e-10:
            return [0.5] * len(values)

        if invert:
            return [(max_val - v) / range_val for v in values]
        else:
            return [(v - min_val) / range_val for v in values]

    def _normalize_scores_z_score(self, values: list[float], invert: bool = False) -> list[float]:
        """Normalize scores using z-score normalization.

        Args:
            values: Raw metric values.
            invert: If True, lower values get higher scores.

        Returns:
            Normalized scores (not bounded to 0-1, but centered around 0.5).
        """
        if not values:
            return []

        mean_val = np.mean(values)
        std_val = np.std(values)

        if std_val < 1e-10:
            return [0.5] * len(values)

        z_scores = [(v - mean_val) / std_val for v in values]

        # Convert z-scores to 0-1 range using sigmoid-like transformation
        if invert:
            return [1.0 / (1.0 + np.exp(z)) for z in z_scores]
        else:
            return [1.0 / (1.0 + np.exp(-z)) for z in z_scores]

    def _normalize_scores(self, values: list[float], invert: bool = False) -> list[float]:
        """Normalize scores using configured method.

        Args:
            values: Raw metric values.
            invert: If True, lower values get higher scores.

        Returns:
            Normalized scores between 0 and 1.
        """
        if self._percentile_method == "z_score":
            return self._normalize_scores_z_score(values, invert)
        return self._normalize_scores_min_max(values, invert)

    def _compute_dimension_scores(
        self,
        strategies: list[StrategyMetrics],
    ) -> dict[str, dict[str, float]]:
        """Compute normalized scores for each dimension.

        Args:
            strategies: List of strategy metrics.

        Returns:
            Nested dict: dimension -> strategy_id -> normalized_score.
        """
        n = len(strategies)
        strategy_ids = [s.strategy_id for s in strategies]

        # Extract raw values for each dimension
        # max_drawdown is always <= 0; use abs() so inversion works correctly
        dimensions = {
            "sharpe_ratio": [s.sharpe_ratio for s in strategies],
            "max_drawdown": [abs(s.max_drawdown) for s in strategies],
            "sortino_ratio": [s.sortino_ratio for s in strategies],
            "calmar_ratio": [s.calmar_ratio for s in strategies],
            "turnover": [s.turnover for s in strategies],
            "oos_ratio": [s.oos_ratio for s in strategies],
            "cost_sensitivity": [s.cost_sensitivity for s in strategies],
        }

        # Dimensions where lower is better
        invert_dims = {"max_drawdown", "turnover", "cost_sensitivity"}

        # Normalize each dimension
        dimension_scores = {}
        for dim, values in dimensions.items():
            invert = dim in invert_dims
            normalized = self._normalize_scores(values, invert=invert)
            dimension_scores[dim] = dict(zip(strategy_ids, normalized))

        return dimension_scores

    def _compute_composite_scores(
        self,
        dimension_scores: dict[str, dict[str, float]],
        strategy_ids: list[str],
    ) -> dict[str, float]:
        """Compute weighted composite scores.

        Args:
            dimension_scores: Normalized dimension scores.
            strategy_ids: List of strategy IDs.

        Returns:
            Dict mapping strategy_id to composite score.
        """
        weights = self._weights.to_dict()
        composite_scores = {}

        for sid in strategy_ids:
            score = 0.0
            for dim, weight in weights.items():
                dim_score = dimension_scores.get(dim, {}).get(sid, 0.0)
                score += weight * dim_score
            composite_scores[sid] = score

        return composite_scores

    def rank(self, strategies: list[StrategyMetrics]) -> RankingResult:
        """Rank strategies across all dimensions.

        Args:
            strategies: List of strategy metrics to rank.

        Returns:
            RankingResult with ranked strategies and detailed scores.
        """
        if not strategies:
            return RankingResult(
                ranked_strategies=[],
                dimension_scores={},
                composite_scores={},
                weights=self._weights.to_dict(),
                rankings_df=pl.DataFrame(),
            )

        # Compute dimension scores
        dimension_scores = self._compute_dimension_scores(strategies)

        # Compute composite scores
        strategy_ids = [s.strategy_id for s in strategies]
        composite_scores = self._compute_composite_scores(dimension_scores, strategy_ids)

        # Sort by composite score (descending)
        sorted_strategies = sorted(
            strategies,
            key=lambda s: composite_scores.get(s.strategy_id, 0.0),
            reverse=True,
        )

        # Build ranked list
        ranked_list = []
        for rank, s in enumerate(sorted_strategies, 1):
            ranked_list.append({
                "rank": rank,
                "strategy_id": s.strategy_id,
                "run_id": s.run_id,
                "composite_score": composite_scores.get(s.strategy_id, 0.0),
                "dimension_scores": {
                    dim: dimension_scores.get(dim, {}).get(s.strategy_id, 0.0)
                    for dim in dimension_scores
                },
                "raw_metrics": s.to_dict(),
            })

        # Build DataFrame
        rows = []
        for s in strategies:
            row = {
                "strategy_id": s.strategy_id,
                "run_id": s.run_id,
                "composite_score": composite_scores.get(s.strategy_id, 0.0),
            }
            for dim in dimension_scores:
                row[f"{dim}_score"] = dimension_scores.get(dim, {}).get(s.strategy_id, 0.0)
            rows.append(row)

        rankings_df = pl.DataFrame(rows).sort("composite_score", descending=True)

        logger.info(
            "Ranked %d strategies, top: %s (score=%.4f)",
            len(strategies),
            ranked_list[0]["strategy_id"] if ranked_list else "N/A",
            ranked_list[0]["composite_score"] if ranked_list else 0.0,
        )

        return RankingResult(
            ranked_strategies=ranked_list,
            dimension_scores=dimension_scores,
            composite_scores=composite_scores,
            weights=self._weights.to_dict(),
            rankings_df=rankings_df,
        )

    @staticmethod
    def from_backtest_results(
        results: list[tuple[str, dict[str, float]]],
        weights: RankingWeights | None = None,
    ) -> RankingResult:
        """Create ranking from backtest result dictionaries.

        Args:
            results: List of (run_id, metrics_dict) tuples.
            weights: Optional ranking weights.

        Returns:
            RankingResult.
        """
        strategies = []
        for run_id, metrics in results:
            strategy_id = metrics.get("strategy_id", run_id)
            strategies.append(StrategyMetrics(
                strategy_id=strategy_id,
                run_id=run_id,
                sharpe_ratio=metrics.get("sharpe_ratio", 0.0),
                max_drawdown=metrics.get("max_drawdown", 0.0),
                sortino_ratio=metrics.get("sortino_ratio", 0.0),
                calmar_ratio=metrics.get("calmar_ratio", 0.0),
                turnover=metrics.get("turnover", 0.0),
                oos_ratio=metrics.get("oos_ratio", 1.0),
                cost_sensitivity=metrics.get("cost_sensitivity", 0.0),
                total_return=metrics.get("total_return", 0.0),
                annualized_return=metrics.get("annualized_return", 0.0),
                win_rate=metrics.get("win_rate", 0.0),
            ))

        ranker = StrategyRanker(weights=weights)
        return ranker.rank(strategies)
