"""cquant.ai_advisor.router — Table-driven intent classification for agent routing.

Design: each RoutingRule maps a keyword set to a list of agent roles that should be
invoked when any keyword appears in the user message. Multiple rules can match;
the union of their roles is returned. The "core" agents (research, debate,
report_writer) are always added by the orchestrator, not by this router.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RoutingRule:
    """A single intent → agent mapping."""
    keywords: frozenset[str]
    agent_roles: tuple[str, ...]


@dataclass
class AgentIntent:
    """Output of IntentRouter.classify()."""
    required_roles: list[str] = field(default_factory=list)


# Table-driven routing configuration.
# Add new rules here to support new agent types — no changes to orchestrator.py needed.
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
]


class IntentRouter:
    """Classify user messages and return the set of optional agent roles to invoke."""

    def __init__(self, rules: list[RoutingRule] | None = None) -> None:
        self._rules: list[RoutingRule] = rules if rules is not None else ROUTING_TABLE

    def classify(self, text: str) -> AgentIntent:
        """Return the agent roles that should handle *text*.

        The core pipeline agents (research, debate, report_writer) are NOT included —
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

        return AgentIntent(required_roles=matched_roles)

    def add_rule(self, rule: RoutingRule) -> None:
        """Register an additional routing rule at runtime (useful for tests/extensions)."""
        self._rules.append(rule)
