"""cquant.ai_advisor — Multi-agent research advisor with RAG and safety rails.

Key safety constraint: this module is research-only.
It will never access broker_adapter, place_order, or any live-trading surface.

Usage::

    from cquant.ai_advisor import AdvisorOrchestrator, AdvisorSession, ClaudeProvider
    from cquant.ai_advisor import SafetyPolicy
    from cquant.ai_advisor.tools import KnowledgeSearchTool, BacktestResultTool
    from cquant.knowledge_base import KnowledgeBaseService

    provider = ClaudeProvider()  # reads ANTHROPIC_API_KEY from .env
    kb = KnowledgeBaseService.create()
    safety = SafetyPolicy()
    tools = [KnowledgeSearchTool(), BacktestResultTool()]

    orchestrator = AdvisorOrchestrator(
        provider=provider,
        agents=None,          # use defaults
        tools=tools,
        kb_service=kb,
        safety=safety,
    )
    session = AdvisorSession()
    response = orchestrator.chat_sync("What does the Goldman Sachs AI report say?", session)
"""

from cquant.ai_advisor.agents import (
    AgentRole, AgentTurn,
    DebateAgent, ExecutionAgent, ReportWriterAgent, ResearchAgent, RiskAgent,
)
from cquant.ai_advisor.context import RAGContext
from cquant.ai_advisor.orchestrator import AdvisorOrchestrator, AdvisorSession
from cquant.ai_advisor.policies import SafetyPolicy
from cquant.ai_advisor.providers import (
    ClaudeProvider, FallbackProvider, LLMProvider, Message, ModelResponse, OpenAIProvider,
)
from cquant.ai_advisor.tools import (
    AdvisorTool, AnalysisReportTool, BacktestResultTool, BacktestRunTool,
    EntityRelationTool, KnowledgeSearchTool, ReportSummaryTool,
    RiskSnapshotTool, SimilarDocumentsTool, ToolContext, ToolResult,
)

__all__ = [
    "AdvisorOrchestrator", "AdvisorSession",
    "AdvisorTool", "AgentRole", "AgentTurn",
    "AnalysisReportTool", "BacktestResultTool", "BacktestRunTool",
    "ClaudeProvider", "DebateAgent", "EntityRelationTool",
    "ExecutionAgent", "FallbackProvider", "KnowledgeSearchTool",
    "LLMProvider", "Message", "ModelResponse", "OpenAIProvider",
    "RAGContext", "ReportSummaryTool", "ReportWriterAgent",
    "ResearchAgent", "RiskAgent", "RiskSnapshotTool",
    "SafetyPolicy", "SimilarDocumentsTool", "ToolContext", "ToolResult",
]
