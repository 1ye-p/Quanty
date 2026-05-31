"""Portfolio optimization guidance tool for AI Advisor."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from cquant.ai_advisor.tools.base import AdvisorTool, ToolContext, ToolResult

logger = logging.getLogger(__name__)


class OptimizeResultTool(AdvisorTool):
    name = "optimize_guidance"
    description = "Provide portfolio optimization guidance (MVO, Risk Parity, Cost-Aware). Returns price data for given assets and optimization best practices."

    async def invoke(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        def _query():
            catalog = ctx.catalog
            parts = []

            asset_ids = args.get("asset_ids", [])
            if isinstance(asset_ids, str):
                asset_ids = [asset_ids]
            if not isinstance(asset_ids, list):
                return "asset_ids must be a list of strings."

            if asset_ids:
                try:
                    placeholders = ",".join(["?" for _ in asset_ids])
                    limit = min(len(asset_ids) * 5, 200)
                    price_df = catalog.query(
                        f"SELECT asset_id, trade_date, close FROM gold_daily_prices "
                        f"WHERE asset_id IN ({placeholders}) "
                        f"ORDER BY trade_date DESC LIMIT {limit}",
                        asset_ids,
                    )
                    if not price_df.is_empty():
                        parts.append("## Recent Price Data\n")
                        for row in price_df.to_dicts():
                            parts.append(f"- {row['asset_id']}: {row['close']:.2f} ({row['trade_date']})")
                except Exception as exc:
                    logger.warning("Price query failed: %s", exc)
                    parts.append(f"Price query failed: {exc}")

            parts.append(
                "\n## Portfolio Optimization Guidance\n"
                "Available optimizers:\n"
                "- **Mean-Variance (MVO)**: Maximize Sharpe ratio, suitable for long-term allocation\n"
                "- **Risk Parity**: Equal risk contribution, suitable for diversified allocation\n"
                "- **Cost-Aware**: Considers transaction costs, suitable for rebalancing\n\n"
                "Recommended steps:\n"
                "1. Compute covariance matrix (Ledoit-Wolf shrinkage recommended)\n"
                "2. Use ML predictions or historical mean as expected returns\n"
                "3. Set per-asset weight cap (e.g. 20%) to avoid concentration\n"
                "4. Compare MVO result against Risk Parity as baseline"
            )

            return "\n".join(parts) if parts else "No optimization data available. Please run optimization in the Optimize page first."

        content = await asyncio.to_thread(_query)
        return ToolResult(success=True, content=content)
