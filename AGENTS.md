# AGENTS.md - Project Guide for AI Coding Agents

## Project Overview

This is a **Multi-Agent Market Research Platform** that performs AI-powered US equity analysis using specialized agents working in parallel, followed by a solution agent that synthesizes outputs into actionable recommendations.

### Key Capabilities
- **Real-time stock analysis** powered by 7 specialized data agents (news, sentiment, fundamentals, market, technical, macro, options)
- **Quant/PM workflow support** with deterministic signal contracts, calibration economics, and portfolio optimization
- **SSE streaming** for live progress updates during analysis
- **Watchlist management** with batch analysis and opportunity ranking
- **Scheduled analysis** with catalyst detection (earnings, macro events)
- **Portfolio tracking** with risk metrics and position sizing
- **Alert system** with v1 and v2 rule types

### Architecture Overview

```
Client → FastAPI → Orchestrator → [Data Agents] → Solution Agent
                                           ↓
                                    signal_contract_v2
                                    PortfolioEngine
                                    SQLite
                                    REST/SSE response
```

Scheduled flow:
```
APScheduler → Orchestrator → analysis_outcomes/calibration_snapshots/reliability_bins → AlertEngine
```

---

## Technology Stack

### Backend
- **Python 3.11+** with async/await pattern
- **FastAPI** - REST API and Server-Sent Events (SSE)
- **SQLite** - Database for persistence (with WAL mode)
- **APScheduler** - Background job scheduling
- **aiohttp** - Async HTTP client for external APIs
- **Pydantic** - Data validation and serialization

### Frontend
- **React 19** with hooks and context
- **Vite** - Build tool and dev server
- **Tailwind CSS v4** - Utility-first styling
- **framer-motion** - Animations and transitions
- **lightweight-charts** - TradingView-style charts

### External APIs
- **Alpha Vantage** - Primary market data source
- **Tavily AI Search** - Enhanced news and research context
- **yfinance** - Yahoo Finance fallback
- **NewsAPI** - News fallback
- **Twitter/X API v2** - Social sentiment
- **Anthropic Claude / OpenAI / xAI Grok** - LLM providers

---

## Project Structure

```
├── src/                          # Backend source
│   ├── api.py                    # FastAPI application (all endpoints)
│   ├── orchestrator.py           # Agent coordination and execution
│   ├── config.py                 # Environment configuration
│   ├── database.py               # SQLite operations and schema
│   ├── models.py                 # Pydantic request/response models
│   ├── scheduler.py              # APScheduler integration
│   ├── alert_engine.py           # Alert rule evaluation
│   ├── signal_contract.py        # Deterministic v2 signal builder
│   ├── portfolio_engine.py       # Portfolio advisory overlay
│   ├── pdf_report.py             # PDF export generation
│   ├── av_rate_limiter.py        # Alpha Vantage rate limiting
│   ├── av_cache.py               # In-flight request coalescing + TTL cache
│   ├── rollout_canary.py         # Phase 7 rollout canary runner
│   ├── rollout_metrics.py        # Rollout gate metrics
│   ├── backfill_signal_contract.py  # Historical backfill utility
│   ├── tavily_client.py          # Tavily AI search client
│   └── agents/                   # Agent implementations
│       ├── base_agent.py         # Abstract base with AV/fallback support
│       ├── news_agent.py         # News gathering (Tavily → AV → NewsAPI)
│       ├── sentiment_agent.py    # LLM-based sentiment analysis
│       ├── fundamentals_agent.py # Financial data + equity research
│       ├── market_agent.py       # Price trends and market data
│       ├── technical_agent.py    # RSI, MACD, Bollinger Bands
│       ├── macro_agent.py        # US macroeconomic indicators
│       ├── options_agent.py      # Options flow and unusual activity
│       └── solution_agent.py     # Final synthesis and recommendation
│
├── frontend/                     # React frontend
│   ├── src/
│   │   ├── components/           # React components
│   │   │   ├── Dashboard.jsx     # Root layout
│   │   │   ├── Sidebar.jsx       # Navigation sidebar
│   │   │   ├── AnalysisTabs.jsx  # Tabbed content (Overview/Risks/Opportunities/Diagnostics)
│   │   │   ├── Recommendation.jsx # Gauge and consensus display
│   │   │   ├── WatchlistPanel.jsx # Watchlist management
│   │   │   ├── HistoryDashboard.jsx # Analysis history browser
│   │   │   ├── PortfolioPanel.jsx # Portfolio management
│   │   │   ├── AlertPanel.jsx    # Alert rules and notifications
│   │   │   └── ...
│   │   ├── hooks/                # Custom React hooks
│   │   ├── context/              # React context providers
│   │   └── utils/api.js          # API client
│   ├── Dockerfile                # Production build (nginx)
│   ├── Dockerfile.dev            # Development (Vite hot-reload)
│   └── nginx.conf                # Nginx reverse proxy config
│
├── tests/                        # Test suite
│   ├── conftest.py               # Shared pytest fixtures
│   ├── test_api.py
│   ├── test_orchestrator.py
│   ├── test_database.py
│   ├── test_alert_engine.py
│   ├── test_scheduler.py
│   ├── test_calibration.py
│   ├── test_signal_contract.py
│   ├── test_portfolio_engine.py
│   ├── test_rollout_*.py
│   └── test_agents/              # Agent-specific tests
│
├── docs/                         # Documentation
│   ├── plans/                    # Implementation plans
│   └── reports/                  # Backfill reports, etc.
│
├── run.py                        # Application entry point
├── pyproject.toml                # Pytest configuration
├── requirements.txt              # Python dependencies
├── Dockerfile                    # Backend Dockerfile
├── docker-compose.yml            # Production Docker stack
├── docker-compose.dev.yml        # Development Docker stack
└── .env.example                  # Environment variable template
```

