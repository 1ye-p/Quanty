"""Knowledge-base hybrid search tool."""

from __future__ import annotations

import asyncio
from typing import Any

from cquant.ai_advisor.tools.base import AdvisorTool, ToolContext, ToolResult
from cquant.knowledge_base import SearchQuery


class KnowledgeSearchTool(AdvisorTool):
    name = "knowledge_search"
    description = "Hybrid search the knowledge base and return cited matches."

    async def invoke(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        text = str(args.get("text", "")).strip()
        top_k = int(args.get("top_k", 5) or 5)
        if not text:
            return ToolResult(success=False, content="KnowledgeSearchTool requires a non-empty `text`.")

        response = await asyncio.to_thread(
            ctx.kb_service.search,
            SearchQuery(text=text, top_k=top_k, session_id=ctx.session_id),
        )
        if not response.hits:
            return ToolResult(success=True, content=f"No knowledge-base matches found for `{text}`.",
                              metadata={"doc_ids": []})

        lines = [f"Knowledge-base matches for `{text}`:"]
        doc_ids: list[str] = []
        for idx, hit in enumerate(response.hits, start=1):
            doc_ids.append(hit.doc_id)
            excerpt = f" | excerpt={hit.headline}" if hit.headline else ""
            lines.append(
                f"{idx}. [doc_id={hit.doc_id}] title={hit.title or 'untitled'} "
                f"| source={hit.source_name or 'unknown'} | score={hit.score:.4f}{excerpt}"
            )
        return ToolResult(success=True, content="\n".join(lines), metadata={"doc_ids": doc_ids})
