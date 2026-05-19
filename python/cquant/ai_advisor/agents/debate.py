"""Devil's-advocate agent — no tools, pure reasoning."""

from __future__ import annotations

from cquant.ai_advisor.agents.base import LLMRole


class DebateAgent(LLMRole):
    role = "debate"
    system_prompt = (
        "You are the devil's advocate in a quantitative research review. Challenge conclusions, "
        "look for weak evidence, alternative explanations, and overconfidence. "
        "Keep critiques specific and actionable."
    )
