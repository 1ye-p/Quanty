"""Machine learning experiment and job routes."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from cquant.api_server.deps import CatalogDep
from cquant.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ml", tags=["ml"])


class MLJobBody(BaseModel):
    trainer: str                    # 'xgb' | 'lgbm'
    feature_set_version: str
    target_name: str = "ret_5d"
    params: dict = {}
    model_id: str = ""


@router.get("/experiments")
async def list_experiments(catalog: CatalogDep, limit: int = 50) -> dict:
    """List ML experiments from MLflow via DuckDB or MLflow SDK."""
    try:
        import mlflow
        mlflow.set_tracking_uri(settings.mlflow.tracking_uri)
        client = mlflow.tracking.MlflowClient()
        experiments = client.search_experiments()
        runs = []
        for exp in experiments:
            for run in client.search_runs(
                experiment_ids=[exp.experiment_id],
                max_results=limit,
            ):
                runs.append({
                    "run_id": run.info.run_id,
                    "experiment_name": exp.name,
                    "trainer_name": run.data.params.get("trainer_name", ""),
                    "status": run.info.status,
                    "metrics": dict(run.data.metrics),
                    "params": dict(run.data.params),
                    "started_at": run.info.start_time,
                    "artifact_uri": run.info.artifact_uri,
                })
        return {"items": runs[:limit], "total": len(runs), "source": "mlflow"}
    except Exception as exc:
        logger.warning("MLflow unavailable: %s — falling back to DuckDB", exc)
        # Fallback: read meta_ml_jobs from DuckDB
        df = catalog.query(
            "SELECT job_id, trainer_name, feature_set_version, target_name, "
            "status, mlflow_run_id, submitted_at, completed_at "
            "FROM meta_ml_jobs ORDER BY submitted_at DESC LIMIT ?",
            [limit],
        )
        return {"items": df.to_dicts(), "total": df.height, "source": "duckdb"}


@router.get("/experiments/{run_id}")
async def get_experiment(run_id: str, catalog: CatalogDep) -> dict:
    try:
        import mlflow
        mlflow.set_tracking_uri(settings.mlflow.tracking_uri)
        client = mlflow.tracking.MlflowClient()
        run = client.get_run(run_id)
        return {
            "run_id": run.info.run_id,
            "status": run.info.status,
            "metrics": dict(run.data.metrics),
            "params": dict(run.data.params),
            "artifact_uri": run.info.artifact_uri,
            "source": "mlflow",
        }
    except Exception:
        df = catalog.query(
            "SELECT * FROM meta_ml_jobs WHERE mlflow_run_id = ? OR job_id = ?",
            [run_id, run_id],
        )
        if df.is_empty():
            raise HTTPException(status_code=404, detail=f"Experiment '{run_id}' not found")
        return {**df.to_dicts()[0], "source": "duckdb"}


@router.get("/experiments/{run_id}/feature-importance")
async def feature_importance(run_id: str) -> dict:
    """Extract feature importance from saved model artifact."""
    try:
        import mlflow
        import polars as pl
        from pathlib import Path

        mlflow.set_tracking_uri(settings.mlflow.tracking_uri)
        client = mlflow.tracking.MlflowClient()
        run = client.get_run(run_id)
        trainer = run.data.params.get("trainer_name", "")
        artifact_uri = run.info.artifact_uri.replace("file://", "")

        if "xgboost" in trainer:
            import xgboost as xgb
            model_path = list(Path(artifact_uri).glob("**/*.json"))[0]
            model = xgb.XGBRegressor()
            model.load_model(str(model_path))
            scores = dict(zip(model.get_booster().feature_names or [], model.feature_importances_))
        elif "lightgbm" in trainer:
            import lightgbm as lgb
            model_path = list(Path(artifact_uri).glob("**/*.txt"))[0]
            booster = lgb.Booster(model_file=str(model_path))
            scores = dict(zip(booster.feature_name(), booster.feature_importance(importance_type='gain')))
        else:
            return {"items": [], "total": 0, "note": "Unknown trainer"}

        items = sorted(
            [{"feature": k, "importance": float(v)} for k, v in scores.items()],
            key=lambda x: x["importance"],
            reverse=True,
        )
        return {"items": items, "total": len(items)}
    except Exception as exc:
        logger.warning("Feature importance extraction failed: %s", exc)
        return {"items": [], "total": 0, "error": str(exc)}


@router.post("/jobs", status_code=202)
async def submit_ml_job(
    body: MLJobBody,
    background_tasks: BackgroundTasks,
    catalog: CatalogDep,
) -> dict:
    """Submit an async ML training job."""
    job_id = str(uuid.uuid4())
    now = datetime.now(tz=timezone.utc).isoformat()

    catalog.execute(
        """INSERT INTO meta_ml_jobs
           (job_id, trainer_name, feature_set_version, target_name, params_json, status, submitted_at)
           VALUES (?, ?, ?, ?, ?, 'pending', ?)""",
        [job_id, body.trainer, body.feature_set_version,
         body.target_name, json.dumps(body.params), now],
    )

    background_tasks.add_task(
        _run_ml_job, job_id, body, catalog
    )
    return {"job_id": job_id, "status": "submitted"}


@router.get("/jobs/{job_id}")
async def get_ml_job(job_id: str, catalog: CatalogDep) -> dict:
    df = catalog.query(
        "SELECT * FROM meta_ml_jobs WHERE job_id = ?", [job_id]
    )
    if df.is_empty():
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return df.to_dicts()[0]


def _run_ml_job(job_id: str, body: MLJobBody, catalog: CatalogDep) -> None:
    """Background task: run the ML training job."""
    import asyncio
    from datetime import timezone

    now = datetime.now(tz=timezone.utc).isoformat()
    try:
        catalog.execute(
            "UPDATE meta_ml_jobs SET status = 'running' WHERE job_id = ?", [job_id]
        )

        if body.trainer == "xgb":
            from cquant.ml_lab.trainers.xgb import XGBTrainer
            trainer = XGBTrainer()
        elif body.trainer == "lgbm":
            from cquant.ml_lab.trainers.lgbm import LGBMTrainer
            trainer = LGBMTrainer()
        else:
            raise ValueError(f"Unknown trainer: {body.trainer!r}")

        from cquant.ml_lab.datasets import MLDataset

        # Auto-infer feature names from gold_factor_values for this feature_set_version,
        # excluding the target factor.
        factor_df = catalog.query(
            "SELECT DISTINCT factor_name FROM gold_factor_values WHERE feature_set_version = ?",
            [body.feature_set_version],
        )
        all_factors = factor_df["factor_name"].to_list() if not factor_df.is_empty() else []
        feature_names = [f for f in all_factors if f != body.target_name]

        if not feature_names:
            raise ValueError(
                f"No factor values found for feature_set_version='{body.feature_set_version}'. "
                "Run the factor pipeline first to populate gold_factor_values."
            )

        dataset = MLDataset.from_catalog(
            catalog=catalog,
            feature_set_version=body.feature_set_version,
            feature_names=feature_names,
            target_name=body.target_name,
        )
        train, valid, _ = dataset.train_valid_test_split()
        config = {"target_name": body.target_name, "params": body.params}
        if body.model_id:
            config["model_id"] = body.model_id

        artifact = trainer.fit(train, valid, config)

        from cquant.ml_lab.experiments import ExperimentTracker
        tracker = ExperimentTracker()
        # Capture the actual MLflow run_id from the active run context, if available
        mlflow_run_id = artifact.model_id   # fallback when MLflow is unavailable
        with tracker.start_run(run_name=f"{body.trainer}_{job_id[:8]}") as mlrun:
            tracker.log_params({"trainer": body.trainer, "feature_set": body.feature_set_version,
                                 "target": body.target_name})
            tracker.log_metrics(artifact.metrics)
            tracker.log_artifact(artifact.model_path)
            if mlrun is not None and hasattr(mlrun, "info"):
                mlflow_run_id = mlrun.info.run_id

        completed = datetime.now(tz=timezone.utc).isoformat()
        catalog.execute(
            "UPDATE meta_ml_jobs SET status = 'done', mlflow_run_id = ?, artifact_path = ?, completed_at = ? WHERE job_id = ?",
            [mlflow_run_id, artifact.model_path, completed, job_id],
        )
    except Exception as exc:
        logger.exception("ML job %s failed: %s", job_id, exc)
        catalog.execute(
            "UPDATE meta_ml_jobs SET status = 'error', error_text = ?, completed_at = ? WHERE job_id = ?",
            [str(exc), datetime.now(tz=timezone.utc).isoformat(), job_id],
        )
