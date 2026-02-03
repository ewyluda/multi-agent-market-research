# Multi-Agent Market Research Platform

Real-time AI-powered stock market analysis using specialized agents.

## Overview

This application uses 5 specialized AI agents to analyze stocks from different perspectives:
- **News Agent**: Gathers financial news from multiple sources
- **Sentiment Agent**: LLM-based sentiment analysis
- **Fundamentals Agent**: Company financial metrics and health
- **Market Agent**: Price trends and market conditions
- **Technical Agent**: RSI, MACD, Bollinger Bands analysis

A **Solution Agent** synthesizes all outputs using chain-of-thought reasoning to provide a final BUY/HOLD/SELL recommendation.

## Features

- Real-time multi-agent analysis
- WebSocket support for live progress updates
- Historical analysis tracking
- SQLite database with comprehensive caching
- RESTful API built with FastAPI
- LLM-powered sentiment and synthesis (Claude/GPT-4)

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

## Setup

### Prerequisites

- Python 3.9+
- API Keys:
  - **Required**: Anthropic API key (or OpenAI API key)
  - **Optional**: Alpha Vantage, NewsAPI, Twitter API

### Installation

1. **Clone the repository**
   ```bash
   cd /Users/ericwyluda/Development/projects/multi-agent-market-research
   ```

2. **Create and activate virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env and add your API keys
   ```

   **Minimum required:**
   ```
   ANTHROPIC_API_KEY=your_key_here
   ```

### Running the Backend

```bash
python run.py
```

The API will be available at `http://localhost:8000`

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
    "reasoning": "Ford exhibits mixed signals...",
    "risks": [
      "EV strategy concerns",
      "Market volatility"
    ],
    "opportunities": [
      "Strong fundamentals",
      "Potential cost-cutting benefits"
    ],
    "price_targets": {
      "entry": 13.74,
      "target": 15.50,
      "stop_loss": 12.00
    },
    "position_size": "MEDIUM",
    "time_horizon": "MEDIUM_TERM"
  },
  "agent_results": {
    "news": { ... },
    "sentiment": { ... },
    "fundamentals": { ... },
    "market": { ... },
    "technical": { ... }
  },
  "duration_seconds": 32.5
}
```

## Testing

### Test Single Analysis

```bash
# Activate virtual environment
source venv/bin/activate

# Run Python REPL
python

# Test orchestrator
from src.orchestrator import Orchestrator
import asyncio

async def test():
    orchestrator = Orchestrator()
    result = await orchestrator.analyze_ticker("AAPL")
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
curl http://localhost:8000/api/analyze/AAPL/latest
```

## Configuration

All configuration is in `.env` file. Key settings:

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_PROVIDER` | LLM provider (anthropic/openai) | anthropic |
| `LLM_MODEL` | Model to use | claude-3-5-sonnet-20241022 |
| `AGENT_TIMEOUT` | Agent execution timeout (sec) | 30 |
| `NEWS_LOOKBACK_DAYS` | Days of news to fetch | 7 |
| `MAX_NEWS_ARTICLES` | Max articles per request | 20 |

See `.env.example` for all available options.

## Database

The application uses SQLite by default. Database file: `market_research.db`

### Tables
- `analyses` - Main analysis records
- `agent_results` - Individual agent outputs
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
│       ├── base_agent.py      # Base agent class
│       ├── news_agent.py      # News gathering
│       ├── sentiment_agent.py # Sentiment analysis
│       ├── fundamentals_agent.py  # Company fundamentals
│       ├── market_agent.py    # Market data
│       ├── technical_agent.py # Technical indicators
│       └── solution_agent.py  # Final synthesis
├── requirements.txt           # Python dependencies
├── .env.example              # Environment template
├── run.py                    # Startup script
└── README.md                 # This file
```

## Next Steps

### Frontend Development

The backend is complete and ready. Next steps for building the React frontend:

1. **Initialize React app**
   ```bash
   cd frontend
   npm create vite@latest . -- --template react
   npm install
   ```

2. **Install dependencies**
   ```bash
   npm install axios chart.js react-chartjs-2 recharts tailwindcss react-gauge-chart
   ```

3. **Create components** (see plan for details):
   - Dashboard
   - PriceChart
   - SentimentReport
   - AgentStatus
   - Recommendation
   - Summary
   - NewsFeed
   - RisksOpportunities

4. **Connect to backend API**
   - Use Axios for HTTP requests
   - WebSocket for real-time updates

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

## License

MIT

## Contributing

Contributions welcome! Please open an issue or PR.
