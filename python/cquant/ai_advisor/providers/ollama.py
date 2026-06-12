"""cquant.ai_advisor.providers.ollama — Ollama local LLM provider."""

from __future__ import annotations

import json
import logging
from typing import Any

from cquant.ai_advisor.providers.base import (
    LLMProvider,
    Message,
    ModelResponse,
    normalize_messages,
    run_sync_response,
    _unavailable,
)

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "qwen2.5:14b"
_DEFAULT_BASE_URL = "http://localhost:11434"


class OllamaProvider(LLMProvider):
    """Ollama local LLM provider using /api/chat endpoint.

    Requires ``httpx`` (already a project dependency) and a running Ollama server.
    """

    name = "ollama"

    def __init__(
        self,
        model: str = _DEFAULT_MODEL,
        base_url: str = _DEFAULT_BASE_URL,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._available_cache: bool | None = None
        self._available_since: float = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def chat(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Low-level chat completion mirroring Ollama's /api/chat contract.

        Returns the raw JSON response dict from Ollama or an error dict.
        """
        try:
            import httpx
        except ImportError:
            return {"error": "httpx not installed"}

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(f"{self.base_url}/api/chat", json=payload)
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as exc:
            logger.warning("Ollama HTTP error: %s", exc)
            return {"error": f"Ollama HTTP {exc.response.status_code}: {exc.response.text[:200]}"}
        except Exception as exc:
            logger.warning("Ollama request failed: %s", exc)
            return {"error": str(exc)}

    async def is_available(self) -> bool:
        """Check whether the Ollama server is reachable and the model is loaded.

        Results are cached for 60 seconds to avoid repeated HTTP requests.
        """
        import time

        now = time.monotonic()
        if self._available_cache is not None and (now - self._available_since) < 60:
            return self._available_cache

        try:
            import httpx
        except ImportError:
            self._available_cache = False
            self._available_since = now
            return False

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                if resp.status_code != 200:
                    self._available_cache = False
                    self._available_since = now
                    return False
                models = resp.json().get("models", [])
                result = any(
                    m.get("name", "").startswith(self.model.split(":")[0])
                    for m in models
                )
                self._available_cache = result
                self._available_since = now
                return result
        except Exception:
            self._available_cache = False
            self._available_since = now
            return False

    # ------------------------------------------------------------------
    # LLMProvider interface (used by advisor agents)
    # ------------------------------------------------------------------

    async def generate(
        self,
        messages: list[Message],
        system: str = "",
        max_tokens: int = 4096,
    ) -> ModelResponse:
        if not await self.is_available():
            return _unavailable(
                f"Ollama not reachable or model '{self.model}' not loaded.",
                model=self.model,
            )

        prompt_system, payload = normalize_messages(messages, system)
        if prompt_system:
            payload.insert(0, {"role": "system", "content": prompt_system})
        if not payload:
            payload = [{"role": "user", "content": "Provide a concise research answer."}]

        raw = await self.chat(payload)
        if "error" in raw:
            return _unavailable(raw["error"], model=self.model)

        content = raw.get("message", {}).get("content", "")
        usage = raw.get("usage", {})
        return ModelResponse(
            content=content.strip(),
            input_tokens=int(usage.get("prompt_tokens", 0)),
            output_tokens=int(usage.get("completion_tokens", 0)),
            model=raw.get("model", self.model),
            stop_reason="stop" if raw.get("done") else "length",
        )

    def generate_sync(
        self,
        messages: list[Message],
        system: str = "",
        max_tokens: int = 4096,
    ) -> ModelResponse:
        return run_sync_response(
            lambda: self.generate(messages, system=system, max_tokens=max_tokens)
        )
