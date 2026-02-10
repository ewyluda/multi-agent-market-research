# Multi-Agent Market Research Platform

Real-time AI-powered stock market analysis using specialized agents.

## Overview

This application uses 6 specialized AI agents to analyze stocks from different perspectives:
- **News Agent**: Gathers financial news with ticker-specific relevance filtering
- **Sentiment Agent**: LLM-based sentiment analysis on news articles (enriched with AV per-article sentiment scores)
- **Fundamentals Agent**: Company financial metrics, health scoring, and LLM equity research
- **Market Agent**: Price trends, moving averages, and market conditions
- **Technical Agent**: RSI, MACD, Bollinger Bands, SMA analysis
- **Macro Agent**: US macroeconomic indicators (fed funds rate, CPI, GDP, treasury yields, unemployment, inflation)

A **Solution Agent** synthesizes all outputs using chain-of-thought reasoning to provide a final BUY/HOLD/SELL recommendation with price targets and risk assessment.

## Features

- Real-time multi-agent analysis with parallel execution
- **Configurable agent pipeline** — select which agents to run per request via `?agents=` parameter
- **Alpha Vantage as primary data source** across all data agents (22 endpoints)
- **AV connection pooling** — shared `aiohttp` session across all agents per analysis
- **AV rate limiting** — centralized sliding-window limiter (5/min, 25/day configurable)
- **AV response caching** — in-memory TTL cache deduplicates repeated requests
- Graceful fallback to yfinance, NewsAPI, and SEC EDGAR when AV is unavailable
- `data_source` tracking in every agent output for transparency
- LLM-powered equity research (Anthropic Claude / OpenAI / xAI Grok)
- Server-Sent Events (SSE) for live progress streaming
- Historical analysis tracking with SQLite
- RESTful API built with FastAPI
- React frontend with Hero UI dark theme, structured executive overview, and macro sidebar widget
- **Analysis history dashboard** — browse past analyses, score trend charts, filter by recommendation, paginated tables
- **Multi-ticker watchlists** — create watchlists, batch-analyze all tickers via SSE, side-by-side comparison table
- **Test suite** — 80 pytest tests covering agents, orchestrator, API, database, AV cache, and rate limiter
- **Docker support** — Dockerfiles + docker-compose for one-command deployment (backend + nginx frontend)

## Architecture

```
User Request → FastAPI → Orchestrator → [6 Agents in Parallel]
                                              ↓
                                        Solution Agent
                                              ↓
                                        Final Analysis → Database
                                              ↓
                                        Response to User
```

### Data Source Priority

Each data agent tries Alpha Vantage first and falls back gracefully:

| Agent | Primary (Alpha Vantage) | Fallback |
|-------|------------------------|----------|
| Market | `GLOBAL_QUOTE` + `TIME_SERIES_DAILY` | yfinance |
| Fundamentals | `COMPANY_OVERVIEW` + `EARNINGS` + `BALANCE_SHEET` + `CASH_FLOW` + `INCOME_STATEMENT` | yfinance + SEC EDGAR |
| News | `NEWS_SENTIMENT` | NewsAPI |
| Technical | `RSI` + `MACD` + `BBANDS` + `SMA` (x3) + `TIME_SERIES_DAILY` | yfinance + local calculation |
| Macro | `FEDERAL_FUNDS_RATE` + `CPI` + `REAL_GDP` + `TREASURY_YIELD` (10Y & 2Y) + `UNEMPLOYMENT` + `INFLATION` | None |

## Setup

### Prerequisites

- Python 3.9+
- Node.js 18+ (for frontend)
- API Keys:
  - **Required**: Anthropic API key (or OpenAI / xAI Grok API key)
  - **Recommended**: Alpha Vantage API key (primary data source for all agents)
  - **Optional**: NewsAPI (fallback news source)

### Installation

1. **Clone the repository**
   ```bash
   cd multi-agent-market-research
   ```

2. **Create and activate virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install backend dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Install frontend dependencies**
   ```bash
   cd frontend
   npm install
   cd ..
   ```

5. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env and add your API keys
   ```

   **Minimum required:**
   ```
   ANTHROPIC_API_KEY=your_key_here
   ```

   **Recommended (enables Alpha Vantage as primary data source):**
   ```
   ALPHA_VANTAGE_API_KEY=your_key_here
   ```

### Running the Backend

```bash
source venv/bin/activate
python run.py
```

The API will be available at `http://localhost:8000`

### Running the Frontend

```bash
cd frontend
npm run dev
```

The UI will be available at `http://localhost:5173`

## API Endpoints

### Trigger Analysis
```bash
POST /api/analyze/{ticker}?agents={comma-separated agent names}

# Run all agents (default)
curl -X POST http://localhost:8000/api/analyze/NVDA

# Run only specific agents
curl -X POST "http://localhost:8000/api/analyze/NVDA?agents=market,technical"

# Sentiment auto-adds news (dependency)
curl -X POST "http://localhost:8000/api/analyze/NVDA?agents=sentiment"
```

Valid agent names: `news`, `sentiment`, `fundamentals`, `market`, `technical`, `macro`. The solution agent always runs.

### Get Latest Analysis
```bash
GET /api/analysis/{ticker}/latest

Example:
curl http://localhost:8000/api/analysis/NVDA/latest
```

### Get Analysis History
```bash
GET /api/analysis/{ticker}/history?limit=10

Example:
curl http://localhost:8000/api/analysis/NVDA/history
```

### Get Detailed History (Paginated + Filtered)
```bash
GET /api/analysis/{ticker}/history/detailed?limit=20&offset=0&recommendation=BUY

Example:
curl "http://localhost:8000/api/analysis/NVDA/history/detailed?recommendation=BUY"
```

### List All Analyzed Tickers
```bash
GET /api/analysis/tickers

Example:
curl http://localhost:8000/api/analysis/tickers
```

### Delete an Analysis
```bash
DELETE /api/analysis/{analysis_id}

Example:
curl -X DELETE http://localhost:8000/api/analysis/5
```

### Watchlists
```bash
# Create a watchlist
curl -X POST http://localhost:8000/api/watchlists -H "Content-Type: application/json" -d '{"name":"Tech"}'

# List all watchlists
curl http://localhost:8000/api/watchlists

# Get watchlist with latest analyses
curl http://localhost:8000/api/watchlists/1

# Add ticker to watchlist
curl -X POST http://localhost:8000/api/watchlists/1/tickers -H "Content-Type: application/json" -d '{"ticker":"NVDA"}'

# Remove ticker from watchlist
curl -X DELETE http://localhost:8000/api/watchlists/1/tickers/NVDA

# Batch analyze all tickers (SSE stream)
curl -N -X POST http://localhost:8000/api/watchlists/1/analyze
```

### SSE Real-time Streaming
```bash
GET /api/analyze/{ticker}/stream?agents={optional}

# Stream analysis with real-time progress
curl -N http://localhost:8000/api/analyze/NVDA/stream
```

Events streamed:
- `progress` — agent status updates (`{stage, progress, ticker, timestamp}`)
- `result` — final analysis (same shape as POST response)
- `error` — on failure (`{error, ticker}`)

```javascript
const es = new EventSource('http://localhost:8000/api/analyze/NVDA/stream');
es.addEventListener('progress', (e) => console.log(JSON.parse(e.data)));
es.addEventListener('result', (e) => { console.log(JSON.parse(e.data)); es.close(); });
```

### Export Analysis as CSV
```bash
GET /api/analysis/{ticker}/export/csv?analysis_id={optional_id}

# Export latest analysis
curl -O http://localhost:8000/api/analysis/NVDA/export/csv

# Export specific analysis by ID
curl -O http://localhost:8000/api/analysis/NVDA/export/csv?analysis_id=3
```

### Health Check
```bash
GET /health

Example:
curl http://localhost:8000/health
```

## API Response Format

### Analysis Response

