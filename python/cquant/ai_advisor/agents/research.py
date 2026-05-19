"""Research analyst agent."""

from __future__ import annotations

from cquant.ai_advisor.agents.base import LLMRole, dedupe, extract_doc_ids, extract_run_ids


class ResearchAgent(LLMRole):
    role = "research"
    system_prompt = (
        "You are a quantitative research analyst. Analyze backtest performance, explain factor "
        "behavior, identify patterns, cite evidence, and state uncertainty when evidence is thin. "
        "Never suggest live execution."
    )

    async def _build_tool_context(self, context: str, history: list) -> tuple[str, list[str]]:
        del history
        sections: list[str] = []
        artifacts: list[str] = []

        result = await self._invoke_tool("knowledge_search", {"text": context, "top_k": 5})
        if result:
            sections.append(result)

        for doc_id in extract_doc_ids(context)[:2]:
            summary = await self._invoke_tool("report_summary", {"doc_id": doc_id})
            if summary:
                sections.append(summary)
            artifacts.append(doc_id)

        for run_id in extract_run_ids(context)[:2]:
            bt = await self._invoke_tool("backtest_result", {"run_id": run_id})
            ar = await self._invoke_tool("analysis_report", {"backtest_run_id": run_id})
            if bt:
                sections.append(bt)
            if ar:
                sections.append(ar)
            artifacts.append(run_id)

        return "\n\n".join(s for s in sections if s.strip()), dedupe(artifacts)
