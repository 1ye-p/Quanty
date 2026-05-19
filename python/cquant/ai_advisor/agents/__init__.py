"""Agent roles used by ai_advisor."""

from cquant.ai_advisor.agents.base import AgentRole, AgentTurn
from cquant.ai_advisor.agents.debate import DebateAgent
from cquant.ai_advisor.agents.execution import ExecutionAgent
from cquant.ai_advisor.agents.report_writer import ReportWriterAgent
from cquant.ai_advisor.agents.research import ResearchAgent
from cquant.ai_advisor.agents.risk import RiskAgent

__all__ = [
    "AgentRole", "AgentTurn",
    "DebateAgent", "ExecutionAgent", "ReportWriterAgent", "ResearchAgent", "RiskAgent",
]
