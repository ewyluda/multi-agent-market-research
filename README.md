# Multi-Agent Market Research Platform

Real-time AI-powered stock market analysis using specialized agents.

## Overview

This application uses 5 specialized AI agents to analyze stocks from different perspectives:
- **News Agent**: Gathers financial news with ticker-specific relevance filtering
- **Sentiment Agent**: LLM-based sentiment analysis on news articles
- **Fundamentals Agent**: Company financial metrics, health scoring, and LLM equity research
- **Market Agent**: Price trends, moving averages, and market conditions
- **Technical Agent**: RSI, MACD, Bollinger Bands, SMA analysis

A **Solution Agent** synthesizes all outputs using chain-of-thought reasoning to provide a final BUY/HOLD/SELL recommendation with price targets and risk assessment.

## Features

- Real-time multi-agent analysis with parallel execution
- **Configurable agent pipeline** — select which agents to run per request via `?agents=` parameter
- **Alpha Vantage as primary data source** across all data agents (15 endpoints)
- **AV connection pooling** — shared `aiohttp` session across all agents per analysis
- **AV rate limiting** — centralized sliding-window limiter (5/min, 25/day configurable)
- **AV response caching** — in-memory TTL cache deduplicates repeated requests
- Graceful fallback to yfinance, NewsAPI, and SEC EDGAR when AV is unavailable
- `data_source` tracking in every agent output for transparency
- LLM-powered equity research (Anthropic Claude / OpenAI / xAI Grok)
- Server-Sent Events (SSE) for live progress streaming
- Historical analysis tracking with SQLite
- RESTful API built with FastAPI
- React frontend with Hero UI dark theme

## Architecture

```
User Request → FastAPI → Orchestrator → [5 Agents in Parallel]
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

Valid agent names: `news`, `sentiment`, `fundamentals`, `market`, `technical`. The solution agent always runs.

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
    "technical": { "data_source": "alpha_vantage", "..." : "..." }
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

See `.env.example` for all available options.

## Testing

### Test Single Analysis

```bash
# Activate virtual environment
source venv/bin/activate

# Test via API
curl -X POST http://localhost:8000/api/analyze/AAPL

# Test orchestrator directly
python -c "
from src.orchestrator import Orchestrator
import asyncio

async def test():
    orchestrator = Orchestrator()
    result = await orchestrator.analyze_ticker('AAPL')
    print(result)

asyncio.run(test())
"
```

### Test Individual Agent

```python
from src.agents.market_agent import MarketAgent
import asyncio

async def test():
    agent = MarketAgent()
    result = await agent.execute("NVDA")
    print(f"Source: {result.get('data', {}).get('data_source', 'unknown')}")
    print(result)

asyncio.run(test())
```

### Test API with curl

```bash
# Health check
curl http://localhost:8000/health

# Analyze stock
curl -X POST http://localhost:8000/api/analyze/AAPL

# Get latest analysis
curl http://localhost:8000/api/analysis/AAPL/latest
```

## Database

The application uses SQLite by default. Database file: `market_research.db`

### Tables
- `analyses` - Main analysis records
- `agent_results` - Individual agent outputs (includes `data_source` in JSON)
- `price_history` - Cached price data
- `news_cache` - Cached news articles
- `sentiment_scores` - Sentiment factor breakdown

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
│   ├── config.py              # Configuration management
│   ├── database.py            # Database operations
│   ├── orchestrator.py        # Agent coordination with configurable pipeline
│   ├── models.py              # Pydantic models
│   ├── api.py                 # FastAPI application
│   ├── av_rate_limiter.py     # AV API rate limiter (sliding window)
│   ├── av_cache.py            # AV response cache (in-memory TTL)
│   └── agents/
│       ├── __init__.py
│       ├── base_agent.py      # Base agent class (ABC)
│       ├── news_agent.py      # News gathering (AV → NewsAPI)
│       ├── sentiment_agent.py # Sentiment analysis (LLM)
│       ├── fundamentals_agent.py  # Fundamentals (AV → yfinance + SEC)
│       ├── market_agent.py    # Market data (AV → yfinance)
│       ├── technical_agent.py # Technical indicators (AV → yfinance + local)
│       └── solution_agent.py  # Final synthesis (LLM)
├── frontend/
│   ├── src/
│   │   ├── components/        # React components
│   │   │   ├── Dashboard.jsx
│   │   │   ├── Recommendation.jsx
│   │   │   ├── AgentStatus.jsx
│   │   │   ├── PriceChart.jsx
│   │   │   ├── SentimentReport.jsx
│   │   │   ├── Summary.jsx
│   │   │   ├── NewsFeed.jsx
│   │   │   └── Icons.jsx
│   │   ├── index.css          # Hero UI dark theme (Tailwind v4)
│   │   └── App.jsx
│   ├── tailwind.config.js
│   └── package.json
├── requirements.txt           # Python dependencies
├── .env.example              # Environment template
├── run.py                    # Startup script
├── CLAUDE.md                 # AI assistant guide
└── README.md                 # This file
```

