# AGENTS.md - Project Guide for Coding Agents

## Mission
Build and maintain a multi-agent stock market analysis platform with a FastAPI backend, async agent orchestration, and a React frontend with SSE progress streaming.

## Quickstart
Backend:
```bash
source venv/bin/activate
python run.py
```
Frontend:
```bash
cd frontend
npm install
npm run dev
```

## Architecture
Request flow:
```
Client → FastAPI → Orchestrator → [Agents in parallel] → Solution Agent → SQLite → Response/SSE
```

Core files:
- `src/api.py` FastAPI app (REST + SSE)
- `src/orchestrator.py` agent coordination, shared session/cache/limiter
- `src/database.py` SQLite persistence and caches
- `src/config.py` env-driven configuration
- `src/agents/*` data agents + solution agent

Agent map:
- News: `src/agents/news_agent.py`
- Sentiment: `src/agents/sentiment_agent.py`
- Fundamentals: `src/agents/fundamentals_agent.py`
- Market: `src/agents/market_agent.py`
- Technical: `src/agents/technical_agent.py`
- Macro: `src/agents/macro_agent.py`
- Synthesis: `src/agents/solution_agent.py`

## Data Sources
Primary: Alpha Vantage (most data agents)
Fallbacks: yfinance, NewsAPI, SEC EDGAR (fundamentals/news)
LLMs: Anthropic / OpenAI / xAI (sentiment, fundamentals, synthesis)

Alpha Vantage shared infra:
- Rate limiter: `src/av_rate_limiter.py`
- TTL cache + in-flight request coalescing: `src/av_cache.py`

## Configuration
Environment variables loaded via `.env`.
Key settings (see `src/config.py`):
- `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` or `GROK_API_KEY`
- `ALPHA_VANTAGE_API_KEY`
- `NEWS_API_KEY`
- `LLM_PROVIDER`, `LLM_MODEL`, `AGENT_TIMEOUT`, `AGENT_MAX_RETRIES`

## Frontend
- Hooks: `frontend/src/hooks/useAnalysis.js`, `frontend/src/hooks/useSSE.js`
- API client: `frontend/src/utils/api.js`
- Main layout: `frontend/src/components/Dashboard.jsx`

## Development Notes
- Prefer async-safe I/O. Any blocking SDKs (LLM clients, yfinance) should be isolated via executors if they become a bottleneck.
- Preserve `data_source` in agent outputs for provenance.
- Keep SSE event types (`progress`, `result`, `error`) stable for the frontend.
- SQLite schema is defined in `src/database.py`; keep migrations manual and explicit.

## Tests
No formal test suite is wired up yet. `test_api.py` is a manual smoke test.
