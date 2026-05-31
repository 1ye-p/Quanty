"""ML prediction query tool for AI Advisor."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from cquant.ai_advisor.tools.base import AdvisorTool, ToolContext, ToolResult

logger = logging.getLogger(__name__)


class MLPredictionTool(AdvisorTool):
    name = "ml_prediction"
    description = "Query ML model predictions. Accepts optional model_version and asset_ids. Returns latest predictions and model info."

    async def invoke(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        def _query():
            catalog = ctx.catalog
            model_version = args.get("model_version", "")
            asset_ids = args.get("asset_ids", [])
            if isinstance(asset_ids, str):
                asset_ids = [asset_ids]
            if not isinstance(asset_ids, list):
                return "asset_ids must be a list of strings."

            parts = []

            # Query recent ML experiments
            try:
                exp_df = catalog.query(
                    "SELECT job_id, trainer_name, feature_set_version, target_name, status, "
                    "mlflow_run_id, completed_at FROM meta_ml_jobs "
                    "ORDER BY submitted_at DESC LIMIT 5"
                )
                if not exp_df.is_empty():
                    parts.append("## Recent ML Experiments\n")
                    for row in exp_df.to_dicts():
                        status_icon = "done" if row["status"] == "done" else "error" if row["status"] == "error" else "running"
                        parts.append(
                            f"- [{status_icon}] **{row['trainer_name']}** | "
                            f"target={row['target_name']} | "
                            f"feature_set={row.get('feature_set_version', 'N/A')} | "
                            f"status={row['status']} | "
                            f"completed={str(row.get('completed_at', 'N/A'))[:10]}"
                        )
            except Exception as exc:
                logger.warning("ML experiment query failed: %s", exc)
                parts.append(f"Failed to query ML experiments: {exc}")

            # Query predictions for specific assets
            if asset_ids:
                try:
                    placeholders = ",".join(["?" for _ in asset_ids])
                    pred_df = catalog.query(
                        f"SELECT model_version, trade_date, asset_id, prediction "
                        f"FROM gold_predictions "
                        f"WHERE asset_id IN ({placeholders}) "
                        f"ORDER BY trade_date DESC LIMIT 50",
                        asset_ids,
                    )
                    if not pred_df.is_empty():
                        parts.append("\n## Asset Predictions\n")
                        for row in pred_df.to_dicts():
                            parts.append(
                                f"- {row['asset_id']}: prediction={row['prediction']:.4f} "
                                f"(model={row['model_version']}, date={row['trade_date']})"
                            )
                except Exception as exc:
                    logger.warning("Prediction query failed: %s", exc)
                    parts.append(f"Failed to query predictions: {exc}")

            # Query predictions for specific model
            if model_version:
                try:
                    pred_df = catalog.query(
                        "SELECT trade_date, asset_id, prediction "
                        "FROM gold_predictions WHERE model_version = ? "
                        "ORDER BY trade_date DESC, prediction DESC LIMIT 20",
                        [model_version],
                    )
                    if not pred_df.is_empty():
                        parts.append(f"\n## Model {model_version} Top-20 Predictions\n")
                        for row in pred_df.to_dicts():
                            parts.append(f"- {row['asset_id']}: {row['prediction']:.4f} ({row['trade_date']})")
                except Exception as exc:
                    logger.warning("Model prediction query failed: %s", exc)
                    parts.append(f"Failed to query model {model_version}: {exc}")

            if not parts:
                return "No ML experiments or predictions available."

            return "\n".join(parts)

        content = await asyncio.to_thread(_query)
        return ToolResult(success=True, content=content)
