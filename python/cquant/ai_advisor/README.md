# cquant.ai_advisor

Multi-agent research assistant for quantitative analysis.

## Architecture

```
User message
     │
     ▼
AdvisorOrchestrator.chat()
     │
     ├─ RAGContext.build()          # Retrieve relevant knowledge chunks
     │
     ├─ ResearchAgent.act()         # Always runs (core pipeline)
     │
     ├─ IntentRouter.classify()     # Table-driven routing (ROUTING_TABLE)
     │   ├─ risk keywords  → RiskAgent.act()
     │   └─ execution keywords → ExecutionAgent.act()
     │
     ├─ DebateAgent.act()           # Always runs — challenges findings
     │
     └─ ReportWriterAgent.act()     # Always runs — synthesizes response
```

Core agents (ResearchAgent, DebateAgent, ReportWriterAgent) always run.
Optional agents (RiskAgent, ExecutionAgent) are activated by keyword matching in
`IntentRouter.classify()` against `ROUTING_TABLE`.

## Module Structure

```
ai_advisor/
├── orchestrator.py    # AdvisorOrchestrator, AdvisorSession
├── router.py          # IntentRouter, ROUTING_TABLE, RoutingRule, AgentIntent
├── session_store.py   # SQLite-backed SessionStore (WAL mode)
├── agents/            # ResearchAgent, RiskAgent, ExecutionAgent, DebateAgent, ReportWriterAgent
├── tools/             # AdvisorTool implementations (read-only, safety-gated)
├── providers/         # LLMProvider, ClaudeProvider, OpenAIProvider, FallbackProvider
├── context/           # RAGContext (LanceDB vector store)
└── policies/          # SafetyPolicy — blocks live-trading instructions
```

## API Endpoints

```bash
# Chat (returns session_id for continuity)
POST /api/v1/advisor/chat
{"message": "Analyze factor momentum_20d", "session_id": ""}

# SSE stream (agent-by-agent events)
GET /api/v1/advisor/stream?message=...&session_id=...

# Session management
GET  /api/v1/advisor/sessions           # list all sessions
GET  /api/v1/advisor/sessions/{id}      # session history
DELETE /api/v1/advisor/sessions/{id}    # clear session
```

## Session Persistence

Sessions persist to SQLite (`data/advisor_sessions.db`).
`SessionStore` stores history as JSON and tracks `created_at` / `updated_at` timestamps.
Sessions survive API server restarts.

## Routing Table

`ROUTING_TABLE` in `router.py` is a list of `RoutingRule` objects.
Multiple rules can match; the union of their `agent_roles` is returned.

| Keywords (sample) | Agent Activated |
|-------------------|----------------|
| risk, drawdown, leverage, var, volatility, 风险, 回撤 | `RiskAgent` |
| run status, job status, backtest run, run_id, 执行, 任务状态 | `ExecutionAgent` |

## Extending with New Agent Types

Add a `RoutingRule` to `ROUTING_TABLE` in `router.py`:

```python
from cquant.ai_advisor.router import ROUTING_TABLE, RoutingRule

ROUTING_TABLE.append(RoutingRule(
    keywords=frozenset({"sector", "industry", "rotation"}),
    agent_roles=("sector_analyst",),
))
```

Then register the agent in `AdvisorOrchestrator._default_agents()`. No changes to the
orchestrator's core routing logic are required.

## Safety

- All tool calls pass through `SafetyPolicy.authorize()`.
- All responses pass through `SafetyPolicy.validate_response()`.
- `ExecutionAgent` is strictly offline — it cannot reach `broker_adapter`.
- Live-trading instructions are blocked at the policy level.
