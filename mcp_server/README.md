# Market Research MCP Server

MCP server exposing the Multi-Agent Market Research Platform to AI agents.

## Prerequisites

The FastAPI backend must be running:

```bash
source venv/bin/activate && python run.py  # Starts on http://localhost:8000
```

## Setup

### Claude Code

Add to project settings (`.claude/settings.json`):

```json
{
  "mcpServers": {
    "market-research": {
      "command": "python",
      "args": ["mcp_server/server.py"],
      "cwd": "/path/to/multi-agent-market-research",
      "env": {"PYTHONPATH": "/path/to/multi-agent-market-research"}
    }
  }
}
```

### OpenClaw (via MCP Bridge)

Add to `openclaw.json`:

```json
{
  "plugins": {
    "entries": {
      "@aiwerk/openclaw-mcp-bridge": {
        "config": {
          "servers": {
            "market-research": {
              "transport": "stdio",
              "command": "python",
              "args": ["/path/to/multi-agent-market-research/mcp_server/server.py"]
            }
          }
        }
      }
    }
  }
}
```

### Custom Backend URL

```bash
MARKET_RESEARCH_URL=http://localhost:9000 python mcp_server/server.py
```

## Available Tools (43 total)

### Layer 1: Analysis (6 tools)
- `get_ticker_summary` — Quick analysis summary (~200 tokens)
- `get_ticker_analysis` — Detailed analysis with section filtering
- `get_ticker_changes` — Delta between recent analyses
- `get_ticker_inflections` — KPI inflection events
- `get_council_results` — Investor council analysis
- `compare_tickers` — Side-by-side comparison (max 5)

### Layer 2: Actions (15 tools)
- `run_analysis` — Trigger fresh analysis (15-45s)
- `run_council` — Trigger council analysis
- Watchlist CRUD: `list_watchlists`, `create_watchlist`, `update_watchlist`, `delete_watchlist`, `add_ticker_to_watchlist`, `remove_ticker_from_watchlist`
- Alert CRUD: `list_alerts`, `create_alert`, `delete_alert`
- Portfolio: `get_portfolio`, `add_holding`, `remove_holding`

### Layer 3: Raw Data (22 tools)
- Market: `get_stock_quote`, `get_price_history`, `get_company_profile`, `get_financials`, `get_earnings_history`, `get_earnings_transcript`, `get_analyst_estimates`, `get_price_targets`, `get_insider_trading`, `get_peers`, `get_financial_ratios`, `get_revenue_segments`, `get_dcf_valuation`, `get_management`, `get_financial_growth`, `get_share_statistics`, `get_technical_indicators`, `get_options_chain`, `get_news`
- Macro: `get_macro_indicators`
- SEC: `get_sec_filings`, `get_sec_filing_section`
