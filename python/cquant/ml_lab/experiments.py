"""cquant.ml_lab.experiments — MLflow-backed experiment tracking.

Gracefully degrades to a no-op when MLflow is not installed or the tracking
server is unreachable — downstream code should never need to guard against
MLflow errors.
"""

from __future__ import annotations

import logging
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path
from typing import Any, Generator

from cquant.core.config import settings

logger = logging.getLogger(__name__)

try:
    import mlflow
    _MLFLOW_AVAILABLE = True
except ImportError:
    mlflow = None  # type: ignore[assignment]
    _MLFLOW_AVAILABLE = False


@contextmanager
def _noop_run() -> Generator[None, None, None]:
    """Fallback context manager used when MLflow is unavailable."""
    yield None


class ExperimentTracker:
    """Thin MLflow wrapper that degrades to no-op if tracking is unavailable.

    Usage::

        tracker = ExperimentTracker()
        with tracker.start_run("momentum_xgb_v1"):
            tracker.log_params({"n_estimators": 300, "max_depth": 6})
            artifact = trainer.fit(train_df, valid_df, config)
            tracker.log_metrics(artifact.metrics)
            tracker.log_artifact(artifact.model_path)
    """

    def __init__(self) -> None:
        self._enabled = _MLFLOW_AVAILABLE
        self._tracking_uri = settings.mlflow.tracking_uri
        self._experiment_name = settings.mlflow.experiment_name

        if self._enabled:
            try:
                mlflow.set_tracking_uri(self._tracking_uri)
                mlflow.set_experiment(self._experiment_name)
            except Exception as exc:
                logger.warning(
                    "MLflow unavailable at %s (experiment=%s): %s — tracking disabled.",
                    self._tracking_uri,
                    self._experiment_name,
                    exc,
                )
                self._enabled = False

    @property
    def enabled(self) -> bool:
        return self._enabled and _MLFLOW_AVAILABLE

    def start_run(
        self,
        run_name: str,
        tags: dict[str, str] | None = None,
    ) -> AbstractContextManager[Any]:
        """Start an MLflow run, or return a no-op context if unavailable."""
        if not self.enabled:
            return _noop_run()
        try:
            return mlflow.start_run(run_name=run_name, tags=tags or {})
        except Exception as exc:
            self._disable(exc)
            return _noop_run()

    def log_params(self, params: dict[str, Any]) -> None:
        """Log parameters to the active MLflow run."""
        if not self.enabled:
            return
        self._safe(mlflow.log_params, {k: str(v) for k, v in params.items()})

    def log_metrics(self, metrics: dict[str, float], step: int | None = None) -> None:
        """Log numeric metrics to the active MLflow run."""
        if not self.enabled:
            return
        safe = {k: float(v) for k, v in metrics.items()}
        if step is None:
            self._safe(mlflow.log_metrics, safe)
        else:
            for key, value in safe.items():
                self._safe(mlflow.log_metric, key, value, step=step)

    def log_artifact(self, local_path: str) -> None:
        """Upload a local file artifact if it exists."""
        if not self.enabled:
            return
        path = Path(local_path)
        if not path.exists():
            logger.warning("Skipping artifact: path does not exist: %s", path)
            return
        self._safe(mlflow.log_artifact, str(path))

    def _safe(self, fn: Any, *args: Any, **kwargs: Any) -> None:
        try:
            fn(*args, **kwargs)
        except Exception as exc:
            self._disable(exc)

    def _disable(self, exc: Exception) -> None:
        logger.warning(
            "Disabling MLflow tracking after runtime error (%s: %s).",
            type(exc).__name__,
            exc,
        )
        self._enabled = False