---

## Build and Test Commands

### Backend

```bash
# Setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run development server
python run.py

# Run tests
pytest

# Run with coverage
pytest --cov=src --cov-report=term-missing

# Run specific test file
pytest tests/test_orchestrator.py -v

# Run with markers
pytest -m "not slow"  # Skip slow tests
pytest -m "integration"  # Run only integration tests
```

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Development server (Vite hot-reload)
npm run dev

# Production build
npm run build

# Preview production build
npm run preview

# Lint
npm run lint
```

### Docker

```bash
# Development with hot reload
docker compose -f docker-compose.dev.yml up --build

# Production stack
docker compose up --build

# Access:
# - Frontend: http://localhost:3000 (prod) or http://localhost:5173 (dev)
# - Backend API: http://localhost:8000
# - Health check: http://localhost:8000/health
```

---

## Code Style Guidelines

### Python

1. **Type Hints**: Use typing for function signatures and complex data structures
   ```python
   from typing import Dict, Any, Optional, List
   
   async def analyze_ticker(self, ticker: str) -> Dict[str, Any]:
       ...
   ```

2. **Docstrings**: Google-style docstrings for all public methods
   ```python
   def method(self, param: str) -> Result:
       """
       Brief description.
       
       Args:
           param: Description of param
           
       Returns:
           Description of return value
       """
   ```

3. **Async Pattern**: All I/O operations must be async
   - Use `asyncio.to_thread()` for blocking calls (yfinance, LLM APIs)
   - Use `aiohttp` for HTTP requests
   - Use `asyncio.gather()` for parallel execution

4. **Error Handling**: Fail gracefully with logged warnings
   ```python
   try:
       data = await self.fetch()
   except Exception as e:
       self.logger.warning(f"Fetch failed: {e}")
       data = None  # Allow fallback
   ```

5. **Naming**: snake_case for functions/variables, PascalCase for classes

6. **Constants**: UPPER_CASE for module-level constants

### JavaScript/React

1. **Components**: PascalCase, functional components with hooks
2. **Hooks**: Prefix with `use`, camelCase
3. **Props**: Destructure in component signature
4. **State**: Use React Context for global state, useState for local
5. **Styling**: Tailwind classes, prefer semantic tokens from `@theme`

---

## Testing Instructions

### Test Organization

```
tests/
├── conftest.py              # Shared fixtures
├── test_api.py              # API endpoint tests
├── test_orchestrator.py     # Orchestrator logic
├── test_database.py         # Database operations
├── test_alert_engine.py     # Alert evaluation
├── test_scheduler.py        # Scheduler functionality
├── test_calibration.py      # Calibration economics
├── test_signal_contract.py  # Signal contract v2
├── test_portfolio_engine.py # Portfolio logic
├── test_rollout_canary.py   # Rollout automation
├── test_rollout_metrics.py  # Rollout metrics
└── test_agents/             # Agent tests
    ├── test_base_agent.py
    ├── test_options_agent.py
    └── test_solution_agent.py
