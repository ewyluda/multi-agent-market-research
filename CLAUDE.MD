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

1. **News Agent** (`src/agents/news_agent.py`) - Fetches financial news from multiple sources
2. **Sentiment Agent** (`src/agents/sentiment_agent.py`) - LLM-based sentiment analysis on news
3. **Fundamentals Agent** (`src/agents/fundamentals_agent.py`) - Company financials and health metrics
4. **Market Agent** (`src/agents/market_agent.py`) - Price trends and market conditions
5. **Technical Agent** (`src/agents/technical_agent.py`) - RSI, MACD, Bollinger Bands
6. **Solution Agent** (`src/agents/solution_agent.py`) - Synthesizes all outputs with chain-of-thought reasoning

## Core Files

### Entry Points
- **`run.py`** - Application startup script (runs FastAPI server)
- **`src/api.py`** - FastAPI application with REST and WebSocket endpoints

### Core Logic
- **`src/orchestrator.py`** - Coordinates all agents in parallel, manages workflow
- **`src/database.py`** - SQLite operations, caching, data persistence
- **`src/config.py`** - Environment variable management, configuration
- **`src/models.py`** - Pydantic models for data validation

### Agent Directory Structure
```
src/agents/
├── base_agent.py         # Abstract base class for all agents
├── news_agent.py         # News gathering
├── sentiment_agent.py    # Sentiment analysis (LLM-powered)
├── fundamentals_agent.py # Company fundamentals
├── market_agent.py       # Market data
├── technical_agent.py    # Technical indicators
└── solution_agent.py     # Final synthesis (LLM-powered)
```

## Key Technologies

- **FastAPI** - REST API and WebSocket server
- **SQLite** - Database for caching and persistence
- **Anthropic Claude / OpenAI** - LLM for sentiment and synthesis
- **AsyncIO** - Parallel agent execution
- **Pydantic** - Data validation and models
- **yfinance** - Stock market data
- **Alpha Vantage** - Market data API (optional)
- **NewsAPI** - News aggregation (optional)

## Environment Setup

### Required Environment Variables
```bash
ANTHROPIC_API_KEY=sk-...  # Primary LLM provider
# OR
OPENAI_API_KEY=sk-...     # Alternative LLM provider
```

### Optional API Keys
```bash
ALPHA_VANTAGE_API_KEY=...
NEWSAPI_KEY=...
TWITTER_BEARER_TOKEN=...
```

### Configuration Options (`.env`)
- `LLM_PROVIDER` - "anthropic" or "openai" (default: anthropic)
- `LLM_MODEL` - Model name (default: claude-3-5-sonnet-20241022)
- `AGENT_TIMEOUT` - Timeout in seconds (default: 30)
- `NEWS_LOOKBACK_DAYS` - Days of news history (default: 7)
- `MAX_NEWS_ARTICLES` - Max articles to fetch (default: 20)

## Running the Application

### Start Server
```bash
# Activate virtual environment
source venv/bin/activate

# Start server
python run.py
```

Server runs on `http://localhost:8000`

### API Endpoints

**Analyze Stock**
```bash
POST /api/analyze/{ticker}
curl -X POST http://localhost:8000/api/analyze/NVDA
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
3. Implement `async def analyze(self, ticker: str) -> Dict[str, Any]`
4. Register agent in `src/orchestrator.py`
5. Update database schema if needed

Example:
```python
from src.agents.base_agent import BaseAgent

class NewAgent(BaseAgent):
    async def analyze(self, ticker: str) -> Dict[str, Any]:
        # Your analysis logic here
        return {
            "status": "success",
            "data": {...}
        }
```

### Modifying API Endpoints

Edit `src/api.py` - FastAPI application with all routes.

### Changing LLM Provider

Update `.env`:
```bash
LLM_PROVIDER=openai  # or anthropic
OPENAI_API_KEY=sk-...
```

### Debugging Agent Failures

1. Check logs for specific agent errors
2. Review `agent_results` table in database
3. Test agent individually:
```python
from src.agents.news_agent import NewsAgent
import asyncio

async def test():
    agent = NewsAgent()
    result = await agent.analyze("AAPL")
    print(result)

asyncio.run(test())
```

## Important Patterns

### Orchestrator Pattern
The `Orchestrator` class coordinates all agents:
1. Runs 5 agents in parallel using `asyncio.gather()`
2. Collects results
3. Passes to Solution Agent for synthesis
4. Saves to database
5. Returns final recommendation

### Agent Base Class
All agents inherit from `BaseAgent` which provides:
- Error handling
- Timeout management
- Logging
- Result validation

### Data Flow
```
Ticker → Orchestrator → Agents (parallel) → Solution Agent → Database → API Response
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
    result = await agent.analyze("NVDA")
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

## Frontend Integration

The frontend is in `frontend/` directory (separate React app).

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

## Code Style

- **Async/await** for all I/O operations
- **Type hints** on all functions
- **Pydantic models** for data validation
- **Error handling** with try/except in agents
- **Logging** for debugging

## Security Notes

- API keys stored in `.env` (not committed to git)
- `.env.example` provided as template
- Database is local SQLite (not exposed)
- CORS configured for frontend access

## Performance Considerations

- Agents run in **parallel** for speed
- Database **caching** reduces API calls
- News and price data **cached** with TTL
- Agent **timeout** prevents hanging
- WebSocket for **real-time** updates (no polling)

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

## File Reading Priority

For most tasks, read these files first:
1. `src/orchestrator.py` - Understand workflow
2. `src/agents/base_agent.py` - Understand agent interface
3. Specific agent file you're modifying
4. `src/models.py` - Understand data structures
5. `src/database.py` - Understand persistence

## Quick Reference Commands

```bash
# Start server
python run.py

# Test API
curl http://localhost:8000/health
curl -X POST http://localhost:8000/api/analyze/AAPL

# Check database
sqlite3 market_research.db "SELECT * FROM analyses ORDER BY timestamp DESC LIMIT 1;"

# Activate venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Response Format Example

```json
{
  "success": true,
  "ticker": "NVDA",
  "analysis_id": 1,
  "analysis": {
    "recommendation": "BUY|HOLD|SELL",
    "score": -100 to 100,
    "confidence": 0.0 to 1.0,
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
    "news": {...},
    "sentiment": {...},
    "fundamentals": {...},
    "market": {...},
    "technical": {...}
  },
  "duration_seconds": 32.5
}
```

## License

MIT License - See project README.md for details.
