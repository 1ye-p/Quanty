"""Read-only analysis (overfit) report lookup tool."""

from __future__ import annotations

import asyncio
from typing import Any

from cquant.ai_advisor.tools.base import AdvisorTool, ToolContext, ToolResult


class AnalysisReportTool(AdvisorTool):
    name = "analysis_report"
    description = "Return post-backtest overfit and robustness analysis from DuckDB."

    async def invoke(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        analysis_id = str(args.get("analysis_run_id", "")).strip()
        backtest_id = str(args.get("backtest_run_id", "")).strip()
        if not analysis_id and not backtest_id:
            return ToolResult(success=False, content="AnalysisReportTool requires `analysis_run_id` or `backtest_run_id`.")

        if analysis_id:
            sql = ("SELECT analysis_run_id, backtest_run_id, overall_overfit_score, dsr, psr, summary, created_at "
                   "FROM gold_bt_analysis_runs WHERE analysis_run_id = ? LIMIT 1")
            params = [analysis_id]
        else:
            sql = ("SELECT analysis_run_id, backtest_run_id, overall_overfit_score, dsr, psr, summary, created_at "
                   "FROM gold_bt_analysis_runs WHERE backtest_run_id = ? ORDER BY created_at DESC LIMIT 1")
            params = [backtest_id]

        df = await asyncio.to_thread(ctx.catalog.query, sql, params)
        if df.is_empty():
            return ToolResult(success=False, content=f"No analysis report found for `{analysis_id or backtest_id}`.")

        row = df.to_dicts()[0]
        return ToolResult(
            success=True,
            content=(
                f"Analysis report [analysis_run_id={row.get('analysis_run_id', '')}] "
                f"for [run_id={row.get('backtest_run_id', '')}]\n"
                f"Overfit score: {float(row.get('overall_overfit_score', 0.0)):.4f}\n"
                f"PSR: {float(row.get('psr', 0.0)):.4f}\n"
                f"DSR: {float(row.get('dsr', 0.0)):.4f}\n"
                f"Summary: {row.get('summary', '') or 'n/a'}"
            ),
            metadata={"run_ids": [str(row.get("backtest_run_id", ""))]},
        )