```json
{
  "success": true,
  "ticker": "NVDA",
  "analysis_id": 1,
  "analysis": {
    "recommendation": "HOLD",
    "score": -15,
    "confidence": 0.75,
    "reasoning": "Mixed signals across agents...",
    "risks": [
      "Valuation concerns",
      "Market volatility"
    ],
    "opportunities": [
      "Strong fundamentals",
      "Revenue growth momentum"
    ],
    "price_targets": {
      "entry": 130.00,
      "target": 155.00,
      "stop_loss": 115.00
    },
    "position_size": "MEDIUM",
    "time_horizon": "MEDIUM_TERM"
  },
  "agent_results": {
    "news": { "data_source": "alpha_vantage", "..." : "..." },
    "sentiment": { "..." : "..." },
    "fundamentals": { "data_source": "alpha_vantage", "..." : "..." },
    "market": { "data_source": "alpha_vantage", "..." : "..." },
    "technical": { "data_source": "alpha_vantage", "..." : "..." },
    "macro": { "data_source": "alpha_vantage", "..." : "..." }
  },
  "duration_seconds": 32.5
}
```

## Configuration

All configuration is in `.env` file. Key settings:

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_PROVIDER` | LLM provider (`anthropic` / `openai` / `xai`) | `anthropic` |
| `LLM_MODEL` | Model to use | `claude-3-5-sonnet-20241022` |
| `ALPHA_VANTAGE_API_KEY` | Alpha Vantage API key (primary data source) | _(empty)_ |
| `NEWS_API_KEY` | NewsAPI key (fallback news source) | _(empty)_ |
| `AGENT_TIMEOUT` | Agent execution timeout (seconds) | `30` |
| `AGENT_MAX_RETRIES` | Retry attempts per data fetch | `2` |
| `NEWS_LOOKBACK_DAYS` | Days of news to fetch | `7` |
| `MAX_NEWS_ARTICLES` | Max articles per request | `20` |
| `FUNDAMENTALS_LLM_ENABLED` | Enable LLM equity research | `true` |
| `PARALLEL_AGENTS` | Run agents in parallel | `true` |
| `AV_RATE_LIMIT_PER_MINUTE` | AV requests allowed per minute | `5` |
| `AV_RATE_LIMIT_PER_DAY` | AV requests allowed per day | `25` |
| `RSI_PERIOD` | RSI calculation period | `14` |
| `MACD_FAST` / `MACD_SLOW` / `MACD_SIGNAL` | MACD parameters | `12` / `26` / `9` |
| `BB_PERIOD` / `BB_STD` | Bollinger Bands parameters | `20` / `2` |
| `MACRO_AGENT_ENABLED` | Enable/disable macroeconomic agent | `true` |

See `.env.example` for all available options.

## Testing

### Run Test Suite

```bash
source venv/bin/activate

# Run all 80 tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=src --cov-report=term-missing

# Run specific test file
python -m pytest tests/test_database.py -v

# Run only fast tests (skip slow/integration)
python -m pytest tests/ -v -m "not slow"
```

Test suite covers:
- **AV Cache** (14 tests) — TTL expiry, in-flight coalescing, key generation, stats
- **AV Rate Limiter** (7 tests) — daily limits, concurrent serialization, exhaustion
- **Database** (16 tests) — all CRUD operations, cross-ticker isolation, indexing
- **Base Agent** (18 tests) — ticker validation, execute flow, AV requests, retry logic
- **Orchestrator** (11 tests) — agent resolution, dependencies, parallel execution, progress callbacks
- **API** (14 tests) — all endpoints, error handling, SSE streaming

### Manual Testing

```bash
# Test via API
curl -X POST http://localhost:8000/api/analyze/AAPL

# Test individual agent
python -c "
from src.agents.market_agent import MarketAgent
import asyncio
async def test():
    agent = MarketAgent()
    result = await agent.execute('NVDA')
    print(result)
asyncio.run(test())
"

# Health check
curl http://localhost:8000/health
```

## Database

The application uses SQLite by default. Database file: `market_research.db`

### Tables
- `analyses` - Main analysis records
- `agent_results` - Individual agent outputs (includes `data_source` in JSON)
- `price_history` - Cached price data
- `news_cache` - Cached news articles
- `sentiment_scores` - Sentiment factor breakdown
- `watchlists` - User-created watchlists
- `watchlist_tickers` - Many-to-many ticker associations for watchlists

### Query Examples

```bash
sqlite3 market_research.db

