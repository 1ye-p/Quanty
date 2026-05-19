"""Risk analyst agent."""

from __future__ import annotations

from cquant.ai_advisor.agents.base import LLMRole, dedupe, extract_run_ids, extract_strategy_ids


class RiskAgent(LLMRole):
    role = "risk"
    system_prompt = (
        "You are a portfolio risk analyst. Explain risk metrics, audit exposures, flag leverage, "
        "drawdown, concentration, and model-overfit concerns. Keep the analysis offline and never "
        "recommend placing trades."
    )

    async def _build_tool_context(self, context: str, history: list) -> tuple[str, list[str]]:
        del history
        sections: list[str] = []
        artifacts: list[str] = []

        for run_id in extract_run_ids(context)[:2]:
            result = await self._invoke_tool("risk_snapshot", {"run_id": run_id})
            if result:
                sections.append(result)
            artifacts.append(run_id)

        for sid in extract_strategy_ids(context)[:1]:
            result = await self._invoke_tool("risk_snapshot", {"strategy_id": sid})
            if result:
                sections.append(result)
            artifacts.append(sid)

        if not sections:
            sections.append(
                "RiskSnapshotTool was not invoked — no explicit run_id or strategy_id found. "
                "Provide a run_id for concrete portfolio exposure data."
            )

        return "\n\n".join(sections), dedupe(artifacts)
