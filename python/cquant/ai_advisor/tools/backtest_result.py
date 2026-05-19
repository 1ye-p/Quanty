"""Read-only backtest result summary tool."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import polars as pl

from cquant.ai_advisor.tools.base import AdvisorTool, ToolContext, ToolResult


class BacktestResultTool(AdvisorTool):
    name = "backtest_result"
    description = "Return read-only summary statistics for a completed backtest run."

    async def invoke(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        run_id = str(args.get("run_id", "")).strip()
        if not run_id:
            return ToolResult(success=False, content="BacktestResultTool requires `run_id`.")

        df = await asyncio.to_thread(
            ctx.catalog.query,
            "SELECT run_id, engine, strategy_id, dataset_version, started_at, completed_at, "
            "status, metrics_uri, error_message FROM gold_backtest_runs WHERE run_id = ? LIMIT 1",
            [run_id],
        )
        if df.is_empty():
            return ToolResult(success=False, content=f"Backtest run `{run_id}` not found.")

        row = df.to_dicts()[0]
        metrics = _load_metrics(str(row.get("metrics_uri", "") or ""))
        lines = [
            f"Backtest result [run_id={run_id}]",
            f"Strategy: {row.get('strategy_id', '')}",
            f"Engine: {row.get('engine', '')}",
            f"Status: {row.get('status', '')}",
            f"Started: {row.get('started_at', '')}",
            f"Completed: {row.get('completed_at', '') or 'n/a'}",
        ]
        if metrics:
            lines.append(f"Metrics: {json.dumps(metrics, ensure_ascii=False, sort_keys=True)}")
        if row.get("error_message"):
            lines.append(f"Error: {row['error_message']}")
        return ToolResult(success=True, content="\n".join(lines), metadata={"run_ids": [run_id]})


def _load_metrics(path_str: str) -> dict[str, Any]:
    if not path_str:
        return {}
    path = Path(path_str)
    if not path.is_absolute():
        path = Path.cwd() / path
    if not path.exists():
        return {}
    try:
        if path.suffix == ".json":
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {"value": data}
        if path.suffix == ".parquet":
            frame = pl.read_parquet(path)
            if frame.is_empty():
                return {}
            row = frame.head(1).to_dicts()[0]
            return {k: _jsonable(v) for k, v in row.items()}
    except Exception:
        pass
    return {}


def _jsonable(v: Any) -> Any:
    try:
        json.dumps(v)
        return v
    except TypeError:
        return str(v)