# Get latest analysis
SELECT * FROM analyses WHERE ticker='NVDA' ORDER BY timestamp DESC LIMIT 1;

# Get all agent results for an analysis
SELECT * FROM agent_results WHERE analysis_id = 1;

# Get sentiment breakdown
SELECT * FROM sentiment_scores WHERE analysis_id = 1;
```

## Project Structure

```
multi-agent-market-research/
├── src/
│   ├── __init__.py
│   ├── api.py                 # FastAPI application (REST + SSE endpoints)
│   ├── config.py              # Configuration management
│   ├── database.py            # Database operations (SQLite)
│   ├── models.py              # Pydantic models
│   ├── orchestrator.py        # Agent coordination with configurable pipeline
│   ├── av_cache.py            # AV response cache (in-memory TTL)
│   ├── av_rate_limiter.py     # AV API rate limiter (sliding window)
│   └── agents/
│       ├── __init__.py
│       ├── base_agent.py          # Base agent class (ABC) with shared AV infrastructure
│       ├── news_agent.py          # News gathering (AV NEWS_SENTIMENT → NewsAPI)
│       ├── sentiment_agent.py     # Sentiment analysis (LLM + AV per-article scores)
│       ├── fundamentals_agent.py  # Company fundamentals (AV 5-endpoint → yfinance + SEC EDGAR)
│       ├── market_agent.py        # Market data (AV GLOBAL_QUOTE + DAILY → yfinance)
│       ├── technical_agent.py     # Technical indicators (AV RSI/MACD/BBANDS/SMA → yfinance + local)
│       ├── macro_agent.py         # US macroeconomic indicators (AV 7-endpoint, no fallback)
│       └── solution_agent.py      # Final synthesis (LLM chain-of-thought)
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Dashboard.jsx         # Main layout (view mode toggle: Analysis/History/Watchlist)
│   │   │   ├── Recommendation.jsx    # SVG gauge with agent consensus strip
│   │   │   ├── AgentStatus.jsx       # Real-time agent progress pipeline
│   │   │   ├── PriceChart.jsx        # Price history, indicators, data source badges
│   │   │   ├── SentimentReport.jsx   # Sentiment breakdown with factor bars
│   │   │   ├── Summary.jsx           # Verdict banner, sectioned analysis, price targets
│   │   │   ├── MacroSnapshot.jsx     # Macro indicators sidebar widget
│   │   │   ├── NewsFeed.jsx          # News article list
│   │   │   ├── HistoryDashboard.jsx  # Analysis history browser with trend charts
│   │   │   ├── WatchlistPanel.jsx    # Watchlist management + comparison table
│   │   │   └── Icons.jsx             # SVG icon components (26+ icons)
│   │   ├── context/
│   │   │   └── AnalysisContext.jsx    # React context for analysis state
│   │   ├── hooks/
│   │   │   ├── useAnalysis.js        # Analysis data fetching hook
│   │   │   ├── useHistory.js         # History state management hook
│   │   │   └── useSSE.js             # SSE streaming hook
│   │   ├── utils/
│   │   │   └── api.js                # API client (analysis + watchlist endpoints)
│   │   ├── assets/
│   │   │   └── react.svg
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   └── index.css                 # Hero UI dark theme (Tailwind v4)
│   ├── Dockerfile                    # Production frontend (nginx)
│   ├── Dockerfile.dev                # Development frontend (Vite hot-reload)
│   ├── nginx.conf                    # Nginx reverse proxy config
│   ├── index.html
│   ├── vite.config.js
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── eslint.config.js
│   └── package.json
├── tests/
│   ├── conftest.py                   # Shared fixtures (DB, cache, rate limiter, mock data)
│   ├── test_av_cache.py              # AV cache tests (14 tests)
│   ├── test_av_rate_limiter.py       # AV rate limiter tests (7 tests)
│   ├── test_database.py              # Database CRUD tests (16 tests)
│   ├── test_orchestrator.py          # Orchestrator tests (11 tests)
│   ├── test_api.py                   # API endpoint tests (14 tests)
│   └── test_agents/
│       └── test_base_agent.py        # Base agent tests (18 tests)
├── Dockerfile                        # Backend Docker image
├── docker-compose.yml                # Production compose
├── docker-compose.dev.yml            # Development compose (hot-reload)
├── .dockerignore
├── pyproject.toml                    # pytest configuration
├── requirements.txt                  # Python dependencies
├── .env.example                      # Environment template
├── run.py                            # Startup script
├── CLAUDE.md                         # AI assistant guide
└── README.md                         # This file
```

## Frontend

The frontend is a React application with a Hero UI-inspired dark theme built on Tailwind CSS v4.

### Layout
- **2-7-3 grid** layout: narrow agent pipeline (left), wide content area (center), recommendation + macro sidebar (right)
- **No tabs** — all analysis sections (Summary, Sentiment, News) render vertically for full scannability
- Glass card effects with hover state transitions and subtle backdrop blur

### Theme
- **Dark-only** design with zinc-based color palette
- Glassmorphic card effects with subtle backdrop blur
- Semantic color tokens: `primary` (blue), `success` (green), `danger` (pink-red), `warning` (amber)
- Three-layer color system: Tailwind config, `@theme` CSS tokens, and `:root` CSS custom properties

### Components
- **Dashboard** — Main layout with view mode toggle (Analysis / History / Watchlist), 2-7-3 grid, search, agent orchestration, and SSE streaming
- **HistoryDashboard** — Analysis history browser with ticker selector, SVG score trend chart, recommendation filter, paginated table, delete actions
- **WatchlistPanel** — Watchlist CRUD, add/remove tickers, per-ticker analysis, batch "Analyze All" via SSE, comparison table sorted by confidence
- **Summary** — Structured executive overview with:
  - Verdict banner (colored BUY/HOLD/SELL with score and summary)
  - At-a-glance metric pills (score, confidence, position, horizon)
  - 10 expandable chain-of-thought sections with domain icons and one-line insights
  - Price targets range bar visualization + 3-column grid
  - Risks and opportunities with numbered lists
- **Recommendation** — SVG gauge showing BUY/HOLD/SELL with score, confidence bar, position/horizon, and agent consensus strip (per-agent signal dots)
- **MacroSnapshot** — Compact sidebar widget showing fed funds rate, treasury yields, yield curve status, inflation, unemployment, GDP, economic cycle, and risk environment
- **PriceChart** — TradingView chart with metric cards, technical indicators (RSI, MACD, signal strength), and data source provenance badges
- **SentimentReport** — Sentiment meter, factor breakdown with centered bars, and key themes
- **AgentStatus** — Real-time progress pipeline for 7 agents with status indicators and duration tracking
- **NewsFeed** — Relevance-scored news article list with source attribution

## Docker

### Production

```bash
# Build and run
docker compose up --build

