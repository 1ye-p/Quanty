"""Unit tests for cquant.ai_advisor."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from cquant.ai_advisor.policies import SafetyPolicy
from cquant.ai_advisor.providers import FallbackProvider, LLMProvider, Message, ModelResponse
from cquant.ai_advisor.tools import AdvisorTool, ToolContext, ToolResult


# ── SafetyPolicy ───────────────────────────────────────────────────────────────

class TestSafetyPolicy:
    def setup_method(self) -> None:
        self.policy = SafetyPolicy()

    def test_forbidden_tool_rejected(self) -> None:
        allowed, reason = self.policy.authorize("broker_adapter", {})
        assert not allowed
        assert "forbidden" in reason.lower()

    def test_allowed_tool_passes(self) -> None:
        allowed, reason = self.policy.authorize("knowledge_search", {})
        assert allowed
        assert reason == ""

    def test_safe_response_passes(self) -> None:
        safe, _ = self.policy.validate_response("The momentum factor performed well in 2024.")
        assert safe

    def test_live_trading_instruction_blocked(self) -> None:
        safe, warning = self.policy.validate_response("Please place an order to buy 100 shares.")
        assert not safe
        assert warning

    def test_explanation_of_no_trading_is_safe(self) -> None:
        safe, _ = self.policy.validate_response("Live trading is not permitted by this advisor.")
        assert safe


# ── FallbackProvider ───────────────────────────────────────────────────────────

class _StubProvider(LLMProvider):
    name = "stub"

    def __init__(self, stop_reason: str = "stop", content: str = "ok") -> None:
        self._stop_reason = stop_reason
        self._content = content

    async def generate(self, messages, system="", max_tokens=4096) -> ModelResponse:
        return ModelResponse(content=self._content, input_tokens=1, output_tokens=1,
                             model=self.name, stop_reason=self._stop_reason)

    def generate_sync(self, messages, system="", max_tokens=4096) -> ModelResponse:
        return asyncio.run(self.generate(messages, system=system, max_tokens=max_tokens))


class TestFallbackProvider:
    def test_first_available_wins(self) -> None:
        p1 = _StubProvider(stop_reason="unavailable", content="p1 unavailable")
        p2 = _StubProvider(stop_reason="stop", content="p2 ok")
        fb = FallbackProvider([p1, p2])
        resp = fb.generate_sync([Message(role="user", content="hi")])
        assert resp.content == "p2 ok"
        assert resp.stop_reason == "stop"

    def test_all_unavailable_returns_last(self) -> None:
        p1 = _StubProvider(stop_reason="unavailable")
        p2 = _StubProvider(stop_reason="unavailable", content="p2 error")
        fb = FallbackProvider([p1, p2])
        resp = fb.generate_sync([Message(role="user", content="hi")])
        assert resp.stop_reason == "unavailable"


# ── ToolContext safety gate ────────────────────────────────────────────────────

class _ReadOnlyTool(AdvisorTool):
    name = "ok_tool"
    description = "test"
    read_only = True

    async def invoke(self, args, ctx) -> ToolResult:
        return ToolResult(success=True, content="result")


class _WriteTool(AdvisorTool):
    name = "write_tool"
    description = "test write"
    read_only = False

    async def invoke(self, args, ctx) -> ToolResult:
        return ToolResult(success=True, content="wrote")


def _tool_context() -> ToolContext:
    kb = MagicMock()
    catalog = MagicMock()
    return ToolContext(kb_service=kb, catalog=catalog, safety=SafetyPolicy())


def test_tool_context_allows_read_only() -> None:
    ctx = _tool_context()
    result = asyncio.run(ctx.call(_ReadOnlyTool(), {}))
    assert result.success
    assert result.content == "result"


def test_tool_context_blocks_non_read_only() -> None:
    ctx = _tool_context()
    with pytest.raises(PermissionError, match="not read-only"):
        asyncio.run(ctx.call(_WriteTool(), {}))


def test_tool_context_blocks_forbidden_tool_name() -> None:
    class ForbiddenTool(AdvisorTool):
        name = "broker_adapter"
        description = "forbidden"
        read_only = True

        async def invoke(self, args, ctx) -> ToolResult:
            return ToolResult(success=True, content="should not reach")

    ctx = _tool_context()
    with pytest.raises(PermissionError, match="forbidden"):
        asyncio.run(ctx.call(ForbiddenTool(), {}))


# ── AdvisorSession Tests ──────────────────────────────────────────────────────

class TestAdvisorSession:
    def test_session_creation(self):
        from cquant.ai_advisor.orchestrator import AdvisorSession

        session = AdvisorSession()
        assert session.session_id is not None
        assert len(session.session_id) > 0
        assert session.history == []

    def test_session_has_unique_id(self):
        from cquant.ai_advisor.orchestrator import AdvisorSession

        s1 = AdvisorSession()
        s2 = AdvisorSession()
        assert s1.session_id != s2.session_id

    def test_session_custom_id(self):
        from cquant.ai_advisor.orchestrator import AdvisorSession

        session = AdvisorSession(session_id="custom-id")
        assert session.session_id == "custom-id"


# ── SafetyPolicy Extended Tests ───────────────────────────────────────────────

class TestSafetyPolicyExtended:
    def setup_method(self) -> None:
        self.policy = SafetyPolicy()

    def test_all_forbidden_tools_blocked(self):
        from cquant.ai_advisor.policies import SafetyPolicy
        for tool_name in SafetyPolicy.FORBIDDEN_TOOLS:
            allowed, _ = self.policy.authorize(tool_name, {})
            assert not allowed, f"Expected {tool_name} to be blocked"

    def test_validate_response_blocks_buy_order(self):
        safe, _ = self.policy.validate_response("Please place an order to buy 600036 shares")
        assert not safe

    def test_validate_response_blocks_sell_order(self):
        safe, _ = self.policy.validate_response("Place a sell order for 1000 shares")
        assert not safe

    def test_validate_response_allows_analysis(self):
        safe, _ = self.policy.validate_response(
            "Based on the factor analysis, the momentum signal is strong."
        )
        assert safe
