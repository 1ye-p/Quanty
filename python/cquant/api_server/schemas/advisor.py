"""AI Advisor API schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AdvisorChatRequest(BaseModel):
    message: str = Field(
        ...,
        description="用户问题或研究请求",
        json_schema_extra={"example": "分析动量因子在 2024 年的表现"},
    )
    session_id: str = Field(
        default="",
        description="会话 ID（首次传空字符串）",
        json_schema_extra={"example": ""},
    )


class AdvisorChatResponse(BaseModel):
    response: str
    session_id: str
    artifacts: list[str] = []   # doc_ids and run_ids referenced


class AdvisorReportRequest(BaseModel):
    subject: str = Field(
        ...,
        description="报告主题",
        json_schema_extra={"example": "沪深300成分股 2024 年价值因子轮动报告"},
    )
    session_id: str = Field(default="", description="会话 ID")


class AdvisorReportResponse(BaseModel):
    report: str
    session_id: str
    artifacts: list[str] = []
