# CLAUDE.MD - AI Assistant Guide

## Project Overview

This is a **Multi-Agent Market Research Platform** that analyzes stocks using 5 specialized AI agents working in parallel, followed by a solution agent that synthesizes their outputs into a final recommendation.

**Key Concept**: Real-time stock analysis powered by distributed AI agents, each with a specific domain of expertise (news, sentiment, fundamentals, market data, technical analysis).

## Architecture

```
User → FastAPI API → Orchestrator → [5 Agents Run in Parallel]
                                          ↓
                                    Solution Agent (Synthesizer)
                                          ↓
                                    Database (SQLite)
                                          ↓
                                    JSON Response
```

### Agent Roles

1. **News Agent** (`src/agents/news_agent.py`) - Fetches financial news with relevance filtering
2. **Sentiment Agent** (`src/agents/sentiment_agent.py`) - LLM-based sentiment analysis on news
3. **Fundamentals Agent** (`src/agents/fundamentals_agent.py`) - Company financials, health metrics, and LLM equity research
4. **Market Agent** (`src/agents/market_agent.py`) - Price trends and market conditions
5. **Technical Agent** (`src/agents/technical_agent.py`) - RSI, MACD, Bollinger Bands, SMA
6. **Solution Agent** (`src/agents/solution_agent.py`) - Synthesizes all outputs with chain-of-thought reasoning

### Data Source Priority (per agent)

All data-fetching agents follow a **primary → fallback** pattern:

| Agent | Primary Source (Alpha Vantage) | Fallback Source |
|-------|-------------------------------|-----------------|
| **Market Agent** | `GLOBAL_QUOTE` + `TIME_SERIES_DAILY` | yfinance |
| **Fundamentals Agent** | `COMPANY_OVERVIEW` + `EARNINGS` + `BALANCE_SHEET` + `CASH_FLOW` + `INCOME_STATEMENT` | yfinance + SEC EDGAR XBRL |
| **News Agent** | `NEWS_SENTIMENT` (includes ticker-specific relevance & sentiment scores) | NewsAPI |
| **Technical Agent** | `RSI` + `MACD` + `BBANDS` + `SMA` (×3 periods) + `TIME_SERIES_DAILY` | yfinance + local indicator calculation |
| **Sentiment Agent** | N/A (LLM-powered) | N/A |

Each agent inherits from `BaseAgent` which provides:
- `_av_request()` method for Alpha Vantage API calls with error handling, rate limiting, and response caching
- `_retry_fetch()` method for synchronous fallback calls with exponential backoff
- Shared `aiohttp` session (injected by orchestrator) for connection pooling
- Each agent adds `_fetch_av_*()` methods for specific AV endpoints
- Graceful fallback when `ALPHA_VANTAGE_API_KEY` is missing or AV returns incomplete data
- `data_source` tracking in analysis output (`"alpha_vantage"` or fallback source name)

## Core Files

### Entry Points
- **`run.py`** - Application startup script (runs FastAPI server)
- **`src/api.py`** - FastAPI application with REST and WebSocket endpoints

### Core Logic
- **`src/orchestrator.py`** - Coordinates agents (configurable pipeline), manages shared session/cache/rate limiter
- **`src/database.py`** - SQLite operations, caching, data persistence
- **`src/config.py`** - Environment variable management, configuration
- **`src/models.py`** - Pydantic models for data validation
- **`src/av_rate_limiter.py`** - Sliding-window rate limiter for AV API (per-minute + per-day)
- **`src/av_cache.py`** - In-memory TTL cache for AV API responses

### Agent Directory Structure
```
src/agents/
├── base_agent.py         # Abstract base class with _av_request(), _retry_fetch(), shared session support
├── news_agent.py         # News gathering (AV NEWS_SENTIMENT → NewsAPI)
├── sentiment_agent.py    # Sentiment analysis (LLM-powered)
├── fundamentals_agent.py # Company fundamentals (AV 5-endpoint → yfinance + SEC EDGAR)
├── market_agent.py       # Market data (AV GLOBAL_QUOTE + DAILY → yfinance)
├── technical_agent.py    # Technical indicators (AV RSI/MACD/BBANDS/SMA → yfinance + local calc)
└── solution_agent.py     # Final synthesis (LLM-powered)
```

