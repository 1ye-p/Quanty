"""Read-only backtest job status tool."""

from __future__ import annotations

import asyncio
from typing import Any

from cquant.ai_advisor.tools.base import AdvisorTool, ToolContext, ToolResult


class BacktestRunTool(AdvisorTool):
    name = "backtest_run"
    description = "Return offline run status for a backtest job (read-only)."

    async def invoke(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        run_id = str(args.get("run_id", "")).strip()
        if not run_id:
            return ToolResult(success=False, content="BacktestRunTool requires `run_id`.")

        df = await asyncio.to_thread(
            ctx.catalog.query,
            "SELECT run_id, strategy_id, engine, status, started_at, completed_at, error_message "
            "FROM gold_backtest_runs WHERE run_id = ? LIMIT 1",
            [run_id],
        )
        if df.is_empty():
            return ToolResult(success=False, content=f"Backtest job `{run_id}` not found.")

        row = df.to_dicts()[0]
        return ToolResult(
            success=True,
            content=(
                f"Offline run status [run_id={run_id}]\n"
                f"Strategy: {row.get('strategy_id', '')}\n"
                f"Engine: {row.get('engine', '')}\n"
                f"Status: {row.get('status', '')}\n"
                f"Started: {row.get('started_at', '')}\n"
                f"Completed: {row.get('completed_at', '') or 'n/a'}\n"
                f"Error: {row.get('error_message', '') or 'none'}"
            ),
            metadata={"run_ids": [run_id]},
        )