## Frontend

The frontend is a React application with a Hero UI-inspired dark theme built on Tailwind CSS v4.

### Theme
- **Dark-only** design with zinc-based color palette
- Glassmorphic card effects with subtle backdrop blur
- Semantic color tokens: `primary` (blue), `success` (green), `danger` (pink-red), `warning` (amber)
- Three-layer color system: Tailwind config, `@theme` CSS tokens, and `:root` CSS custom properties

### Components
- **Dashboard** - Main layout with search, agent orchestration, and SSE streaming
- **Recommendation** - SVG gauge component showing BUY/HOLD/SELL with score
- **AgentStatus** - Real-time progress indicators for each agent
- **PriceChart** - Price history, moving averages, and technical indicator display
- **SentimentReport** - Sentiment breakdown with factor bars and gradient visualization
- **Summary** - Price targets, risks/opportunities, and position sizing
- **NewsFeed** - Relevance-scored news article list with source attribution

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
- Each full analysis uses ~15 AV requests (across all agents concurrently)
- Agents automatically fall back to yfinance/NewsAPI when daily limit is exhausted
- Check logs for `"Rate limiter: waiting"` or `"AV daily limit reached"` messages
- Consider upgrading to AV premium for production use and adjusting rate limit config accordingly

**Alpha Vantage returns empty data**
- Verify ticker is valid on AV (some international tickers differ)
- Agents gracefully fall back to alternative sources
- Check `data_source` field in agent results to confirm which source was used

## Potential Future Improvements (To-Do List)

- **Light/dark theme toggle**: The frontend currently supports dark theme only. Adding a light theme variant with a toggle would improve accessibility.
- **Historical data source comparison**: Track and display which data source was used per agent over time, allowing users to compare analysis quality between AV and fallback sources.
- **Unit and integration tests**: Add pytest test suite for agent data parsing, AV response handling, fallback logic, and end-to-end analysis flow.
- ~~**Real-time streaming via SSE**: Replace WebSocket polling pattern with Server-Sent Events for simpler one-way streaming of agent progress updates.~~ *(Done — `GET /api/analyze/{ticker}/stream` delivers progress + final result via SSE)*
- **Multi-ticker batch analysis**: Support analyzing multiple tickers in a single request with shared AV rate budget.
- **Options flow / unusual activity agent**: Add a new agent that monitors options market data for unusual volume, put/call ratios, and large block trades.
- ~~**Macroeconomic agent**: Add an agent for broader market context using AV endpoints like `FEDERAL_FUNDS_RATE`, `CPI`, `REAL_GDP`, and treasury yield data.~~ *(Done — `MacroAgent` fetches 7 AV macro endpoints with yield curve, economic cycle, and risk environment analysis)*
- ~~**News sentiment aggregation into sentiment agent**: The AV NEWS_SENTIMENT endpoint provides per-article sentiment scores. These could be forwarded to the sentiment agent to supplement its LLM-based analysis.~~ *(Done — AV per-article sentiment scores are now included in the LLM prompt and blended into the keyword fallback)*
- **Docker containerization**: Add Dockerfile and docker-compose for one-command deployment of both backend and frontend.
- ~~**Export analysis as PDF/CSV**: Add endpoints to export analysis results in downloadable formats for reporting.~~ *(Done — CSV export available at `GET /api/analysis/{ticker}/export/csv`)*
- ~~**In-flight request coalescing**: Deduplicate concurrent identical AV requests (e.g., market and technical agents both requesting TIME_SERIES_DAILY simultaneously).~~ *(Done — `AVCache` tracks in-flight requests via `asyncio.Future`; concurrent identical requests coalesce into a single HTTP call)*

## License

MIT

## Contributing

Contributions welcome! Please open an issue or PR.
