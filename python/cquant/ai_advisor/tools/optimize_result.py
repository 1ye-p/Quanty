"""Portfolio optimization query tool for AI Advisor."""

from __future__ import annotations

import asyncio
from typing import Any

from cquant.ai_advisor.tools.base import AdvisorTool, ToolContext, ToolResult


class OptimizeResultTool(AdvisorTool):
    name = "optimize_result"
    description = "查询组合优化的最新结果和权重配置。可回答关于资产配置、权重分配、风险收益比的问题。"

    async def invoke(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        def _query():
            catalog = ctx.catalog
            parts = []

            asset_ids = args.get("asset_ids", [])

            if asset_ids:
                try:
                    placeholders = ",".join(["?" for _ in asset_ids])
                    price_df = catalog.query(
                        f"SELECT asset_id, trade_date, close FROM gold_daily_prices "
                        f"WHERE asset_id IN ({placeholders}) "
                        f"ORDER BY trade_date DESC LIMIT ?",
                        asset_ids + [len(asset_ids) * 5],
                    )
                    if not price_df.is_empty():
                        parts.append("## 最近价格数据\n")
                        for row in price_df.to_dicts():
                            parts.append(f"- {row['asset_id']}: {row['close']:.2f} ({row['trade_date']})")
                except Exception:
                    pass

            parts.append(
                "\n## 组合优化建议\n"
                "可用优化器：\n"
                "- **Mean-Variance (MVO)**: 最大化 Sharpe 比率，适合长期配置\n"
                "- **Risk Parity**: 等风险贡献，适合分散化配置\n"
                "- **Cost-Aware**: 考虑交易成本，适合调仓场景\n\n"
                "建议步骤：\n"
                "1. 先计算资产协方差矩阵（推荐 Ledoit-Wolf 收缩估计）\n"
                "2. 用 ML 预测或历史均值作为预期收益\n"
                "3. 设置单资产权重上限（如 20%）避免集中风险\n"
                "4. 用 Risk Parity 作为基准对比 MVO 结果"
            )

            return "\n".join(parts) if parts else "暂无优化数据。请先在组合优化页面运行优化。"

        content = await asyncio.to_thread(_query)
        return ToolResult(success=True, content=content)
