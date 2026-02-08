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
- **Alpha Vantage as primary data source** across all data agents (15 endpoints)
- Graceful fallback to yfinance, NewsAPI, and SEC EDGAR when AV is unavailable
- `data_source` tracking in every agent output for transparency
- LLM-powered equity research (Anthropic Claude / OpenAI / xAI Grok)
- WebSocket support for live progress updates
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
POST /api/analyze/{ticker}

Example:
curl -X POST http://localhost:8000/api/analyze/NVDA
```

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

### WebSocket Real-time Updates
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/analysis/NVDA');

ws.onmessage = (event) => {
  const update = JSON.parse(event.data);
  console.log(update);
};
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
│   ├── orchestrator.py        # Agent coordination
│   ├── models.py              # Pydantic models
│   ├── api.py                 # FastAPI application
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
- **Dashboard** - Main layout with search, agent orchestration, and WebSocket integration
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
- Free tier allows 25 requests/day, 5 requests/minute
- Each full analysis uses ~15 AV requests (across all agents concurrently)
- Agents automatically fall back to yfinance/NewsAPI when rate-limited
- Check logs for `"Alpha Vantage rate limited"` messages
- Consider upgrading to AV premium for production use

**Alpha Vantage returns empty data**
- Verify ticker is valid on AV (some international tickers differ)
- Agents gracefully fall back to alternative sources
- Check `data_source` field in agent results to confirm which source was used

## Potential Future Improvements

- **Shared AV session / connection pooling**: Each agent currently creates its own `aiohttp.ClientSession` per request. A shared session (or connection pool) across agents would reduce connection overhead and improve performance.
- **AV request rate limiter**: Implement a centralized rate limiter (e.g., token bucket) to coordinate AV API calls across all agents and avoid hitting rate limits during concurrent analysis.
- **Refactor `_av_request()` into base class**: The `_av_request()` method is duplicated across all 4 data agents. Extracting it into `BaseAgent` (or a mixin) would reduce duplication.
- **AV response caching layer**: Cache AV responses (keyed by function + symbol + date) to avoid redundant API calls when analyzing the same ticker repeatedly within a short window.
- **Light/dark theme toggle**: The frontend currently supports dark theme only. Adding a light theme variant with a toggle would improve accessibility.
- **Historical data source comparison**: Track and display which data source was used per agent over time, allowing users to compare analysis quality between AV and fallback sources.
- **Unit and integration tests**: Add pytest test suite for agent data parsing, AV response handling, fallback logic, and end-to-end analysis flow.
- **Real-time streaming via SSE**: Replace WebSocket polling pattern with Server-Sent Events for simpler one-way streaming of agent progress updates.
- **Multi-ticker batch analysis**: Support analyzing multiple tickers in a single request with shared AV rate budget.
- **Options flow / unusual activity agent**: Add a new agent that monitors options market data for unusual volume, put/call ratios, and large block trades.
- **Macroeconomic agent**: Add an agent for broader market context using AV endpoints like `FEDERAL_FUNDS_RATE`, `CPI`, `REAL_GDP`, and treasury yield data.
- **News sentiment aggregation into sentiment agent**: The AV NEWS_SENTIMENT endpoint provides per-article sentiment scores. These could be forwarded to the sentiment agent to supplement its LLM-based analysis.
- **Docker containerization**: Add Dockerfile and docker-compose for one-command deployment of both backend and frontend.
- **Configurable agent pipeline**: Allow users to enable/disable specific agents or adjust their weights in the solution agent via API parameters.
- **Export analysis as PDF/CSV**: Add endpoints to export analysis results in downloadable formats for reporting.

## License

MIT

## Contributing

Contributions welcome! Please open an issue or PR.