### Frontend
```
frontend/
├── src/
│   ├── components/
│   │   ├── Dashboard.jsx       # Main layout and orchestration
│   │   ├── Recommendation.jsx  # SVG gauge with BUY/HOLD/SELL
│   │   ├── AgentStatus.jsx     # Real-time agent progress
│   │   ├── PriceChart.jsx      # Price history and indicators
│   │   ├── SentimentReport.jsx # Sentiment breakdown
│   │   ├── Summary.jsx         # Price targets, risks, opportunities
│   │   ├── NewsFeed.jsx        # News article list
│   │   └── Icons.jsx           # SVG icon components
│   ├── index.css               # Theme system (Tailwind v4 @theme + CSS custom properties)
│   └── App.jsx                 # Root component
├── tailwind.config.js          # Tailwind color configuration
└── package.json
```

**Frontend Theme**: Hero UI dark theme variant (zinc-based). Three color layers:
1. `tailwind.config.js` - Custom color values
2. `@theme` block in `index.css` - Semantic tokens (`--color-primary`, `--color-success`, etc.)
3. `:root` block in `index.css` - CSS custom properties for backgrounds, borders, glows

## Key Technologies

- **FastAPI** - REST API and WebSocket server
- **SQLite** - Database for caching and persistence
- **Anthropic Claude / OpenAI / xAI Grok** - LLM for sentiment, equity research, and synthesis
- **AsyncIO** - Parallel agent execution
- **aiohttp** - Async HTTP client for Alpha Vantage API calls
- **Pydantic** - Data validation and models
- **yfinance** - Stock market data (fallback source)
- **Alpha Vantage** - Primary market data API (15 endpoints used across 4 agents)
- **NewsAPI** - News aggregation (fallback for news agent)
- **React + Tailwind CSS v4** - Frontend UI with Hero UI dark theme
- **Vite** - Frontend build tool

## Environment Setup

### Required Environment Variables
```bash
ANTHROPIC_API_KEY=sk-...  # Primary LLM provider
# OR
OPENAI_API_KEY=sk-...     # Alternative LLM provider
# OR
GROK_API_KEY=...          # xAI Grok provider
```

### Recommended API Keys
```bash
ALPHA_VANTAGE_API_KEY=... # Primary data source for all data agents (strongly recommended)
```

### Optional API Keys
```bash
NEWSAPI_KEY=...           # Fallback news source (used when AV unavailable)
TWITTER_BEARER_TOKEN=...
```

### Configuration Options (`.env`)
- `LLM_PROVIDER` - "anthropic", "openai", or "xai" (default: anthropic)
- `LLM_MODEL` - Model name (default: claude-3-5-sonnet-20241022)
- `AGENT_TIMEOUT` - Timeout in seconds (default: 30)
- `AGENT_MAX_RETRIES` - Retry attempts per data fetch (default: 2)
- `NEWS_LOOKBACK_DAYS` - Days of news history (default: 7)
- `MAX_NEWS_ARTICLES` - Max articles to fetch (default: 20)
- `FUNDAMENTALS_LLM_ENABLED` - Enable LLM equity research in fundamentals agent (default: true)
- `PARALLEL_AGENTS` - Run data agents in parallel vs sequential (default: true)
- `AV_RATE_LIMIT_PER_MINUTE` - Max AV API requests per minute (default: 5)
- `AV_RATE_LIMIT_PER_DAY` - Max AV API requests per day (default: 25)
- `RSI_PERIOD` - RSI calculation period (default: 14)
- `MACD_FAST` / `MACD_SLOW` / `MACD_SIGNAL` - MACD parameters (default: 12/26/9)
- `BB_PERIOD` / `BB_STD` - Bollinger Bands parameters (default: 20/2)

## Running the Application

### Start Backend Server
```bash
# Activate virtual environment
source venv/bin/activate

# Start server
python run.py
```

Server runs on `http://localhost:8000`

### Start Frontend
```bash
cd frontend
npm install
npm run dev
```

Frontend runs on `http://localhost:5173`

### API Endpoints

**Analyze Stock**
```bash
POST /api/analyze/{ticker}?agents={comma-separated agent names}

# All agents (default)
curl -X POST http://localhost:8000/api/analyze/NVDA

# Specific agents only
curl -X POST "http://localhost:8000/api/analyze/NVDA?agents=market,technical"
```

**Get Latest Analysis**
```bash
GET /api/analysis/{ticker}/latest
curl http://localhost:8000/api/analysis/NVDA/latest
```