```

### Running Tests

```bash
# All tests
pytest

# Verbose output
pytest -v

# With coverage
pytest --cov=src --cov-report=html

# Specific markers
pytest -m "slow"           # Real API calls (>5s)
pytest -m "integration"    # Multi-component tests
pytest -m "not slow"       # Fast tests only

# Specific test
pytest tests/test_api.py::test_analyze_ticker -v
```

### Test Fixtures

Key fixtures in `conftest.py`:
- `db_manager` - In-memory database for tests
- `mock_av_response` - Mocked Alpha Vantage responses
- `test_ticker` - Standard test ticker symbol
- `av_cache` - Fresh AVCache instance
- `av_rate_limiter` - Rate limiter with generous limits for testing
- `test_config` - Configuration dictionary for testing
- `make_agent` - Factory to create agents with injected test infrastructure

### Writing Tests

```python
import pytest

@pytest.mark.asyncio
async def test_agent_execution():
    agent = TestAgent("AAPL", config)
    result = await agent.execute()
    assert result["success"] is True
    assert result["agent_type"] == "test"
```

---

## Security Considerations

### API Keys
- **NEVER commit `.env` file** - it's in `.gitignore`
- Store API keys in environment variables only
- Rotate keys regularly
- Use different keys for development/production

### Required Keys

```bash
# At least one LLM provider (required)
ANTHROPIC_API_KEY=sk-...
# OR
OPENAI_API_KEY=sk-...
# OR
GROK_API_KEY=...

