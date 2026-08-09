"""cquant.qlib_bridge.tuner — Hyperparameter tuning engine.

Supports grid search, random search, and (optionally) Bayesian optimization
for qlib models.  Integrates with the model registry from ``models.py``.

Usage::

    from cquant.qlib_bridge.tuner import HyperparameterTuner

    tuner = HyperparameterTuner(
        model_name="lgbm",
        param_grid={"learning_rate": [0.01, 0.05, 0.1], "max_depth": [4, 6, 8]},
        method="grid",
        metric="rmse",
        n_trials=20,
    )
    result = tuner.run(train_data, valid_data)
    print(result.best_params, result.best_score)
"""

from __future__ import annotations

import itertools
import logging
import random
from dataclasses import dataclass, field
from typing import Any, Callable

from cquant.qlib_bridge.models import QLIB_MODELS, create_model

logger = logging.getLogger(__name__)


@dataclass
class TuningResult:
    """Result of a hyperparameter tuning run."""

    best_params: dict[str, Any]
    best_score: float
    all_trials: list[dict[str, Any]] = field(default_factory=list)
    method: str = "grid"
    n_trials: int = 0
    metric: str = "rmse"

    def summary(self) -> str:
        direction = "minimize" if self.metric in ("rmse", "mae") else "maximize"
        return (
            f"TuningResult(method={self.method}, metric={self.metric}, "
            f"direction={direction}, n_trials={len(self.all_trials)}, "
            f"best_score={self.best_score:.6f})"
        )


def _evaluate_model(
    model_name: str,
    params: dict[str, Any],
    train_fn: Callable[[Any], dict[str, float]],
    metric: str,
) -> float:
    """Create a model, train it via ``train_fn``, and return the metric value."""
    model = create_model(model_name, params)
    metrics = train_fn(model)
    return metrics.get(metric, float("inf"))


def _generate_grid(param_grid: dict[str, list[Any]]) -> list[dict[str, Any]]:
    """Generate all combinations from a param grid."""
    keys = list(param_grid.keys())
    values = list(param_grid.values())
    return [dict(zip(keys, combo)) for combo in itertools.product(*values)]


def _generate_random(
    param_ranges: dict[str, list[Any]],
    n_trials: int,
    seed: int | None = None,
) -> list[dict[str, Any]]:
    """Sample random param combinations from ranges.

    Uses a LOCAL :class:`random.Random` instance seeded with *seed* so that
    sampling does not touch the global :mod:`random` state.  Same seed → same
    sampled trials, which keeps tuning reproducible and concurrent runs
    isolated from one another.
    """
    rng = random.Random(seed)
    trials = []
    for _ in range(n_trials):
        trial = {}
        for key, values in param_ranges.items():
            if isinstance(values, list) and len(values) == 2 and all(isinstance(v, (int, float)) for v in values):
                # Continuous range [min, max]
                if isinstance(values[0], int):
                    trial[key] = rng.randint(values[0], values[1])
                else:
                    trial[key] = rng.uniform(values[0], values[1])
            elif isinstance(values, list):
                # Discrete choices
                trial[key] = rng.choice(values)
            else:
                trial[key] = values
        trials.append(trial)
    return trials


class HyperparameterTuner:
    """Hyperparameter tuning engine for qlib models.

    Parameters
    ----------
    model_name : str
        Model key in ``QLIB_MODELS``.
    param_grid : dict
        Parameter grid/ranges.  For grid search, values should be lists of
        discrete choices.  For random search, values can be ``[min, max]``
        ranges or discrete lists.
    method : str
        ``"grid"``, ``"random"``, or ``"bayesian"``.
    metric : str
        Metric to optimize (e.g. ``"rmse"``, ``"mae"``, ``"sharpe"``).
    n_trials : int
        Max trials (used by random/bayesian; grid uses all combinations).
    higher_is_better : bool, optional
        Whether higher metric values are better.  Auto-detected from metric name.
    """

    HIGHER_IS_BETTER_METRICS = {"sharpe", "r2", "accuracy", "auc", "ic", "ir"}

    def __init__(
        self,
        model_name: str,
        param_grid: dict[str, list[Any]],
        method: str = "grid",
        metric: str = "rmse",
        n_trials: int = 20,
        higher_is_better: bool | None = None,
        seed: int | None = None,
    ):
        if model_name not in QLIB_MODELS:
            raise KeyError(f"Unknown model: {model_name!r}")

        self.model_name = model_name
        self.param_grid = param_grid
        self.method = method
        self.metric = metric
        self.n_trials = n_trials
        # Local RNG seed — when provided, random/bayesian search becomes
        # reproducible without polluting the global ``random`` state.
        self.seed = seed

        if higher_is_better is not None:
            self.higher_is_better = higher_is_better
        else:
            self.higher_is_better = metric.lower() in self.HIGHER_IS_BETTER_METRICS

    def run(
        self,
        train_fn: Callable[[Any], dict[str, float]],
    ) -> TuningResult:
        """Run the tuning loop.

        Parameters
        ----------
        train_fn : callable
            A function that takes a model instance, trains it, and returns
            a dict of evaluation metrics (must include ``self.metric``).

        Returns
        -------
        TuningResult
        """
        # Generate candidate param sets
        if self.method == "grid":
            candidates = _generate_grid(self.param_grid)
        elif self.method == "random":
            candidates = _generate_random(self.param_grid, self.n_trials, seed=self.seed)
        elif self.method == "bayesian":
            # Simple random sampling as fallback (real BO requires optuna)
            logger.warning(
                "Bayesian optimization not fully implemented; falling back to random search."
            )
            candidates = _generate_random(self.param_grid, self.n_trials, seed=self.seed)
        else:
            raise ValueError(f"Unknown method: {self.method!r}")

        logger.info(
            "Starting %s tuning for %s: %d candidates, metric=%s",
            self.method, self.model_name, len(candidates), self.metric,
        )

        best_score = float("-inf") if self.higher_is_better else float("inf")
        best_params: dict[str, Any] = {}
        all_trials: list[dict[str, Any]] = []

        for i, params in enumerate(candidates):
            try:
                score = _evaluate_model(self.model_name, params, train_fn, self.metric)
            except Exception as e:
                logger.warning("Trial %d failed with params %s: %s", i, params, e)
                score = float("inf") if not self.higher_is_better else float("-inf")

            trial_record = {"params": params, self.metric: score, "trial_idx": i}
            all_trials.append(trial_record)

            improved = (
                (self.higher_is_better and score > best_score)
                or (not self.higher_is_better and score < best_score)
            )
            if improved:
                best_score = score
                best_params = params.copy()

            if (i + 1) % 10 == 0:
                logger.info("Trial %d/%d done. Current best: %.6f", i + 1, len(candidates), best_score)

        return TuningResult(
            best_params=best_params,
            best_score=best_score,
            all_trials=all_trials,
            method=self.method,
            n_trials=len(candidates),
            metric=self.metric,
        )