**Get History**
```bash
GET /api/analysis/{ticker}/history?limit=10
curl http://localhost:8000/api/analysis/NVDA/history
```

**WebSocket (Real-time Updates)**
```javascript
ws://localhost:8000/ws/analysis/{ticker}
```

**Health Check**
```bash
GET /health
curl http://localhost:8000/health
```

## Database Schema

**SQLite Database**: `market_research.db`

### Tables

1. **`analyses`** - Main analysis records
   - `id`, `ticker`, `timestamp`, `recommendation`, `score`, `confidence`, `reasoning`

2. **`agent_results`** - Individual agent outputs
   - `id`, `analysis_id`, `agent_name`, `data` (JSON), `duration_seconds`

3. **`price_history`** - Cached price data
   - `ticker`, `timestamp`, `open`, `high`, `low`, `close`, `volume`

4. **`news_cache`** - Cached news articles
   - `ticker`, `article_id`, `title`, `content`, `source`, `published_at`

5. **`sentiment_scores`** - Sentiment factor breakdown
   - `analysis_id`, `overall_score`, `news_sentiment`, `social_sentiment`

## Common Tasks

### Adding a New Agent

1. Create file in `src/agents/` (e.g., `new_agent.py`)
2. Inherit from `BaseAgent` in `src/agents/base_agent.py`
3. Implement `async def fetch_data(self) -> Dict[str, Any]`
4. Implement `async def analyze(self, raw_data: Dict[str, Any]) -> Dict[str, Any]`
5. Register agent in `src/orchestrator.py` `AGENT_REGISTRY` dict (include dependencies in `requires`)
6. Add agent name to `DEFAULT_AGENTS` list if it should run by default
7. Update database schema if needed

Example:
```python
from src.agents.base_agent import BaseAgent

class NewAgent(BaseAgent):
    async def fetch_data(self) -> Dict[str, Any]:
        # Fetch raw data — use self._av_request() for AV endpoints (inherited from BaseAgent)
        # Session, rate limiter, and cache are injected automatically by orchestrator
        return {"ticker": self.ticker, "data": {...}}

    async def analyze(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        # Analyze the fetched data
        return {"status": "success", "data": {...}}
```

### Adding Alpha Vantage to a New Agent

Follow the established pattern:
1. `_av_request()` and `AV_BASE_URL` are inherited from `BaseAgent` — no duplication needed
2. Add `_fetch_av_*()` methods for each AV endpoint that call `self._av_request(params)`
3. Update `fetch_data()` to try AV first, then fallback
4. Normalize AV data to match existing dict key formats
5. Add `data_source` field to track which source was used
6. The shared session, rate limiter, and cache are injected by the orchestrator automatically

### Modifying API Endpoints

Edit `src/api.py` - FastAPI application with all routes.

### Changing LLM Provider

Update `.env`:
```bash
LLM_PROVIDER=openai  # or anthropic or xai
OPENAI_API_KEY=sk-...
```

### Debugging Agent Failures

1. Check logs for specific agent errors
2. Review `agent_results` table in database
3. Check `data_source` field in results to see which source was used
4. Test agent individually:
```python
from src.agents.news_agent import NewsAgent
import asyncio

async def test():
    agent = NewsAgent()
    result = await agent.execute("AAPL")
    print(result)

asyncio.run(test())
```

### Debugging Alpha Vantage Issues

1. Check if `ALPHA_VANTAGE_API_KEY` is set in `.env`
2. AV free tier: 25 requests/day — agents will fallback automatically when rate-limited
3. Look for log messages: `"Alpha Vantage rate limited"`, `"Alpha Vantage API error"`, `"falling back to"`
4. Test AV directly:
```bash
curl "https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol=AAPL&apikey=YOUR_KEY"
```

## Important Patterns

### Orchestrator Pattern
The `Orchestrator` class coordinates all agents:
1. Creates a shared `aiohttp.ClientSession` for connection pooling
2. Resolves which agents to run (from `AGENT_REGISTRY`, with dependency enforcement)
3. Injects shared resources (session, rate limiter, cache) into each agent
4. Runs data agents in parallel (or sequential if `PARALLEL_AGENTS=false`) using `asyncio.gather()`
5. Runs sentiment agent (depends on news + market results)
6. Passes all results to Solution Agent for synthesis
7. Saves to database
8. Closes shared session in `finally` block

