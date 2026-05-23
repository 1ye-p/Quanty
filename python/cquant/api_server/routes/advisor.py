"""AI Advisor chat and report routes."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from cquant.ai_advisor import (
    AdvisorSession,
    ClaudeProvider,
    FallbackProvider,
    OpenAIProvider,
    SafetyPolicy,
)
from cquant.ai_advisor.agents import (
    DebateAgent,
    ReportWriterAgent,
    ResearchAgent,
    RiskAgent,
)
from cquant.ai_advisor.agents.base import AgentTurn
from cquant.ai_advisor.context import RAGContext
from cquant.ai_advisor.orchestrator import _debate_ctx, _fallback_md, _writer_ctx
from cquant.ai_advisor.tools import (
    AnalysisReportTool,
    BacktestResultTool,
    BacktestRunTool,
    KnowledgeSearchTool,
    ReportSummaryTool,
    RiskSnapshotTool,
    ToolContext,
)
from cquant.api_server.deps import CatalogDep, KBServiceDep
from cquant.api_server.schemas.advisor import (
    AdvisorChatRequest,
    AdvisorChatResponse,
    AdvisorReportRequest,
    AdvisorReportResponse,
)
from cquant.ai_advisor.session_store import SessionStore
from cquant.core.config import settings
from cquant.knowledge_base.store.vector_lance import LanceVectorStore

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/advisor", tags=["advisor"])

# SQLite-backed session store — survives API server restarts
# Note: settings.db_path is a str, so wrap with Path()
_store = SessionStore(Path(settings.db_path).parent / "advisor_sessions.db")

# Singleton vector store — avoids re-opening the LanceDB index on every request
_vector_store: LanceVectorStore | None = None
_MAX_HISTORY_TURNS = 50   # cap per-session turn count (sliding window)


def _get_vector_store() -> LanceVectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = LanceVectorStore(
            Path(settings.storage.knowledge_root) / "vector" / "lancedb"
        )
    return _vector_store


async def _get_or_create_session(session_id: str) -> AdvisorSession:
    if session_id:
        try:
            existing = await asyncio.to_thread(_store.load, session_id)
            if existing is not None:
                return existing
        except Exception as exc:
            logger.warning("Failed to load session %s: %s", session_id, exc)
    session = AdvisorSession()
    try:
        await asyncio.to_thread(_store.save, session)
    except Exception as exc:
        logger.warning("Failed to save new session %s: %s", session.session_id, exc)
    return session


def _session_artifacts(session: AdvisorSession) -> list[str]:
    last = session.history[-1] if session.history else None
    return getattr(last, "artifacts", []) if last else []


def _recent_history(session: AdvisorSession, n: int = 20) -> list[AgentTurn]:
    """Return the last *n* turns to avoid ballooning context size."""
    return session.history[-n:]


def _build_provider() -> FallbackProvider:
    return FallbackProvider([ClaudeProvider(), OpenAIProvider()])


def _build_tools() -> list:
    return [
        KnowledgeSearchTool(), ReportSummaryTool(), BacktestResultTool(),
        AnalysisReportTool(), RiskSnapshotTool(), BacktestRunTool(),
    ]


def _get_orchestrator(catalog: CatalogDep, kb: KBServiceDep):
    from cquant.ai_advisor import AdvisorOrchestrator
    return AdvisorOrchestrator(
        provider=_build_provider(),
        agents=None,
        tools=_build_tools(),
        kb_service=kb,
        safety=SafetyPolicy(),
        catalog=catalog,
    )


OrchestratorDep = Annotated[object, Depends(_get_orchestrator)]


@router.post("/chat", response_model=AdvisorChatResponse)
async def advisor_chat(
    body: AdvisorChatRequest,
    orchestrator: OrchestratorDep,
) -> AdvisorChatResponse:
    session = await _get_or_create_session(body.session_id)
    try:
        response_text = await orchestrator.chat(body.message, session)
    except Exception as exc:
        logger.exception("Advisor chat failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Advisor error: {exc}")
    _trim_session(session)
    try:
        await asyncio.to_thread(_store.save, session)
    except Exception as exc:
        logger.warning("Failed to persist session %s: %s", session.session_id, exc)
    return AdvisorChatResponse(
        response=response_text,
        session_id=session.session_id,
        artifacts=_session_artifacts(session),
    )


@router.post("/report", response_model=AdvisorReportResponse)
async def advisor_report(
    body: AdvisorReportRequest,
    orchestrator: OrchestratorDep,
) -> AdvisorReportResponse:
    session = await _get_or_create_session(body.session_id)
    try:
        report_text = await orchestrator.generate_report(body.subject, session)
    except Exception as exc:
        logger.exception("Advisor report failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Report error: {exc}")
    _trim_session(session)
    try:
        await asyncio.to_thread(_store.save, session)
    except Exception as exc:
        logger.warning("Failed to persist session %s: %s", session.session_id, exc)
    return AdvisorReportResponse(
        report=report_text,
        session_id=session.session_id,
        artifacts=_session_artifacts(session),
    )


@router.get("/sessions")
async def list_sessions() -> dict:
    """Return all session IDs ordered by most-recently updated."""
    session_ids = await asyncio.to_thread(_store.list_sessions)
    return {"items": session_ids, "total": len(session_ids)}


@router.delete("/sessions/{session_id}")
async def clear_session(session_id: str) -> dict:
    await asyncio.to_thread(_store.delete, session_id)
    return {"status": "cleared", "session_id": session_id}


@router.get("/sessions/{session_id}")
async def get_advisor_session(session_id: str) -> dict:
    session = await asyncio.to_thread(_store.load, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    return {
        "session_id": session.session_id,
        "turn_count": len(session.history),
        "history": [
            {"role": t.role, "content": t.content[:500], "artifacts": t.artifacts}
            for t in session.history
        ],
    }


@router.get("/sessions/{session_id}/agents")
async def get_session_agents(session_id: str) -> dict:
    session = await asyncio.to_thread(_store.load, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    agent_roles = {"research", "risk", "debate", "execution", "report_writer"}
    items = [
        {"agent_role": t.role, "content": t.content, "artifacts": t.artifacts, "turn_index": i}
        for i, t in enumerate(session.history)
        if t.role in agent_roles
    ]
    return {"items": items, "session_id": session_id}


@router.get("/stream")
async def advisor_stream(
    message: str,
    catalog: CatalogDep,
    kb: KBServiceDep,
    session_id: str = "",
) -> StreamingResponse:
    """SSE stream: emit stage events as each Agent completes."""

    def emit(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    async def event_generator():
        try:
            session = await _get_or_create_session(session_id)
            yield emit("session_started", {"session_id": session.session_id, "message": message[:100]})

            provider = _build_provider()
            safety = SafetyPolicy()
            tool_ctx = ToolContext(
                kb_service=kb,
                catalog=catalog,
                safety=safety,
                vector_store=_get_vector_store(),
                session_id=session.session_id,
            )
            tool_registry = {t.name: t for t in _build_tools()}

            rag_ctx = await asyncio.to_thread(RAGContext().build, message, kb, 2)
            yield emit("rag_done", {"context_preview": rag_ctx[:200]})

            base_context = f"User message:\n{message}\n\nRAG context:\n{rag_ctx}"
            history = _recent_history(session)

            yield emit("agent_start", {"agent": "research"})
            research = ResearchAgent(
                provider, safety, tool_context=tool_ctx,
                tools=[tool_registry[n] for n in ("knowledge_search", "report_summary",
                       "backtest_result", "analysis_report") if n in tool_registry],
            )
            r_turn = await research.act(base_context, history)
            yield emit("agent_done", {"agent": "research", "content": r_turn.content, "artifacts": r_turn.artifacts})

            yield emit("agent_start", {"agent": "risk"})
            risk_agent = RiskAgent(
                provider, safety, tool_context=tool_ctx,
                tools=[tool_registry["risk_snapshot"]] if "risk_snapshot" in tool_registry else [],
            )
            risk_turn = await risk_agent.act(base_context, history + [r_turn])
            yield emit("agent_done", {"agent": "risk", "content": risk_turn.content, "artifacts": risk_turn.artifacts})

            yield emit("agent_start", {"agent": "debate"})
            debate = DebateAgent(provider, safety)
            debate_turn = await debate.act(_debate_ctx(message, [r_turn, risk_turn]), history + [r_turn, risk_turn])
            yield emit("agent_done", {"agent": "debate", "content": debate_turn.content, "artifacts": []})

            writer = ReportWriterAgent(provider, safety, max_tokens=3072)
            writer_turn = await writer.act(
                _writer_ctx(message, [r_turn, risk_turn], debate_turn, report_mode=False),
                history + [r_turn, risk_turn, debate_turn],
            )
            final = writer_turn.content.strip()
            if not final or "api key" in final.lower():
                final = _fallback_md("Advisor Response", [r_turn, risk_turn], debate_turn)

            yield emit("final_report", {"content": final})

            session.history.extend([r_turn, risk_turn, debate_turn, AgentTurn(role="assistant", content=final)])
            _trim_session(session)
            try:
                await asyncio.to_thread(_store.save, session)
            except Exception as exc:
                logger.warning("Failed to persist session %s: %s", session.session_id, exc)
            yield emit("done", {"session_id": session.session_id})

        except Exception as exc:
            logger.exception("SSE advisor stream failed: %s", exc)
            yield emit("error", {"message": str(exc)})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _trim_session(session: AdvisorSession) -> None:
    """Keep session history bounded to prevent unbounded memory growth."""
    if len(session.history) > _MAX_HISTORY_TURNS:
        # Keep the most recent turns; discard the oldest
        session.history = session.history[-_MAX_HISTORY_TURNS:]
