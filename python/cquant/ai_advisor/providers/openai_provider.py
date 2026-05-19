"""cquant.ai_advisor.providers.openai_provider — OpenAI fallback provider."""

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


class OpenAIProvider(LLMProvider):
    """OpenAI chat-completions fallback provider."""

    name = "openai"

    def __init__(self, model: str = "gpt-4o", api_key: str | None = None) -> None:
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
            return self._unavailable("OpenAI API key is not configured. Set OPENAI_API_KEY in .env.")
        try:
            from openai import AsyncOpenAI
        except ImportError:
            return self._unavailable("openai SDK not installed. Run: pip install openai")

        prompt_system, payload = normalize_messages(messages, system)
        if prompt_system:
            payload = [{"role": "system", "content": prompt_system}, *payload]
        if not payload:
            payload = [{"role": "user", "content": "Provide a concise research answer."}]

        try:
            client = AsyncOpenAI(api_key=api_key)
            response = await client.chat.completions.create(
                model=self.model, messages=payload, max_tokens=max_tokens
            )
            return self._parse_response(response)
        except Exception as exc:
            return self._unavailable(f"OpenAI request failed: {exc}")

    def generate_sync(
        self,
        messages: list[Message],
        system: str = "",
        max_tokens: int = 4096,
    ) -> ModelResponse:
        return run_sync_response(lambda: self.generate(messages, system=system, max_tokens=max_tokens))

    def _resolved_key(self) -> str:
        return (self._api_key or settings.openai_api_key).strip()

    def _parse_response(self, response: Any) -> ModelResponse:
        choice = response.choices[0] if getattr(response, "choices", None) else None
        content = ""
        if choice is not None and getattr(choice, "message", None) is not None:
            content = str(getattr(choice.message, "content", "") or "")
        usage = getattr(response, "usage", None)
        return ModelResponse(
            content=content.strip(),
            input_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
            output_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
            model=str(getattr(response, "model", self.model)),
            stop_reason=str(getattr(choice, "finish_reason", "stop") if choice else "stop"),
        )

    def _unavailable(self, reason: str) -> ModelResponse:
        return ModelResponse(content=reason, input_tokens=0, output_tokens=0,
                             model=self.model, stop_reason="unavailable")