# Data sources (strongly recommended)
ALPHA_VANTAGE_API_KEY=...
TAVILY_API_KEY=...
```

### Security Best Practices

1. **Input Validation**: All API endpoints validate ticker format (`^[A-Z]{1,5}$`)
2. **Rate Limiting**: Alpha Vantage requests are rate-limited per-minute and per-day
3. **SQL Injection**: Database queries use parameterized statements
4. **CORS**: Configured via `CORS_ORIGINS` environment variable
5. **No Sensitive Data in Logs**: API keys are never logged

### Docker Security
- Backend runs as non-root user
- Frontend nginx runs on port 80 (unprivileged in container)
- Health checks verify service availability
- No secrets in Docker layers

---

## Agent Development

### Creating a New Agent

1. **Inherit from BaseAgent**:
   ```python
   from src.agents.base_agent import BaseAgent
   
   class NewAgent(BaseAgent):
       async def fetch_data(self) -> Dict[str, Any]:
           # Fetch from primary source (Alpha Vantage)
           data = await self._av_request({"function": "..."})
           if not data:
               # Fallback implementation
               data = await self._fetch_fallback()
           return data
       
       async def analyze(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
           # Process and return structured data
           return {"metric": value, "summary": "..."}
   ```

2. **Register in Orchestrator**:
   ```python
   # src/orchestrator.py
   AGENT_REGISTRY = {
       "new_agent": {"class": NewAgent, "requires": []},
       # ...
   }
   ```

3. **Add Tests**:
   Create `tests/test_agents/test_new_agent.py`

### Agent Data Source Priority

All agents follow **primary → fallback** pattern:
1. Try Alpha Vantage (via `_av_request()`)
2. Fall back to yfinance or other sources
3. Track `data_source` in output for provenance

### Shared Resources

The orchestrator injects shared resources into agents:
- `_shared_session` - aiohttp session for connection pooling
- `_rate_limiter` - AVRateLimiter for rate limiting
- `_av_cache` - AVCache for response caching and request coalescing

---

## Configuration Reference

### Key Environment Variables

#### LLM Configuration
| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | anthropic | anthropic, openai, or xai |
| `LLM_MODEL` | claude-3-5-sonnet-20241022 | Model identifier |
| `LLM_TEMPERATURE` | 0.3 | Sampling temperature |
| `LLM_MAX_TOKENS` | 4096 | Max response tokens |

#### Feature Flags
| Variable | Default | Description |
|----------|---------|-------------|
| `SIGNAL_CONTRACT_V2_ENABLED` | false | Enable deterministic signal contract |
| `PORTFOLIO_OPTIMIZER_V2_ENABLED` | false | Enable optimizer v2 |
| `CALIBRATION_ECONOMICS_ENABLED` | false | Enable calibration economics |
| `ALERTS_V2_ENABLED` | false | Enable v2 alert rule types |
| `WATCHLIST_RANKING_ENABLED` | false | Enable opportunity ranking |
| `COT_PERSISTENCE_ENABLED` | false | Persist chain-of-thought |

#### Scheduled Rollout Overrides
| Variable | Default | Description |
|----------|---------|-------------|
| `SCHEDULED_SIGNAL_CONTRACT_V2_ENABLED` | false | Enable v2 for scheduled runs only |
| `SCHEDULED_CALIBRATION_ECONOMICS_ENABLED` | false | Enable calibration for scheduled runs |
| `SCHEDULED_PORTFOLIO_OPTIMIZER_V2_ENABLED` | false | Enable optimizer v2 for scheduled runs |
| `SCHEDULED_ALERTS_V2_ENABLED` | false | Enable v2 alerts for scheduled runs |

#### Rate Limits
| Variable | Default | Description |
|----------|---------|-------------|
| `AV_RATE_LIMIT_PER_MINUTE` | 5 | Alpha Vantage calls per minute |
| `AV_RATE_LIMIT_PER_DAY` | 25 | Alpha Vantage calls per day |

---

## API Endpoints

### Analysis
- `POST /api/analyze/{ticker}` - Trigger analysis
- `POST /api/analyze/batch` - Batch analysis (SSE stream)
- `GET /api/analyze/{ticker}/stream` - SSE progress stream
- `GET /api/analysis/{ticker}/latest` - Get latest analysis
- `GET /api/analysis/{ticker}/history` - Get analysis history
- `GET /api/analysis/{ticker}/history/detailed` - Paginated with filters
- `GET /api/analysis/tickers` - List analyzed tickers
- `DELETE /api/analysis/{analysis_id}` - Delete analysis

### Exports
- `GET /api/analysis/{ticker}/export/csv` - CSV export
- `GET /api/analysis/{ticker}/export/pdf` - PDF report

### Watchlists
- `GET/POST /api/watchlists` - CRUD operations
- `GET /api/watchlists/{id}` - Get watchlist with analyses
- `PUT/DELETE /api/watchlists/{id}` - Update/delete
- `POST /api/watchlists/{id}/tickers` - Add ticker
- `DELETE /api/watchlists/{id}/tickers/{ticker}` - Remove ticker
- `POST /api/watchlists/{id}/analyze` - Batch analyze (SSE)
- `GET /api/watchlists/{id}/opportunities` - Ranked opportunities

### Schedules
- `GET/POST /api/schedules` - CRUD operations
- `GET/PUT/DELETE /api/schedules/{id}` - Individual schedule
- `GET /api/schedules/{id}/runs` - Run history

### Portfolio
- `GET /api/portfolio` - Profile + holdings + snapshot
- `PUT /api/portfolio/profile` - Update profile
- `GET/POST /api/portfolio/holdings` - Holdings CRUD
- `GET /api/portfolio/risk-summary` - Risk metrics

### Calibration
- `GET /api/calibration/summary` - Calibration overview
- `GET /api/calibration/ticker/{ticker}` - Ticker-specific
- `GET /api/calibration/reliability` - Reliability bins

### Alerts
- `GET/POST /api/alerts` - Alert rules CRUD
- `PUT/DELETE /api/alerts/{id}` - Individual rule
- `GET /api/alerts/notifications` - Notifications feed
- `POST /api/alerts/notifications/{id}/acknowledge` - Acknowledge
- `GET /api/alerts/notifications/unacknowledged-count` - Count badge

### Rollout
- `GET /api/rollout/phase7/status` - Rollout gate status

### Health
- `GET /health` - Health check

---

## Database Schema

### Core Tables
- `analyses` - Analysis runs with v1/v2 schema support
- `agent_results` - Individual agent outputs
- `sentiment_scores` - Sentiment factor breakdowns
- `price_history` - Cached price data
- `news_cache` - Cached news articles

### Portfolio Tables
- `portfolio_profile` - Singleton portfolio configuration
- `portfolio_holdings` - Position data

### Watchlist/Schedule Tables
- `watchlists` - Watchlist definitions
- `watchlist_tickers` - Many-to-many membership
- `schedules` - Recurring analysis schedules
- `schedule_runs` - Execution history

### Quant PM Tables
- `analysis_outcomes` - Post-analysis outcome tracking
- `calibration_snapshots` - Daily calibration summaries
- `confidence_reliability_bins` - Reliability by confidence band

### Alert Tables
- `alert_rules` - Rule definitions (legacy + v2 types)
- `alert_notifications` - Triggered notifications

### Macro Tables
- `macro_catalyst_events` - Seeded macro event calendar

---

## Rollout and Deployment

### Phase 7 Rollout Process
1. **Preflight** - Basic health and connectivity checks
2. **Stage A** - Feature flag validation
3. **Stage B** - Sample analysis validation
4. **Stage C** - Performance benchmark
5. **Stage D** - End-to-end frontend validation

### Canary Runner

```bash
# Full rollout check
python -m src.rollout_canary --base-url http://localhost:8000 --stage all --window-hours 72

# Individual stages
python -m src.rollout_canary --stage preflight
python -m src.rollout_canary --stage stage_a --window-hours 72
python -m src.rollout_canary --stage stage_b --window-hours 72
python -m src.rollout_canary --stage stage_c --window-hours 72 --stage-c-tickers AAPL,MSFT
python -m src.rollout_canary --stage stage_d --window-hours 72 --frontend-url http://localhost:5173
```

---

## Common Tasks

### Add a New Alert Rule Type
1. Add to `AlertRuleCreate` model in `src/models.py`
2. Add evaluation method in `src/alert_engine.py`
3. Update schema migration in `src/database.py` if needed
4. Add tests in `tests/test_alert_engine.py`

### Add a New Agent
1. Create `src/agents/new_agent.py` inheriting from `BaseAgent`
2. Register in `src/orchestrator.py` `AGENT_REGISTRY`
3. Add tests in `tests/test_agents/`
4. Update SSE progress map in orchestrator

### Database Migration

Migrations are manual and idempotent. Add to `initialize_database()`:

```python
def initialize_database(self):
    with self.get_connection() as conn:
        cursor = conn.cursor()
        # New table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS new_table (...)
        """)
        # Schema migration
        self._ensure_column(cursor, "existing_table", "new_column", "TEXT")
```

---

## Troubleshooting

### Common Issues

**Import errors**: Ensure `venv` is activated and dependencies installed
```bash
source venv/bin/activate
pip install -r requirements.txt
```

**Database locked**: SQLite WAL mode handles most cases; check for unclosed connections

**Rate limit errors**: Monitor `AV_RATE_LIMIT_PER_DAY` usage; cache reduces calls

**Frontend API connection**: Check `VITE_API_URL` environment variable

**SSE not working**: Check nginx proxy buffering settings for SSE endpoints

### Debug Logging

```bash
# Enable debug logging
LOG_LEVEL=DEBUG python run.py
```

---

## Resources

- **FastAPI Docs**: https://fastapi.tiangolo.com/
- **React Docs**: https://react.dev/
- **Tailwind CSS**: https://tailwindcss.com/
- **Alpha Vantage**: https://www.alphavantage.co/documentation/
- **Tavily AI**: https://docs.tavily.com/
