"""AI Advisor API schemas."""

from __future__ import annotations

from pydantic import BaseModel


class AdvisorChatRequest(BaseModel):
    message: str
    session_id: str = ""        # Provide to continue a previous session


class AdvisorChatResponse(BaseModel):
    response: str
    session_id: str
    artifacts: list[str] = []   # doc_ids and run_ids referenced


class AdvisorReportRequest(BaseModel):
    subject: str
    session_id: str = ""


class AdvisorReportResponse(BaseModel):
    report: str
    session_id: str
    artifacts: list[str] = []
