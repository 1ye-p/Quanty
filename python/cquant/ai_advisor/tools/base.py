"""cquant.ai_advisor.tools.base — Tool contracts and execution context."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from cquant.datahub.catalog import Catalog
from cquant.knowledge_base import KnowledgeBaseService
from cquant.knowledge_base.store.vector_base import VectorStore

if TYPE_CHECKING:
    from cquant.ai_advisor.policies import SafetyPolicy


@dataclass
class ToolResult:
    success: bool
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolContext:
    """Runtime context passed to every tool invocation."""

    kb_service: KnowledgeBaseService
    catalog: Catalog
    safety: "SafetyPolicy"
    vector_store: VectorStore | None = None
    session_id: str = ""

    async def call(self, tool: "AdvisorTool", args: dict[str, Any]) -> ToolResult:
        """Authorize and invoke *tool* with *args*."""
        allowed, reason = self.safety.authorize(tool.name, args)
        if not allowed:
            raise PermissionError(reason)
        if not tool.read_only:
            raise PermissionError(
                f"Tool '{tool.name}' is not read-only and cannot be used by ai_advisor"
            )
        return await tool.invoke(args, self)


class AdvisorTool(ABC):
    """Abstract advisor tool — all tools are read-only by default."""

    name: str
    description: str
    read_only: bool = True

    @abstractmethod
    async def invoke(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        """Execute the tool and return a ToolResult."""
