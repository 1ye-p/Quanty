# cquant.mcp_server

FastMCP server exposing cQuant DuckDB data and AKShare market data as MCP tools.

## Overview

This module provides a [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server
that allows AI agents (Claude, etc.) to query cQuant data without direct Python imports.
The server is registered as `"cQuant Data Tools"` via `FastMCP`.

## Usage

```bash
# Start the MCP server (stdio transport)
python -m cquant.mcp_server

# Set database path via environment variable
CQUANT_DB=/path/to/cquant.duckdb python -m cquant.mcp_server
```

Default DB path: `~/.cquant/data/cquant.duckdb` (override with `CQUANT_DB` env var).
All DuckDB connections are opened **read-only**.

## Available Tools

| Tool | Description | Key Args |
|------|-------------|----------|
| `query_backtest_result` | Returns summary stats for a completed backtest run | `run_id: str` |
| `query_factor_ic` | Returns IC analysis summary for a factor | `factor_name: str`, `feature_set_version: str = ""` |
| `query_risk_snapshot` | Returns latest risk snapshot for a run or strategy | `run_id: str = ""`, `strategy_id: str = ""` |
| `get_stock_history` | Returns A-share OHLCV history (AKShare) | `symbol: str`, `start_date: str`, `end_date: str`, `period: str = "daily"`, `adjust: str = "hfq"` |

All tools return JSON strings. Errors return `{"error": "..."}` — never raise exceptions.

### `get_stock_history` notes

- `symbol`: 6-digit A-share code without market prefix (e.g. `"600036"`)
- `start_date` / `end_date`: format `YYYYMMDD` (e.g. `"20240101"`)
- `period`: `"daily"` / `"weekly"` / `"monthly"` (default `"daily"`)
- `adjust`: `"hfq"` (back-adjusted) / `"qfq"` (forward-adjusted) / `""` (unadjusted), default `"hfq"`

## Module Structure

```
mcp_server/
├── server.py          # FastMCP instance ("cQuant Data Tools") + @mcp.tool() definitions
├── __main__.py        # Entry point: mcp.run()
└── tools/
    └── market_data.py # AKShare get_stock_history() implementation
```

## Integration with Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "cquant": {
      "command": "conda",
      "args": ["run", "-n", "cQuanty", "python", "-m", "cquant.mcp_server"],
      "env": { "CQUANT_DB": "/path/to/cquant.duckdb" }
    }
  }
}
```

## Dependency Note

`fastmcp >= 3.x` upgrades `starlette` to `>=1.0.0`, which conflicts with `fastapi 0.115.x`.
Pin `starlette<1.0.0` in your environment to keep both working:
```bash
pip install "starlette<1.0.0"
```
