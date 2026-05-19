"""cquant.ai_advisor.agents.base — Agent abstractions."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Iterable

from cquant.ai_advisor.providers import LLMProvider, Message
from cquant.ai_advisor.tools import AdvisorTool, ToolContext
from cquant.ai_advisor.policies import SafetyPolicy

_UUID_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)
_DOC_ID_RE = re.compile(r"\bdoc_id\s*[:=]\s*([^\s,;]+)", re.IGNORECASE)
_DOC_TOKEN_RE = re.compile(r"\b[a-zA-Z0-9:_-]+__[a-zA-Z0-9:_-]+\b")
_STRATEGY_ID_RE = re.compile(r"\bstrategy_id\s*[:=]\s*([^\s,;]+)", re.IGNORECASE)


@dataclass
class AgentTurn:
    role: str
    content: str
    artifacts: list[str] = field(default_factory=list)


class AgentRole(ABC):
    role: str
    system_prompt: str

    @abstractmethod
    async def act(self, context: str, history: list[AgentTurn]) -> AgentTurn:
        """Produce the next agent turn."""


class LLMRole(AgentRole):
    """Tool-aware LLM agent base class."""

    def __init__(
        self,
        provider: LLMProvider,
        safety: SafetyPolicy,
        tool_context: ToolContext | None = None,
        tools: Iterable[AdvisorTool] = (),
        max_tokens: int = 2048,
    ) -> None:
        self._provider = provider
        self._safety = safety
        self._tool_context = tool_context
        self._tools = {tool.name: tool for tool in tools}
        self._max_tokens = max_tokens

    async def act(self, context: str, history: list[AgentTurn]) -> AgentTurn:
        tool_notes, artifacts = await self._build_tool_context(context, history)
        prompt = context.strip()
        if tool_notes:
            prompt = f"{prompt}\n\nTool evidence:\n{tool_notes}"

        response = await self._provider.generate(
            self._build_messages(history, prompt),
            system=self.system_prompt,
            max_tokens=self._max_tokens,
        )
        content = response.content.strip()

        # If LLM unavailable, fall back to tool evidence alone
        if not content or response.stop_reason in {"error", "unavailable"}:
            content = (f"{tool_notes}\n\nLLM status: {response.content}".strip()
                       if tool_notes else response.content)

        safe, warning = self._safety.validate_response(content)
        if not safe:
            content = f"{warning}\n\nThe advisor will not provide live-trading instructions."

        return AgentTurn(role=self.role, content=content, artifacts=dedupe(artifacts))

    async def _build_tool_context(self, context: str, history: list[AgentTurn]) -> tuple[str, list[str]]:
        return "", []

    async def _invoke_tool(self, name: str, args: dict) -> str:
        if self._tool_context is None:
            return ""
        tool = self._tools.get(name)
        if tool is None:
            return ""
        try:
            result = await self._tool_context.call(tool, args)
            return result.content
        except PermissionError as exc:
            return f"[BLOCKED] {exc}"
        except Exception as exc:
            return f"[ERROR] {name}: {exc}"

    def _build_messages(self, history: list[AgentTurn], prompt: str) -> list[Message]:
        messages: list[Message] = []
        for turn in history[-6:]:
            role = "user" if turn.role == "user" else "assistant"
            messages.append(Message(role=role, content=_clip(f"[{turn.role}] {turn.content}")))
        messages.append(Message(role="user", content=prompt))
        return messages


def extract_run_ids(text: str) -> list[str]:
    return dedupe(m.group(0) for m in _UUID_RE.finditer(text))


def extract_doc_ids(text: str) -> list[str]:
    explicit = [m.group(1) for m in _DOC_ID_RE.finditer(text)]
    tokens = [m.group(0) for m in _DOC_TOKEN_RE.finditer(text)]
    return dedupe([*explicit, *tokens])


def extract_strategy_ids(text: str) -> list[str]:
    return dedupe(m.group(1) for m in _STRATEGY_ID_RE.finditer(text))


def dedupe(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for v in values:
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return out


def _clip(text: str, limit: int = 4000) -> str:
    return text if len(text) <= limit else f"{text[:limit]}..."
