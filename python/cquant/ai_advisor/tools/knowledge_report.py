"""Knowledge-base report summary lookup tool."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from cquant.ai_advisor.tools.base import AdvisorTool, ToolContext, ToolResult


class ReportSummaryTool(AdvisorTool):
    name = "report_summary"
    description = "Load stored document metadata and the most recent persisted summary."

    async def invoke(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        doc_id = str(args.get("doc_id", "")).strip()
        if not doc_id:
            return ToolResult(success=False, content="ReportSummaryTool requires `doc_id`.")

        doc_df = await asyncio.to_thread(ctx.kb_service.get_document, doc_id)
        if doc_df.is_empty():
            return ToolResult(success=False, content=f"Document `{doc_id}` was not found.")

        doc = doc_df.to_dicts()[0]
        summary_df = await asyncio.to_thread(
            ctx.catalog.query,
            "SELECT summary_kind, content_path, model_name, created_at "
            "FROM kb_summaries WHERE doc_id = ? ORDER BY created_at DESC LIMIT 5",
            [doc_id],
        )

        summary_kind, summary_text = "", ""
        for row in summary_df.to_dicts():
            text = _read_file(row.get("content_path", ""))
            if text:
                summary_kind = str(row.get("summary_kind", "summary"))
                summary_text = text
                break

        lines = [
            f"Document summary for [doc_id={doc_id}]",
            f"Title: {doc.get('title', '') or 'untitled'}",
            f"Source: {doc.get('source_name', '') or 'unknown'}",
            f"Logical type: {doc.get('logical_type', '') or 'unknown'}",
            f"Published at: {doc.get('published_at', '') or 'unknown'}",
            (f"{summary_kind.title()} summary: {summary_text}"
             if summary_text else "Summary: No persisted summary text found."),
        ]
        return ToolResult(success=True, content="\n".join(lines), metadata={"doc_ids": [doc_id]})


def _read_file(path_str: str) -> str:
    if not path_str:
        return ""
    path = Path(path_str)
    if not path.is_absolute():
        path = Path.cwd() / path
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8").strip()[:1600]
    except OSError:
        return ""
