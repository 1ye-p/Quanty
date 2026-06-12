"""cquant.ai_advisor.router -- Table-driven + LLM-fallback intent classification.

Design: each RoutingRule maps a keyword set to a list of agent roles that should be
invoked when any keyword appears in the user message. Multiple rules can match;
the union of their roles is returned. The "core" agents (research, debate,
report_writer) are always added by the orchestrator, not by this router.

When keyword matching returns no roles, an LLM-based classifier can be used as
fallback. Pass an LLMProvider to enable this behaviour.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

_LLM_CLASSIFY_SYSTEM = (
    "You are an intent classifier for a quantitative research assistant. "
    "Given a user message, determine which specialist agent(s) should handle it.\n\n"
    "Available roles:\n"
    "- research: ML predictions, optimization, general research, factor analysis\n"
    "- risk: risk metrics, drawdown, volatility, alerts, exposure\n"
    "- execution: running backtests, job status, task queues\n\n"
    "Respond with ONLY a JSON array of role names, e.g. [\"risk\"] or [\"research\",\"risk\"]. "
    "If no specialist is needed (purely conversational), return []."
)


@dataclass(frozen=True)
class RoutingRule:
    """A single intent -> agent mapping."""
    keywords: frozenset[str]
    agent_roles: tuple[str, ...]


@dataclass
class AgentIntent:
    """Output of IntentRouter.classify()."""
    required_roles: list[str] = field(default_factory=list)


# Table-driven routing configuration.
# Add new rules here to support new agent types -- no changes to orchestrator.py needed.
ROUTING_TABLE: list[RoutingRule] = [
    RoutingRule(
        keywords=frozenset({
            "risk", "drawdown", "leverage", "exposure", "var", "cvar",
            "beta", "overfit", "psr", "dsr", "volatility", "风险", "回撤",
        }),
        agent_roles=("risk",),
    ),
    RoutingRule(
        keywords=frozenset({
            "run status", "job status", "queue", "backtest run", "analysis run",
            "offline run", "run_id", "执行", "任务状态",
        }),
        agent_roles=("execution",),
    ),
    RoutingRule(
        keywords=frozenset({
            "predict", "prediction", "ml model", "机器学习", "预测", "模型推理",
            "optimize", "optimization", "portfolio optimization", "组合优化", "mvo",
            "risk parity", "weight", "权重",
        }),
        agent_roles=("research",),
    ),
    RoutingRule(
        keywords=frozenset({
            "alert", "alarm", "notification", "告警", "预警", "通知",
        }),
        agent_roles=("risk",),
    ),
]


class IntentRouter:
    """Classify user messages and return the set of optional agent roles to invoke.

    Supports two classification strategies:
    1. **Keyword matching** (fast, deterministic) -- always tried first.
    2. **LLM fallback** (optional) -- used when keyword matching returns no roles.
       Pass an ``llm_provider`` to enable.
    """

    VALID_ROLES = {"research", "risk", "execution"}

    def __init__(
        self,
        rules: list[RoutingRule] | None = None,
        llm_provider: object | None = None,
    ) -> None:
        self._rules: list[RoutingRule] = rules if rules is not None else ROUTING_TABLE
        self._llm = llm_provider

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def classify(self, text: str) -> AgentIntent:
        """Return the agent roles that should handle *text*.

        The core pipeline agents (research, debate, report_writer) are NOT included --
        those are always run by the orchestrator. Only optional specialist roles are returned.
        """
        lower = text.lower()
        matched_roles: list[str] = []
        seen: set[str] = set()

        for rule in self._rules:
            if any(kw in lower for kw in rule.keywords):
                for role in rule.agent_roles:
                    if role not in seen:
                        seen.add(role)
                        matched_roles.append(role)

        if matched_roles:
            return AgentIntent(required_roles=matched_roles)

        # LLM fallback
        if self._llm is not None:
            roles = self._llm_classify(text)
            if roles:
                return AgentIntent(required_roles=roles)

        return AgentIntent(required_roles=[])

    async def classify_async(self, text: str) -> AgentIntent:
        """Async variant that awaits LLM fallback when keyword matching is empty."""
        lower = text.lower()
        matched_roles: list[str] = []
        seen: set[str] = set()

        for rule in self._rules:
            if any(kw in lower for kw in rule.keywords):
                for role in rule.agent_roles:
                    if role not in seen:
                        seen.add(role)
                        matched_roles.append(role)

        if matched_roles:
            return AgentIntent(required_roles=matched_roles)

        if self._llm is not None:
            roles = await self._llm_classify_async(text)
            if roles:
                return AgentIntent(required_roles=roles)

        return AgentIntent(required_roles=[])

    def add_rule(self, rule: RoutingRule) -> None:
        """Register an additional routing rule at runtime (useful for tests/extensions)."""
        self._rules.append(rule)

    # ------------------------------------------------------------------
    # LLM classification helpers
    # ------------------------------------------------------------------

    def _llm_classify(self, text: str) -> list[str]:
        """Synchronous LLM classification fallback."""
        try:
            from cquant.ai_advisor.providers.base import Message, LLMProvider

            if not isinstance(self._llm, LLMProvider):
                return []

            messages = [Message(role="user", content=text)]
            resp = self._llm.generate_sync(messages, system=_LLM_CLASSIFY_SYSTEM, max_tokens=128)
            return self._parse_roles(resp.content)
        except Exception as exc:
            logger.debug("LLM routing fallback failed: %s", exc)
            return []

    async def _llm_classify_async(self, text: str) -> list[str]:
        """Async LLM classification fallback."""
        try:
            from cquant.ai_advisor.providers.base import Message, LLMProvider

            if not isinstance(self._llm, LLMProvider):
                return []

            messages = [Message(role="user", content=text)]
            resp = await self._llm.generate(messages, system=_LLM_CLASSIFY_SYSTEM, max_tokens=128)
            return self._parse_roles(resp.content)
        except Exception as exc:
            logger.debug("LLM routing fallback failed: %s", exc)
            return []

    def _parse_roles(self, raw: str) -> list[str]:
        """Extract valid role names from LLM output (expects a JSON array)."""
        try:
            parsed = json.loads(raw.strip())
            if isinstance(parsed, list):
                return [r for r in parsed if r in self.VALID_ROLES]
        except (json.JSONDecodeError, TypeError):
            import re
            found = re.findall(r'"(\w+)"', raw)
            return [r for r in found if r in self.VALID_ROLES]
        return []
