"""Read-only risk snapshot lookup tool."""

from __future__ import annotations

import asyncio
from typing import Any

from cquant.ai_advisor.tools.base import AdvisorTool, ToolContext, ToolResult


class RiskSnapshotTool(AdvisorTool):
    name = "risk_snapshot"
    description = "Return the latest stored portfolio risk snapshot for a run or strategy."

    async def invoke(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        run_id = str(args.get("run_id", "")).strip()
        strategy_id = str(args.get("strategy_id", "")).strip()
        if not run_id and not strategy_id:
            return ToolResult(success=False, content="RiskSnapshotTool requires `run_id` or `strategy_id`.")

        if run_id:
            sql = ("SELECT run_id, snapshot_ts, strategy_id, gross_leverage, net_leverage, beta, "
                   "drawdown, var_95, cvar_95, sector_exposure, factor_exposure "
                   "FROM gold_risk_snapshots WHERE run_id = ? ORDER BY snapshot_ts DESC LIMIT 1")
            params, ref = [run_id], run_id
        else:
            sql = ("SELECT run_id, snapshot_ts, strategy_id, gross_leverage, net_leverage, beta, "
                   "drawdown, var_95, cvar_95, sector_exposure, factor_exposure "
                   "FROM gold_risk_snapshots WHERE strategy_id = ? ORDER BY snapshot_ts DESC LIMIT 1")
            params, ref = [strategy_id], strategy_id

        df = await asyncio.to_thread(ctx.catalog.query, sql, params)
        if df.is_empty():
            return ToolResult(success=False, content=f"No risk snapshot found for `{ref}`.")

        row = df.to_dicts()[0]
        return ToolResult(
            success=True,
            content=(
                f"Risk snapshot [run_id={row.get('run_id', '')}] "
                f"[strategy_id={row.get('strategy_id', '')}]\n"
                f"Snapshot time: {row.get('snapshot_ts', '')}\n"
                f"Gross leverage: {float(row.get('gross_leverage', 0.0)):.4f}\n"
                f"Net leverage: {float(row.get('net_leverage', 0.0)):.4f}\n"
                f"Beta: {row.get('beta', 'n/a')}\n"
                f"Drawdown: {float(row.get('drawdown', 0.0)):.4f}\n"
                f"VaR 95: {row.get('var_95', 'n/a')}\n"
                f"CVaR 95: {row.get('cvar_95', 'n/a')}"
            ),
            metadata={"run_ids": [str(row.get("run_id", ""))]},
        )
