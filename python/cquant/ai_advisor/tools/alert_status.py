"""Alert status query tool for AI Advisor."""

from __future__ import annotations

import asyncio
from typing import Any

from cquant.ai_advisor.tools.base import AdvisorTool, ToolContext, ToolResult


class AlertStatusTool(AdvisorTool):
    name = "alert_status"
    description = "查询当前告警状态和历史记录。返回活跃告警规则、最近触发的告警、未读告警数量。"

    async def invoke(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        def _query():
            catalog = ctx.catalog
            parts = []

            # Query active rules
            try:
                rules_df = catalog.query(
                    "SELECT rule_id, rule_type, params_json, enabled FROM meta_alert_rules "
                    "WHERE enabled = TRUE"
                )
                if not rules_df.is_empty():
                    parts.append("## 活跃告警规则\n")
                    for row in rules_df.to_dicts():
                        parts.append(f"- [{row['rule_type']}] {row['params_json']}")
                else:
                    parts.append("当前无活跃告警规则。")
            except Exception:
                parts.append("无法查询告警规则（表可能不存在）。")

            # Query recent alerts
            try:
                alerts_df = catalog.query(
                    "SELECT rule_type, message, triggered_at, read "
                    "FROM meta_alert_history "
                    "ORDER BY triggered_at DESC LIMIT 10"
                )
                if not alerts_df.is_empty():
                    parts.append("\n## 最近告警记录\n")
                    for row in alerts_df.to_dicts():
                        read_icon = "⬜" if not row["read"] else "✅"
                        parts.append(
                            f"- {read_icon} [{row['rule_type']}] {row['message']} "
                            f"({str(row['triggered_at'])[:16]})"
                        )

                    unread = sum(1 for r in alerts_df.to_dicts() if not r["read"])
                    if unread > 0:
                        parts.append(f"\n**未读告警：{unread} 条**")
            except Exception:
                parts.append("无法查询告警历史。")

            return "\n".join(parts) if parts else "当前无告警数据。"

        content = await asyncio.to_thread(_query)
        return ToolResult(success=True, content=content)
