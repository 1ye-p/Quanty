"""Offline execution coordinator agent (NO live trading)."""

from __future__ import annotations

from cquant.ai_advisor.agents.base import LLMRole, dedupe, extract_run_ids


class ExecutionAgent(LLMRole):
    role = "execution"
    system_prompt = (
        "You coordinate offline research jobs only. You may discuss backtest and analysis run "
        "status, prerequisites, and next offline steps. You must never access broker adapters, "
        "submit live orders, or suggest real trading actions."
    )

    async def _build_tool_context(self, context: str, history: list) -> tuple[str, list[str]]:
        del history
        run_ids = extract_run_ids(context)[:2]
        if not run_ids:
            return (
                "Execution is offline-only. No backtest run_id found in the request; "
                "only status guidance can be provided.",
                [],
            )
        sections = [await self._invoke_tool("backtest_run", {"run_id": rid}) for rid in run_ids]
        return "\n\n".join(s for s in sections if s.strip()), dedupe(run_ids)
