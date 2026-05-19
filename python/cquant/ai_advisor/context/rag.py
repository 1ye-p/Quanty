"""cquant.ai_advisor.context.rag — 3-layer RAG context builder."""

from __future__ import annotations

from cquant.knowledge_base import KnowledgeBaseService, SearchQuery


class RAGContext:
    """Build layered retrieval context for the advisor.

    Level 1: document titles / metadata summary
    Level 2: retrieved chunk headlines
    Level 3: on-demand tool list (for agents with tool access)
    """

    def __init__(self, top_k: int = 5) -> None:
        self._top_k = top_k

    def build(
        self,
        query: str,
        kb_service: KnowledgeBaseService,
        level: int = 2,
    ) -> str:
        try:
            response = kb_service.search(SearchQuery(text=query, top_k=self._top_k))
        except Exception as exc:
            return f"RAG context unavailable: {exc}"

        if not response.hits:
            return f"User query: {query}\n\nKnowledge-base context: no relevant documents found."

        sections = [f"User query: {query}"]

        if level >= 1:
            lines = ["Relevant document metadata:"]
            for hit in response.hits:
                lines.append(
                    f"- [doc_id={hit.doc_id}] title={hit.title or 'untitled'} "
                    f"| source={hit.source_name or 'unknown'} | type={hit.logical_type or 'unknown'}"
                )
            sections.append("\n".join(lines))

        if level >= 2:
            lines = ["Retrieved evidence chunks:"]
            for hit in response.hits:
                if hit.headline:
                    lines.append(f"- [doc_id={hit.doc_id}] {hit.headline}")
            if len(lines) == 1:
                lines.append("- No chunk excerpts available from hybrid search.")
            sections.append("\n".join(lines))

        if level >= 3:
            sections.append(
                "On-demand tools available: knowledge_search, report_summary, entity_relation, "
                "similar_documents, backtest_result, analysis_report, risk_snapshot, backtest_run."
            )

        return "\n\n".join(sections)