# Backend: http://localhost:8000
# Frontend: http://localhost:3000 (nginx proxies /api/* to backend)
```

### Development (with hot-reload)

```bash
docker compose -f docker-compose.dev.yml up --build

# Backend: http://localhost:8000 (auto-reload on file changes)
# Frontend: http://localhost:5173 (Vite HMR)
```

Environment variables are read from `.env` by docker-compose. The SQLite database is persisted in a Docker volume.

## Troubleshooting

### Common Issues

**Import errors**
```bash
# Make sure you're in the project root and virtual environment is activated
source venv/bin/activate
export PYTHONPATH=$PYTHONPATH:$(pwd)
```

**API key errors**
```bash
# Check your .env file has valid API keys
cat .env | grep API_KEY
```

**Database errors**
```bash
# Delete and recreate database
rm market_research.db
python run.py  # Will create fresh database
```

**Alpha Vantage rate limiting**
- Built-in rate limiter enforces per-minute and per-day limits (configurable via `AV_RATE_LIMIT_PER_MINUTE` / `AV_RATE_LIMIT_PER_DAY`)
- Free tier allows 25 requests/day, 5 requests/minute — the rate limiter queues excess requests automatically
- Each full analysis uses ~22 AV requests (across all agents concurrently; macro data cached for 1 day)
- Agents automatically fall back to yfinance/NewsAPI when daily limit is exhausted
- Check logs for `"Rate limiter: waiting"` or `"AV daily limit reached"` messages
- Consider upgrading to AV premium for production use and adjusting rate limit config accordingly

**Alpha Vantage returns empty data**
- Verify ticker is valid on AV (some international tickers differ)
- Agents gracefully fall back to alternative sources
- Check `data_source` field in agent results to confirm which source was used

## Roadmap

### Tier 2 — Meaningful Feature Expansions

- **Options flow / unusual activity agent**: New agent monitoring options market data for unusual volume, put/call ratios, and large block trades.
- **PDF export with branded report**: Generate downloadable PDF reports with charts, agent summaries, and recommendation branding.
- **Scheduled / recurring analysis**: Cron-style or interval-based automatic re-analysis of watched tickers.
- **Alert system**: Notify users when a ticker's recommendation changes or crosses a score threshold.

### Tier 3 — Polish & Production Readiness

- **TypeScript migration for frontend**: Convert React components to TypeScript for type safety across complex agent result structures.
- **Light/dark theme toggle**: Add a light theme variant with a toggle in the header.
- **Authentication & multi-user support**: User accounts, API key management, and per-user watchlists.
- **Database optimization**: Additional indices on `agent_results.agent_type` and composite indices for cross-ticker queries.

### Tier 4 — Ambitious / Differentiating

- **Agent performance scoring**: Track prediction accuracy over time by comparing recommendations to actual price movements.
- **Custom agent builder**: User-configurable agents with selectable data sources, LLM prompts, and weighting.
- **Sector / industry heatmap**: Aggregate analysis results across tickers to visualize sector-level sentiment and momentum.
- **Real-time market data streaming**: Continuous intraday data feeds replacing periodic snapshots.

### Completed

- ~~**Test suite (pytest)**: 80 unit and integration tests covering agents, orchestrator, API endpoints, AV cache, and rate limiter with full mocking infrastructure.~~ *(Done — `tests/` directory with conftest fixtures, 80 passing tests, pytest-asyncio + aioresponses)*
- ~~**Multi-ticker watchlist & comparison**: Batch analysis across multiple tickers with watchlist persistence, SSE batch streaming, and side-by-side comparison UI.~~ *(Done — `watchlists` + `watchlist_tickers` tables, 8 CRUD endpoints, WatchlistPanel component with batch analyze + comparison)*
- ~~**Analysis history dashboard**: Browse past analyses per ticker, visualize score trends over time, filter/paginate results, and delete records.~~ *(Done — HistoryDashboard with SVG trend chart, recommendation filter, paginated table, 3 new API endpoints)*
- ~~**Docker containerization**: Dockerfile + docker-compose for one-command deployment of backend and frontend with persistent SQLite volume.~~ *(Done — multi-stage Dockerfiles, production + dev compose, nginx reverse proxy with SSE support)*
- ~~**Real-time streaming via SSE**: Replace WebSocket polling pattern with Server-Sent Events for simpler one-way streaming of agent progress updates.~~ *(Done — `GET /api/analyze/{ticker}/stream` delivers progress + final result via SSE)*
- ~~**Macroeconomic agent**: Add an agent for broader market context using AV endpoints like `FEDERAL_FUNDS_RATE`, `CPI`, `REAL_GDP`, and treasury yield data.~~ *(Done — `MacroAgent` fetches 7 AV macro endpoints with yield curve, economic cycle, and risk environment analysis)*
- ~~**News sentiment aggregation into sentiment agent**: The AV NEWS_SENTIMENT endpoint provides per-article sentiment scores. These could be forwarded to the sentiment agent to supplement its LLM-based analysis.~~ *(Done — AV per-article sentiment scores are now included in the LLM prompt and blended into the keyword fallback)*
- ~~**Export analysis as CSV**: Add endpoints to export analysis results in downloadable formats for reporting.~~ *(Done — CSV export available at `GET /api/analysis/{ticker}/export/csv`)*
- ~~**In-flight request coalescing**: Deduplicate concurrent identical AV requests (e.g., market and technical agents both requesting TIME_SERIES_DAILY simultaneously).~~ *(Done — `AVCache` tracks in-flight requests via `asyncio.Future`; concurrent identical requests coalesce into a single HTTP call)*

## License

MIT

## Contributing

Contributions welcome! Please open an issue or PR.
