"""Entity and mention lookup tool."""

from __future__ import annotations

import asyncio
from typing import Any

from cquant.ai_advisor.tools.base import AdvisorTool, ToolContext, ToolResult


class EntityRelationTool(AdvisorTool):
    name = "entity_relation"
    description = "Return entities mentioned in a knowledge-base document."

    async def invoke(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        doc_id = str(args.get("doc_id", "")).strip()
        limit = int(args.get("limit", 10) or 10)
        if not doc_id:
            return ToolResult(success=False, content="EntityRelationTool requires `doc_id`.")

        df = await asyncio.to_thread(
            ctx.catalog.query,
            """
            SELECT m.entity_id, e.entity_type, e.canonical_name,
                   m.mention_text, m.role, m.confidence
            FROM kb_entity_mentions AS m
            LEFT JOIN kb_entities AS e ON e.entity_id = m.entity_id
            WHERE m.doc_id = ?
            ORDER BY m.confidence DESC, e.canonical_name ASC
            LIMIT ?
            """,
            [doc_id, limit],
        )
        if df.is_empty():
            return ToolResult(success=True, content=f"No entity mentions found for `{doc_id}`.",
                              metadata={"doc_ids": [doc_id]})

        lines = [f"Entities for [doc_id={doc_id}]:"]
        for row in df.to_dicts():
            name = row.get("canonical_name", "") or row.get("entity_id", "")
            lines.append(
                f"- {name} ({row.get('entity_type', 'unknown')}) "
                f"| mention={row.get('mention_text', '')} "
                f"| role={row.get('role', '')} "
                f"| confidence={float(row.get('confidence', 0.0)):.2f}"
            )
        return ToolResult(success=True, content="\n".join(lines), metadata={"doc_ids": [doc_id]})