### Agent Base Class
All agents inherit from `BaseAgent` which provides:
- Error handling and timeout management
- Logging and result validation
- `execute()` method that orchestrates: `fetch_data()` → `analyze()` → return result dict
- `_av_request(params)` — shared AV API method with session pooling, rate limiting, and response caching
- `_retry_fetch(func)` — exponential backoff with jitter for synchronous fallback calls
- `_shared_session`, `_rate_limiter`, `_av_cache` — injected by orchestrator, used automatically by `_av_request()`

### Alpha Vantage Integration Pattern
All data agents follow the same pattern:
1. `fetch_data()` checks for `ALPHA_VANTAGE_API_KEY`
2. If present, fetches from AV endpoints concurrently via `asyncio.gather()`
3. Each `_fetch_av_*()` method calls `self._av_request(params)` — cache, rate limiter, and session are handled automatically
4. Handles exceptions per-endpoint (partial success is OK)
5. If AV provides sufficient data, returns immediately with `source: "alpha_vantage"`
6. If AV fails or is incomplete, falls through to fallback sources
7. Data is normalized to match existing dict key formats so `analyze()` methods work unchanged

### Configurable Agent Pipeline
The API accepts a `?agents=` query parameter to select which agents to run:
- Valid agents: `news`, `sentiment`, `fundamentals`, `market`, `technical`
- Dependencies are auto-resolved (e.g., `sentiment` auto-adds `news`)
- Solution agent always runs to synthesize available results
- The `AGENT_REGISTRY` in `orchestrator.py` maps agent names to classes and dependencies

### Data Flow
```
Ticker → Orchestrator → Agents (parallel) → Solution Agent → Database → API Response

Per Agent:
  fetch_data() → [AV API (primary)] → [yfinance/NewsAPI/SEC (fallback)] → analyze() → result
```

## Testing

### Test API
```bash
# Health check
curl http://localhost:8000/health

# Analyze stock
curl -X POST http://localhost:8000/api/analyze/AAPL
```

### Test Orchestrator Directly
```python
from src.orchestrator import Orchestrator
import asyncio

async def test():
    orchestrator = Orchestrator()
    result = await orchestrator.analyze_ticker("AAPL")
    print(result)

asyncio.run(test())
```

### Test Individual Agent
```python
from src.agents.market_agent import MarketAgent
import asyncio

async def test():
    agent = MarketAgent()
    result = await agent.execute("NVDA")
    print(result)

asyncio.run(test())
```

## Common Issues & Solutions

### Import Errors
```bash
# Add project root to PYTHONPATH
export PYTHONPATH=$PYTHONPATH:$(pwd)
```

### Database Locked
```bash
# Delete and recreate database
rm market_research.db
python run.py
```

### API Key Errors
- Check `.env` file exists
- Verify API keys are valid
- Ensure correct provider is set

### Agent Timeout
- Increase `AGENT_TIMEOUT` in `.env`
- Check network connectivity
- Verify external API keys are working

### Alpha Vantage Rate Limiting
- Built-in `AVRateLimiter` enforces per-minute and per-day limits (configurable via `AV_RATE_LIMIT_PER_MINUTE` / `AV_RATE_LIMIT_PER_DAY`)
- Free tier defaults: 5 requests/minute, 25 requests/day
- The rate limiter queues excess requests automatically; agents fall back when daily limit is exhausted
- The fundamentals agent makes 5 concurrent AV requests per analysis
- The technical agent makes 7 concurrent AV requests per analysis
- Total per full analysis: ~15 AV requests (queued through the shared rate limiter)
- Check logs for `"Rate limiter: waiting"` or `"AV daily limit reached"` messages
- `AVCache` deduplicates repeated requests for the same endpoint+ticker within TTL windows

### Alpha Vantage Returns No Data
- Verify the ticker symbol is valid on Alpha Vantage (some international tickers differ)
- Check for `"Error Message"` in AV response logs
- Agents will automatically use fallback sources

## Frontend Integration

The frontend is in `frontend/` directory (React + Vite + Tailwind CSS v4).

**Theme**: Hero UI dark variant (zinc-based palette)
- Primary: `#006fee` (blue)
- Success: `#17c964` (green)
- Danger: `#f31260` (pink-red)
- Warning: `#f5a524` (amber)
- Background: `#000000` (pure black)
- Content surfaces: `#18181b` → `#27272a` → `#3f3f46` → `#52525b` (zinc scale)

