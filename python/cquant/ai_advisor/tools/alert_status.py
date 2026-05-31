"""Alert status query tool for AI Advisor."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from cquant.ai_advisor.tools.base import AdvisorTool, ToolContext, ToolResult

logger = logging.getLogger(__name__)


class AlertStatusTool(AdvisorTool):
    name = "alert_status"
    description = "Query current alert status and history. Returns active alert rules, recent triggers, and unread count."

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
                    parts.append("## Active Alert Rules\n")
                    for row in rules_df.to_dicts():
                        parts.append(f"- [{row['rule_type']}] {row['params_json']}")
                else:
                    parts.append("No active alert rules.")
            except Exception as exc:
                logger.warning("Alert rules query failed: %s", exc)
                parts.append(f"Failed to query alert rules: {exc}")

            # Query recent alerts
            try:
                alerts_df = catalog.query(
                    "SELECT rule_type, message, triggered_at, read "
                    "FROM meta_alert_history "
                    "ORDER BY triggered_at DESC LIMIT 10"
                )
                if not alerts_df.is_empty():
                    rows = alerts_df.to_dicts()
                    parts.append("\n## Recent Alerts\n")
                    for row in rows:
                        read_icon = "unread" if not row["read"] else "read"
                        parts.append(
                            f"- [{read_icon}] [{row['rule_type']}] {row['message']} "
                            f"({str(row['triggered_at'])[:16]})"
                        )

                    unread = sum(1 for r in rows if not r["read"])
                    if unread > 0:
                        parts.append(f"\n**Unread alerts: {unread}**")
            except Exception as exc:
                logger.warning("Alert history query failed: %s", exc)
                parts.append(f"Failed to query alert history: {exc}")

            return "\n".join(parts) if parts else "No alert data available."

        content = await asyncio.to_thread(_query)
        return ToolResult(success=True, content=content)
