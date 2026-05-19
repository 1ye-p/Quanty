"""cquant.ai_advisor.providers.base — LLM provider contracts."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable, Coroutine, Iterable


@dataclass(frozen=True)
class Message:
    role: str       # 'user' | 'assistant' | 'system'
    content: str


@dataclass(frozen=True)
class ModelResponse:
    content: str
    input_tokens: int
    output_tokens: int
    model: str
    stop_reason: str


class LLMProvider(ABC):
    """Abstract LLM provider used by advisor agents."""

    name: str

    @abstractmethod
    async def generate(
        self,
        messages: list[Message],
        system: str = "",
        max_tokens: int = 4096,
    ) -> ModelResponse:
        """Generate one assistant completion (async)."""

    @abstractmethod
    def generate_sync(
        self,
        messages: list[Message],
        system: str = "",
        max_tokens: int = 4096,
    ) -> ModelResponse:
        """Sync wrapper for Jupyter / CLI use."""


class FallbackProvider(LLMProvider):
    """Try providers in order until one succeeds."""

    name = "fallback"

    def __init__(self, providers: Iterable[LLMProvider]) -> None:
        self._providers = list(providers)

    async def generate(
        self,
        messages: list[Message],
        system: str = "",
        max_tokens: int = 4096,
    ) -> ModelResponse:
        last = _unavailable("no providers configured", model="fallback")
        for provider in self._providers:
            resp = await provider.generate(messages, system=system, max_tokens=max_tokens)
            if resp.stop_reason not in {"unavailable", "error"}:
                return resp
            last = resp
        return last

    def generate_sync(
        self,
        messages: list[Message],
        system: str = "",
        max_tokens: int = 4096,
    ) -> ModelResponse:
        last = _unavailable("no providers configured", model="fallback")
        for provider in self._providers:
            resp = provider.generate_sync(messages, system=system, max_tokens=max_tokens)
            if resp.stop_reason not in {"unavailable", "error"}:
                return resp
            last = resp
        return last


def run_sync_response(
    factory: Callable[[], Coroutine[object, object, ModelResponse]],
) -> ModelResponse:
    """Run async generation safely from sync code, even under Jupyter."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(factory())
    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(lambda: asyncio.run(factory())).result()


def normalize_messages(
    messages: list[Message],
    system: str = "",
) -> tuple[str, list[dict[str, str]]]:
    """Split system content from chat messages."""
    system_parts = [system.strip()] if system.strip() else []
    payload: list[dict[str, str]] = []
    for msg in messages:
        if msg.role == "system":
            if msg.content.strip():
                system_parts.append(msg.content.strip())
            continue
        role = "assistant" if msg.role == "assistant" else "user"
        payload.append({"role": role, "content": msg.content})
    return "\n\n".join(system_parts), payload


def _unavailable(reason: str, *, model: str) -> ModelResponse:
    return ModelResponse(content=reason, input_tokens=0, output_tokens=0, model=model, stop_reason="unavailable")
