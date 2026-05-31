"""ML prediction query tool for AI Advisor."""

from __future__ import annotations

import asyncio
from typing import Any

from cquant.ai_advisor.tools.base import AdvisorTool, ToolContext, ToolResult


class MLPredictionTool(AdvisorTool):
    name = "ml_prediction"
    description = "查询 ML 模型的预测结果。输入 model_version（可选）和 asset_ids（可选），返回最新预测值和模型信息。"

    async def invoke(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        def _query():
            catalog = ctx.catalog
            model_version = args.get("model_version", "")
            asset_ids = args.get("asset_ids", [])

            parts = []

            # Query recent ML experiments
            try:
                exp_df = catalog.query(
                    "SELECT job_id, trainer_name, feature_set_version, target_name, status, "
                    "mlflow_run_id, completed_at FROM meta_ml_jobs "
                    "ORDER BY submitted_at DESC LIMIT 5"
                )
                if not exp_df.is_empty():
                    parts.append("## 最近 ML 实验\n")
                    for row in exp_df.to_dicts():
                        status_icon = "✅" if row["status"] == "done" else "❌" if row["status"] == "error" else "⏳"
                        parts.append(
                            f"- {status_icon} **{row['trainer_name']}** | "
                            f"target={row['target_name']} | "
                            f"feature_set={row.get('feature_set_version', 'N/A')} | "
                            f"status={row['status']} | "
                            f"completed={str(row.get('completed_at', 'N/A'))[:10]}"
                        )
            except Exception:
                parts.append("无法查询 ML 实验列表。")

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
                        parts.append("\n## 资产预测值\n")
                        for row in pred_df.to_dicts():
                            parts.append(
                                f"- {row['asset_id']}: prediction={row['prediction']:.4f} "
                                f"(model={row['model_version']}, date={row['trade_date']})"
                            )
                except Exception:
                    parts.append("无法查询预测数据。")

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
                        parts.append(f"\n## 模型 {model_version} 最新预测 Top-20\n")
                        for row in pred_df.to_dicts():
                            parts.append(f"- {row['asset_id']}: {row['prediction']:.4f} ({row['trade_date']})")
                except Exception:
                    parts.append(f"无法查询模型 {model_version} 的预测。")

            if not parts:
                return "当前无 ML 实验或预测数据。"

            return "\n".join(parts)

        content = await asyncio.to_thread(_query)
        return ToolResult(success=True, content=content)
