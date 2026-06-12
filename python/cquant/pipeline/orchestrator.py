"""cquant.pipeline.orchestrator — Five-stage automated pipeline.

Stages:
  1. Factors  — materialise factor values from the data warehouse
  2. ML       — walk-forward model training
  3. Backtest — vectorised backtest on OOS predictions
  4. Analysis — compute IC / Sharpe / drawdown metrics
  5. Promotion — optionally promote model to production if threshold met
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from cquant.pipeline.config import PipelineConfig

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    """Run the full cQuant pipeline end-to-end.

    Parameters
    ----------
    catalog
        Initialised ``Catalog`` (DuckDB) instance.
    config
        Pipeline configuration.  Uses defaults when omitted.
    """

    def __init__(self, catalog: Any, config: PipelineConfig | None = None) -> None:
        self._catalog = catalog
        self._config = config or PipelineConfig()
        self._last_run: dict[str, Any] | None = None

    @property
    def config(self) -> PipelineConfig:
        return self._config

    @property
    def last_run(self) -> dict[str, Any] | None:
        return self._last_run

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_full_pipeline(self) -> dict[str, Any]:
        """Execute all five stages sequentially.

        Returns
        -------
        dict
            Summary with keys ``run_id``, ``stages``, ``status``, ``started_at``,
            ``finished_at``, and per-stage results.
        """
        run_id = uuid.uuid4().hex[:12]
        started_at = datetime.now(tz=timezone.utc)
        cfg = self._config
        stages: dict[str, Any] = {}
        status = "success"

        logger.info("Pipeline %s started — feature_set=%s, models=%s", run_id, cfg.feature_set_version, cfg.model_types)

        # Stage 1: Factors
        stages["factors"] = self._stage_factors(run_id)

        # Stage 2: ML training
        stages["ml"] = self._stage_ml(run_id)

        # Stage 3: Backtest
        stages["backtest"] = self._stage_backtest(run_id)

        # Stage 4: Analysis
        stages["analysis"] = self._stage_analysis(run_id)

        # Stage 5: Promotion
        stages["promotion"] = self._stage_promotion(run_id)

        # Check for failures
        for name, result in stages.items():
            if isinstance(result, dict) and result.get("status") == "error":
                status = "partial_failure"
                break

        finished_at = datetime.now(tz=timezone.utc)
        self._last_run = {
            "run_id": run_id,
            "config": asdict(cfg),
            "stages": stages,
            "status": status,
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "duration_seconds": (finished_at - started_at).total_seconds(),
        }

        logger.info("Pipeline %s finished — status=%s, duration=%.1fs",
                     run_id, status, self._last_run["duration_seconds"])
        return self._last_run

    # ------------------------------------------------------------------
    # Stages
    # ------------------------------------------------------------------

    def _stage_factors(self, run_id: str) -> dict[str, Any]:
        """Stage 1: Materialise factor values."""
        logger.info("[%s] Stage 1/5: factor materialisation", run_id)
        try:
            from cquant.factorlab.materializer import FactorMaterializer

            mat = FactorMaterializer(self._catalog)
            result = mat.materialise(
                dataset_version=self._config.feature_set_version,
                factor_names=self._config.factor_names or None,
            )
            return {"status": "success", "rows": result.get("total_rows", 0)}
        except Exception as exc:
            logger.error("[%s] Factor stage failed: %s", run_id, exc)
            return {"status": "error", "error": str(exc)}

    def _stage_ml(self, run_id: str) -> dict[str, Any]:
        """Stage 2: Walk-forward ML training."""
        logger.info("[%s] Stage 2/5: ML training (models=%s)", run_id, self._config.model_types)
        try:
            from cquant.ml_lab.pipeline import run_ml_prediction_pipeline
            from cquant.factorlab.materializer import FactorMaterializer

            mat = FactorMaterializer(self._catalog)
            features = mat.load_features(self._config.feature_set_version)

            if features.is_empty():
                return {"status": "error", "error": "No features available"}

            model_ids: list[str] = []
            for model_type in self._config.model_types:
                mid = run_ml_prediction_pipeline(
                    catalog=self._catalog,
                    features=features,
                    model_id_prefix=f"pipeline_{model_type}",
                    n_splits=self._config.n_splits,
                    gap_days=self._config.gap_days,
                )
                model_ids.append(mid)

            return {"status": "success", "model_ids": model_ids}
        except Exception as exc:
            logger.error("[%s] ML stage failed: %s", run_id, exc)
            return {"status": "error", "error": str(exc)}

    def _stage_backtest(self, run_id: str) -> dict[str, Any]:
        """Stage 3: Vectorised backtest on OOS predictions."""
        logger.info("[%s] Stage 3/5: backtest", run_id)
        try:
            from cquant.backtest_vector.engine import VectorBacktestEngine

            engine = VectorBacktestEngine(catalog=self._catalog)
            result = engine.run(
                model_ids=self._last_run.get("stages", {}).get("ml", {}).get("model_ids", []),
                top_n=self._config.top_n,
                initial_cash=self._config.initial_cash,
                rebalance_frequency=self._config.rebalance_frequency,
            )
            return {"status": "success", "run_id": result.get("run_id", "")}
        except Exception as exc:
            logger.error("[%s] Backtest stage failed: %s", run_id, exc)
            return {"status": "error", "error": str(exc)}

    def _stage_analysis(self, run_id: str) -> dict[str, Any]:
        """Stage 4: Compute performance metrics."""
        logger.info("[%s] Stage 4/5: analysis", run_id)
        try:
            from cquant.bt_analyzer.metrics import compute_metrics

            bt_run_id = self._last_run.get("stages", {}).get("backtest", {}).get("run_id", "")
            if not bt_run_id:
                return {"status": "error", "error": "No backtest run_id available"}

            metrics = compute_metrics(self._catalog, bt_run_id)
            return {
                "status": "success",
                "sharpe": metrics.get("sharpe_ratio", 0),
                "annual_return": metrics.get("annual_return", 0),
                "max_drawdown": metrics.get("max_drawdown", 0),
            }
        except Exception as exc:
            logger.error("[%s] Analysis stage failed: %s", run_id, exc)
            return {"status": "error", "error": str(exc)}

    def _stage_promotion(self, run_id: str) -> dict[str, Any]:
        """Stage 5: Promote model to production if threshold met."""
        logger.info("[%s] Stage 5/5: promotion", run_id)
        try:
            analysis = self._last_run.get("stages", {}).get("analysis", {})
            sharpe = analysis.get("sharpe", 0)
            threshold = self._config.promotion_threshold

            if not self._config.auto_promote:
                return {"status": "skipped", "reason": "auto_promote disabled"}

            if sharpe < threshold:
                return {
                    "status": "skipped",
                    "reason": f"Sharpe {sharpe:.3f} below threshold {threshold}",
                }

            from cquant.ml_lab.model_registry import ModelRegistry

            registry = ModelRegistry(self._catalog)
            ml_stage = self._last_run.get("stages", {}).get("ml", {})
            model_ids = ml_stage.get("model_ids", [])

            promoted = []
            for mid in model_ids:
                registry.promote(mid, stage="production")
                promoted.append(mid)

            return {"status": "success", "promoted_models": promoted}
        except Exception as exc:
            logger.error("[%s] Promotion stage failed: %s", run_id, exc)
            return {"status": "error", "error": str(exc)}
