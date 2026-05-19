"""cquant.ai_advisor.policies.safety — Safety guardrails.

Prevents ai_advisor from ever accessing live-trading surfaces.
"""

from __future__ import annotations

import re


class SafetyPolicy:
    """Authorize tool calls and validate LLM responses for safety.

    Rules:
    1. Forbidden tool names → reject before invocation.
    2. Response validation → reject if output contains live-trading patterns.
    """

    FORBIDDEN_TOOLS = frozenset([
        "broker_adapter", "live_trading", "place_order", "cancel_order",
    ])

    # Phrases that indicate the response is *explaining* that trading is not allowed.
    _SAFE_EXPLANATIONS = (
        "live trading is not permitted",
        "never place orders",
        "do not place orders",
        "broker access is forbidden",
        "offline-only",
        "cannot place",
    )

    # Patterns that suggest the response is trying to instruct actual trades.
    _DANGEROUS_PATTERNS = (
        re.compile(r"\b(place_order|cancel_order|broker_adapter|live_trading)\b", re.IGNORECASE),
        re.compile(r"\b(place|submit|execute|route|cancel)\b.{0,24}\b(order|trade)\b", re.IGNORECASE),
        re.compile(r"(^|\n)\s*(buy|sell|short|cover)\b(?!\s+side)", re.IGNORECASE),
    )

    def authorize(self, tool_name: str, args: dict) -> tuple[bool, str]:
        """Return (allowed, reason). Raises nothing — caller decides."""
        del args
        normalized = tool_name.strip().lower()
        if normalized in self.FORBIDDEN_TOOLS:
            return False, f"Tool '{tool_name}' is forbidden: live trading is not permitted"
        return True, ""

    def validate_response(self, content: str) -> tuple[bool, str]:
        """Return (safe, warning_message)."""
        lowered = content.lower()
        if any(phrase in lowered for phrase in self._SAFE_EXPLANATIONS):
            return True, ""
        for pattern in self._DANGEROUS_PATTERNS:
            if pattern.search(content):
                return (
                    False,
                    "Safety policy blocked a response that appeared to include "
                    "broker or live-trading instructions.",
                )
        return True, ""
