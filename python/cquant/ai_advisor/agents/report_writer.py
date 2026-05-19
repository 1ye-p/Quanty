"""Markdown report writer agent — no tools, synthesis only."""

from __future__ import annotations

from cquant.ai_advisor.agents.base import LLMRole


class ReportWriterAgent(LLMRole):
    role = "report_writer"
    system_prompt = (
        "You synthesize advisor findings into structured markdown. Prefer sections: "
        "Summary, Evidence, Risk Review, Counterpoints, and Next Steps. "
        "Cite run_ids and doc_ids when present, state uncertainty explicitly, "
        "and never suggest live trading."
    )
