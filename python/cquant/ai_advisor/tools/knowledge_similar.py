"""Similar-documents lookup tool via LanceDB."""

from __future__ import annotations

import asyncio
from typing import Any

from cquant.ai_advisor.tools.base import AdvisorTool, ToolContext, ToolResult


class SimilarDocumentsTool(AdvisorTool):
    name = "similar_documents"
    description = "Find documents similar to a source document via the vector store."

    async def invoke(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        doc_id = str(args.get("doc_id", "")).strip()
        top_k = int(args.get("top_k", 5) or 5)
        if not doc_id:
            return ToolResult(success=False, content="SimilarDocumentsTool requires `doc_id`.")
        if ctx.vector_store is None:
            return ToolResult(success=False, content="Vector store unavailable.")

        try:
            hits = await asyncio.to_thread(ctx.vector_store.similar_to_document, doc_id, top_k)
        except NotImplementedError:
            return ToolResult(success=False, content="Vector store does not implement document similarity.")

        if not hits:
            return ToolResult(success=True, content=f"No similar documents found for `{doc_id}`.",
                              metadata={"doc_ids": [doc_id]})

        similar_ids = [doc_id]
        lines = [f"Documents similar to [doc_id={doc_id}]:"]
        for idx, hit in enumerate(hits, start=1):
            similar_ids.append(hit.doc_id)
            lines.append(f"{idx}. [doc_id={hit.doc_id}] score={hit.score:.4f} | {hit.text[:180]}")
        return ToolResult(success=True, content="\n".join(lines), metadata={"doc_ids": similar_ids})
