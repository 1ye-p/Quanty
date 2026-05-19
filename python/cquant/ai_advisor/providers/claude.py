"""cquant.ai_advisor.providers.claude — Anthropic Claude provider."""

from __future__ import annotations

from typing import Any

from cquant.ai_advisor.providers.base import (
    LLMProvider,
    Message,
    ModelResponse,
    normalize_messages,
    run_sync_response,
)
from cquant.core.config import settings


class ClaudeProvider(LLMProvider):
    """Primary Anthropic provider with graceful degradation."""

    name = "claude"

    def __init__(
        self,
        model: str = "claude-opus-4-6",
        api_key: str | None = None,
    ) -> None:
        self.model = model
        self._api_key = api_key

    async def generate(
        self,
        messages: list[Message],
        system: str = "",
        max_tokens: int = 4096,
    ) -> ModelResponse:
        api_key = self._resolved_key()
        if not api_key:
            return self._unavailable("Claude API key is not configured. Set ANTHROPIC_API_KEY in .env.")
        try:
            from anthropic import AsyncAnthropic
        except ImportError:
            return self._unavailable("anthropic SDK not installed. Run: pip install anthropic")

        prompt_system, payload = normalize_messages(messages, system)
        if not payload:
            payload = [{"role": "user", "content": "Provide a concise research answer."}]

        try:
            client = AsyncAnthropic(api_key=api_key)
            response = await client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=prompt_system or None,
                messages=payload,
            )
            return self._parse_response(response)
        except Exception as exc:
            return self._unavailable(f"Claude request failed: {exc}")

    def generate_sync(
        self,
        messages: list[Message],
        system: str = "",
        max_tokens: int = 4096,
    ) -> ModelResponse:
        return run_sync_response(lambda: self.generate(messages, system=system, max_tokens=max_tokens))

    def _resolved_key(self) -> str:
        return (self._api_key or settings.anthropic_api_key).strip()

    def _parse_response(self, response: Any) -> ModelResponse:
        blocks = getattr(response, "content", [])
        text = "\n".join(
            b.text for b in blocks
            if getattr(b, "type", "") == "text" and getattr(b, "text", "")
        ).strip()
        usage = getattr(response, "usage", None)
        return ModelResponse(
            content=text,
            input_tokens=int(getattr(usage, "input_tokens", 0) or 0),
            output_tokens=int(getattr(usage, "output_tokens", 0) or 0),
            model=str(getattr(response, "model", self.model)),
            stop_reason=str(getattr(response, "stop_reason", "stop")),
        )

    def _unavailable(self, reason: str) -> ModelResponse:
        return ModelResponse(content=reason, input_tokens=0, output_tokens=0,
                             model=self.model, stop_reason="unavailable")