**Backend provides**:
- REST API for historical data
- WebSocket for real-time updates
- JSON responses with full analysis

**Frontend connects via**:
- Axios for HTTP requests
- WebSocket for live progress
- `http://localhost:8000` as API base URL

## Development Workflow

1. **Make changes** to agents or orchestrator
2. **Test locally** with curl or Python
3. **Check database** to verify data persistence
4. **Run API tests** to ensure endpoints work
5. **Test WebSocket** for real-time updates
6. **Build frontend** to verify no build errors: `cd frontend && npm run build`

## Code Style

- **Async/await** for all I/O operations
- **Type hints** on all functions
- **Pydantic models** for data validation
- **Error handling** with try/except in agents
- **Logging** for debugging
- **aiohttp** for all external HTTP requests in agents
- **`asyncio.gather()`** for concurrent API calls within agents

## Security Notes

- API keys stored in `.env` (not committed to git)
- `.env.example` provided as template
- Database is local SQLite (not exposed)
- CORS configured for frontend access
- Alpha Vantage API key passed as query parameter (standard for AV)

## Performance Considerations

- Agents run in **parallel** for speed (configurable via `PARALLEL_AGENTS`)
- Within each agent, AV endpoints are fetched **concurrently** via `asyncio.gather()`
- **Shared `aiohttp` session** with connection pooling across all agents per analysis
- **AV response caching** deduplicates repeated requests (in-memory TTL cache shared across agents)
- **AV rate limiter** queues requests to stay within API limits instead of getting rejected
- Database **caching** reduces API calls
- News and price data **cached** with TTL
- Agent **timeout** prevents hanging
- WebSocket for **real-time** updates (no polling)
- Alpha Vantage as primary reduces yfinance rate-limit issues
- `return_exceptions=True` in `asyncio.gather()` prevents one failed endpoint from blocking others

## Next Steps for AI Assistants

When working with this codebase:

1. **Read relevant files** before making changes
2. **Test changes** with individual agent tests first
3. **Check database schema** if modifying data structures
4. **Update `.env.example`** if adding new config options
5. **Maintain async patterns** throughout
6. **Preserve error handling** in all agents
7. **Use type hints** for clarity
8. **Follow existing agent patterns** when adding new ones
9. **Follow the AV integration pattern** when adding new data sources
10. **Keep fallback behavior** — never remove existing data sources

## File Reading Priority

For most tasks, read these files first:
1. `src/orchestrator.py` - Understand workflow
2. `src/agents/base_agent.py` - Understand agent interface
3. Specific agent file you're modifying
4. `src/models.py` - Understand data structures
5. `src/config.py` - Understand configuration options
6. `src/database.py` - Understand persistence

## Quick Reference Commands

```bash
# Start backend server
source venv/bin/activate
python run.py

# Start frontend
cd frontend && npm run dev

# Build frontend
cd frontend && npm run build

# Test API
curl http://localhost:8000/health
curl -X POST http://localhost:8000/api/analyze/AAPL

# Check database
sqlite3 market_research.db "SELECT * FROM analyses ORDER BY timestamp DESC LIMIT 1;"

# Install backend dependencies
pip install -r requirements.txt

# Install frontend dependencies
cd frontend && npm install
```

## Response Format Example

```json
{
  "success": true,
  "ticker": "NVDA",
  "analysis_id": 1,
  "analysis": {
    "recommendation": "BUY|HOLD|SELL",
    "score": "-100 to 100",
    "confidence": "0.0 to 1.0",
    "reasoning": "Detailed explanation...",
    "risks": ["Risk 1", "Risk 2"],
    "opportunities": ["Opp 1", "Opp 2"],
    "price_targets": {
      "entry": 150.00,
      "target": 175.00,
      "stop_loss": 140.00
    },
    "position_size": "SMALL|MEDIUM|LARGE",
    "time_horizon": "SHORT_TERM|MEDIUM_TERM|LONG_TERM"
  },
  "agent_results": {
    "news": {"data_source": "alpha_vantage", "...": "..."},
    "sentiment": {"...": "..."},
    "fundamentals": {"data_source": "alpha_vantage", "...": "..."},
    "market": {"data_source": "alpha_vantage", "...": "..."},
    "technical": {"data_source": "alpha_vantage", "...": "..."}
  },
  "duration_seconds": 32.5
}
```

## License

MIT License - See project README.md for details.
