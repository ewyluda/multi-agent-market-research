# AGENTS.md - Project Guide for Coding Agents

## Project Overview

This is a **Multi-Agent Market Research Platform** that provides AI-powered US equity analysis with a quant/PM (Portfolio Manager) workflow upgrade. The platform orchestrates multiple specialized agents to analyze stocks and synthesizes their outputs into actionable trading signals.

### Key Capabilities
- Real-time multi-agent analysis (news, sentiment, fundamentals, market, technical, macro, options)
- Deterministic signal contracts (`signal_contract_v2`) with EV scores, calibrated confidence, and regime labels
- Portfolio optimization with position sizing recommendations
- Watchlist management with cross-sectional opportunity ranking
- Scheduled analysis with calibration economics
- Alert system with v2 rule taxonomy (EV, regime, data quality)
- PDF/CSV export capabilities

### Design Philosophy
- **Additive-first upgrades**: Legacy fields preserved for backward compatibility
- **Feature-flagged rollout**: All v2 features behind config flags (safe defaults)
- **No CoT by default**: Chain-of-thought not persisted/displayed unless explicitly enabled
- **Fail-open**: External service failures don't block analysis flow

---

## Technology Stack

### Backend
| Component | Technology | Version |
|-----------|------------|---------|
| Runtime | Python | 3.10+ |
| Web Framework | FastAPI | 0.109.0 |
| Server | uvicorn | 0.27.0 |
| Database | SQLite | (builtin) |
| Scheduler | APScheduler | 3.10+ |
| HTTP Client | aiohttp | 3.9.3 |
| Data Processing | pandas | 2.2.0 |
| Numerical | numpy | 1.26.3 |
| Validation | pydantic | 2.6.0 |
| LLM SDKs | anthropic, openai | latest |
| PDF Generation | reportlab | 4.0+ |

### Frontend
| Component | Technology | Version |
|-----------|------------|---------|
| Framework | React | 19.2.0 |
| Build Tool | Vite | 7.2.4 |
| Styling | Tailwind CSS | 4.1.18 |
| HTTP Client | axios | 1.13.4 |
| Charts | lightweight-charts | 5.1.0 |
| Animation | framer-motion | 12.34.0 |

### Infrastructure
| Component | Technology |
|-----------|------------|
| Containerization | Docker + Docker Compose |
| Web Server (prod) | nginx |
| Process Management | Python asyncio |

---

## Project Structure

```
multi-agent-market-research/
├── src/                          # Backend source code
│   ├── api.py                    # FastAPI application, routes, lifecycle
│   ├── orchestrator.py           # Agent coordination, pipeline execution
│   ├── models.py                 # Pydantic request/response models
│   ├── database.py               # SQLite schema, migrations, CRUD
│   ├── config.py                 # Environment-driven configuration
│   ├── signal_contract.py        # Deterministic signal_contract_v2 builder
│   ├── portfolio_engine.py       # Portfolio optimization v1/v2
│   ├── scheduler.py              # APScheduler jobs, calibration economics
│   ├── alert_engine.py           # Rule evaluation, notification logic
│   ├── rollout_metrics.py        # Phase 7 rollout gate metrics
│   ├── rollout_canary.py         # CLI canary runner for staged rollout
│   ├── backfill_signal_contract.py # 180-day backfill utility
│   ├── pdf_report.py             # Branded PDF export generation
│   ├── av_rate_limiter.py        # Alpha Vantage rate limiting
│   ├── av_cache.py               # TTL cache + in-flight request coalescing
│   └── agents/                   # Agent implementations
│       ├── base_agent.py         # Abstract base with AV fetching
│       ├── news_agent.py         # News fetching (AV, NewsAPI fallback)
│       ├── sentiment_agent.py    # Sentiment analysis (depends on news)
│       ├── fundamentals_agent.py # Financial fundamentals (AV, yfinance, SEC)
│       ├── market_agent.py       # Market data, price history
│       ├── technical_agent.py    # Technical indicators (RSI, MACD, BB)
│       ├── macro_agent.py        # Macro-economic data (Fed rates, CPI)
│       ├── options_agent.py      # Options flow analysis
│       └── solution_agent.py     # Synthesis agent (LLM-based reasoning)
│
├── frontend/src/                 # Frontend source code
│   ├── App.jsx                   # Root component with AnalysisProvider
│   ├── main.jsx                  # React entry point
│   ├── components/               # React components
│   │   ├── Dashboard.jsx         # Main layout (sidebar + workspace)
│   │   ├── Sidebar.jsx           # Navigation sidebar
│   │   ├── AnalysisTabs.jsx      # Overview/Risk/Opportunities/Diagnostics
│   │   ├── Summary.jsx           # Action/risk/evidence cards
│   │   ├── Recommendation.jsx    # Signal display component
│   │   ├── WatchlistPanel.jsx    # Watchlist CRUD + batch analyze
│   │   ├── PortfolioPanel.jsx    # Holdings management
│   │   ├── AlertPanel.jsx        # Alert rules + notifications
│   │   ├── HistoryDashboard.jsx  # Historical analysis view
│   │   ├── SchedulePanel.jsx     # Scheduled analysis management
│   │   ├── PriceChart.jsx        # TradingView chart widget
│   │   ├── AgentPipelineBar.jsx  # Agent progress visualization
│   │   └── ...
│   ├── context/
│   │   └── AnalysisContext.jsx   # Global analysis state
│   ├── hooks/
│   │   ├── useAnalysis.js        # Analysis execution hook
│   │   ├── useSSE.js             # Server-Sent Events hook
│   │   └── useHistory.js         # History data fetching
│   └── utils/
│       └── api.js                # Axios API client
│
├── tests/                        # Test suite
│   ├── conftest.py               # Shared pytest fixtures
│   ├── test_api.py               # API endpoint tests
│   ├── test_orchestrator.py      # Orchestrator tests
│   ├── test_database.py          # Database tests
│   ├── test_signal_contract.py   # Signal contract tests
│   ├── test_portfolio_engine.py  # Portfolio optimizer tests
│   ├── test_scheduler.py         # Scheduler tests
│   ├── test_alert_engine.py      # Alert engine tests
│   ├── test_calibration.py       # Calibration economics tests
│   ├── test_rollout_metrics.py   # Rollout metrics tests
│   ├── test_rollout_canary.py    # Canary runner tests
│   ├── test_backfill_signal_contract.py
│   ├── test_pdf_report.py
│   ├── test_av_cache.py
│   ├── test_av_rate_limiter.py
│   └── test_agents/              # Agent-specific tests
│       ├── test_base_agent.py
│       ├── test_solution_agent.py
│       └── test_options_agent.py
│
├── docs/                         # Documentation
│   ├── plans/                    # Implementation plans
│   │   ├── 2026-02-16-quant-pm-upgrade-implementation-plan.md
│   │   └── 2026-02-17-analysis-intelligence-design.md
│   └── reports/                  # Audit reports
│       └── signal-contract-backfill-report.md
│
├── run.py                        # Backend startup script
├── requirements.txt              # Python dependencies
├── pyproject.toml                # pytest configuration
├── Dockerfile                    # Backend container
├── docker-compose.yml            # Production Docker stack
├── docker-compose.dev.yml        # Development Docker stack
├── .env.example                  # Environment template
└── AGENTS.md                     # This file
```

---

## Build and Run Commands

### Local Development

**Backend:**
```bash
# Setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your API keys

# Run
python run.py
# Server starts at http://localhost:8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
# Dev server starts at http://localhost:5173
```

### Docker

**Development (with hot reload):**
```bash
docker compose -f docker-compose.dev.yml up --build
# Backend: http://localhost:8000
# Frontend: http://localhost:5173
```

**Production:**
```bash
docker compose up --build
# Frontend (nginx): http://localhost:3000
# API proxied through nginx to backend
```

---

## Testing

### Backend Tests
```bash
source venv/bin/activate
pytest

# With coverage
pytest --cov=src

# Specific markers
pytest -m "not slow"          # Skip slow tests
pytest -m "integration"       # Run integration tests only
```

**Test Configuration** (pyproject.toml):
- `asyncio_mode = "auto"` for async test support
- Custom markers: `slow`, `integration`
- Deprecation warnings ignored

**Current Status:** 214 tests passing

### Frontend Quality
```bash
cd frontend
npm run lint
npm run build
```

### Canary/Rollout Testing
```bash
# Full canary suite
python -m src.rollout_canary --base-url http://localhost:8000 --stage all --window-hours 72

# Stage-specific
python -m src.rollout_canary --stage preflight
python -m src.rollout_canary --stage stage_a --window-hours 72
python -m src.rollout_canary --stage stage_b --window-hours 72
python -m src.rollout_canary --stage stage_c --window-hours 72
python -m src.rollout_canary --stage stage_d --window-hours 72 --frontend-url http://localhost:5173
```

---

## Architecture

### Request Flow
```
Client Request
    ↓
FastAPI (src/api.py)
    ↓
Orchestrator (src/orchestrator.py)
    ↓
[Data Agents in parallel]
├── NewsAgent (Tavily AI Search primary)
├── MarketAgent
├── FundamentalsAgent (Tavily context)
├── TechnicalAgent
├── MacroAgent (if enabled)
└── OptionsAgent (if enabled)
    ↓
SentimentAgent (depends on News context)
    ↓
SolutionAgent (synthesis + Tavily narrative)
    ↓
signal_contract_v2 build/validate
    ↓
PortfolioEngine (optimizer v1/v2)
    ↓
Database persistence
    ↓
REST/SSE response
```

### Scheduled Flow
```
APScheduler triggers
    ↓
Orchestrator.analyze_ticker()
    ↓
Analysis stored
    ↓
Outcomes recorded (analysis_outcomes table)
    ↓
Calibration snapshots updated
    ↓
AlertEngine evaluates rules
    ↓
Notifications created (if triggered)
```

### Database Schema

**Core Tables:**
- `analyses` - Main analysis runs with v1/v2 schema support
- `agent_results` - Individual agent outputs
- `sentiment_scores` - Factor-level sentiment breakdown
- `price_history` - Cached price data
- `news_cache` - Cached news articles

**PM/Quant Tables:**
- `watchlists`, `watchlist_tickers` - Watchlist management
- `schedules`, `schedule_runs` - Scheduled analysis
- `portfolio_profile`, `portfolio_holdings` - Portfolio data
- `alert_rules`, `alert_notifications` - Alert system
- `analysis_outcomes` - Post-analysis performance tracking
- `calibration_snapshots` - Reliability metrics over time
- `confidence_reliability_bins` - Binned accuracy by confidence level

---

## Configuration

Configuration is environment-driven via `.env` file, loaded in `src/config.py`.

### Required API Keys
- At least one LLM provider:
  - `ANTHROPIC_API_KEY` (for anthropic provider)
  - `OPENAI_API_KEY` (for openai provider)
  - `GROK_API_KEY` (for xai provider)

### Optional API Keys
- `ALPHA_VANTAGE_API_KEY` - Primary market data source
- `NEWS_API_KEY` - News fallback
- `TWITTER_BEARER_TOKEN` - Social sentiment

### Key Feature Flags
| Flag | Default | Description |
|------|---------|-------------|
| `TAVILY_ENABLED` | true | Enable Tavily AI search integration |
| `TAVILY_NEWS_ENABLED` | true | Use Tavily as primary news source |
| `TAVILY_CONTEXT_ENABLED` | true | Enable contextual research for fundamentals |
| `TAVILY_MAX_RESULTS` | 20 | Max news articles per search |
| `TAVILY_NEWS_DAYS` | 7 | Lookback period for news |
| `TAVILY_SEARCH_DEPTH` | advanced | Search depth: basic or advanced |
| `SIGNAL_CONTRACT_V2_ENABLED` | false | EV scores, calibrated confidence, regime labels |
| `COT_PERSISTENCE_ENABLED` | false | Store full chain-of-thought in DB |
| `PORTFOLIO_OPTIMIZER_V2_ENABLED` | false | Advanced position sizing optimizer |
| `CALIBRATION_ECONOMICS_ENABLED` | false | Net-return calibration tracking |
| `ALERTS_V2_ENABLED` | false | EV/regime/data-quality alert types |
| `WATCHLIST_RANKING_ENABLED` | false | EV-ranked watchlist ordering |
| `SCHEDULER_ENABLED` | true | Background scheduled analysis |
| `MACRO_AGENT_ENABLED` | true | Macro-economic data agent |
| `OPTIONS_AGENT_ENABLED` | true | Options flow agent |

### Scheduled-Run Overrides
Flags for safe staged rollout (enable v2 for scheduled runs only):
- `SCHEDULED_SIGNAL_CONTRACT_V2_ENABLED`
- `SCHEDULED_CALIBRATION_ECONOMICS_ENABLED`
- `SCHEDULED_PORTFOLIO_OPTIMIZER_V2_ENABLED`
- `SCHEDULED_ALERTS_V2_ENABLED`

---

## Code Style Guidelines

### Python
- **Type hints**: Use for function signatures and key variables
- **Docstrings**: Google style for all public methods
- **Async/await**: Prefer async for I/O; wrap blocking calls with `asyncio.to_thread()`
- **Error handling**: Fail-open for external services; log warnings
- **Imports**: Group as stdlib → third-party → local

### JavaScript/React
- **Components**: PascalCase, one component per file
- **Hooks**: camelCase, prefix with `use`
- **Props destructuring**: Explicit prop listing
- **State management**: Use AnalysisContext for global state

---

## Development Conventions

### Agent Development
1. Inherit from `BaseAgent` in `src/agents/base_agent.py`
2. Implement `fetch_data()` and `analyze()` abstract methods
3. Use `_av_request()` for Alpha Vantage calls (handles rate limiting, caching)
4. Preserve `data_source` metadata in outputs for provenance
5. Dependencies declared in `Orchestrator.AGENT_REGISTRY`

### Database Changes
- Schema changes live in `src/database.py`
- Migrations are manual and idempotent
- Use `CREATE TABLE IF NOT EXISTS` pattern
- Add new columns with `DEFAULT` values for compatibility

### API Changes
- Use Pydantic models in `src/models.py` for validation
- Maintain backward compatibility for response shapes
- Version schema changes via `analysis_schema_version` field
- SSE events: use `progress`, `result`, `error` (stable names)

### Testing
- Mock external API calls (use fixtures in `conftest.py`)
- Test both success and failure paths
- Use `aioresponses` for aiohttp mocking
- Database tests use `:memory:` or temp files

---

## Security Considerations

### API Keys
- Never commit `.env` file
- API keys validated at startup in `Config.validate_config()`
- Keys not logged or exposed in responses

### Data Handling
- SQLite uses WAL mode (`PRAGMA journal_mode=WAL`)
- Busy timeout set to 5 seconds to prevent locks
- Ticker validation before processing (regex + yfinance check)

### Docker
- Non-root containers where possible
- Backend health check endpoint for orchestration
- Frontend nginx doesn't expose server version

### Rate Limiting
- Alpha Vantage: per-minute and per-day limits enforced
- In-flight request coalescing prevents duplicate API calls

---

## Common Tasks

### Add a New Agent
1. Create file in `src/agents/{name}_agent.py`
2. Inherit from `BaseAgent`
3. Implement `fetch_data()` and `analyze()`
4. Register in `Orchestrator.AGENT_REGISTRY` with dependencies
5. Add tests in `tests/test_agents/`

### Add a New API Endpoint
1. Add Pydantic models to `src/models.py` if needed
2. Implement route in `src/api.py`
3. Add tests in `tests/test_api.py`
4. Update root endpoint documentation

### Database Migration
1. Add CREATE/ALTER statements to `DatabaseManager.initialize_database()`
2. Ensure idempotent (IF NOT EXISTS, OR IGNORE)
3. Test with existing database file
4. Document in commit message

### Feature Flag Rollout
1. Add flag to `src/config.py` with safe default
2. Add to `.env.example` with documentation
3. Gate feature usage behind flag check
4. Add canary test in `src/rollout_canary.py`
5. Document in rollout plan

---

## External Dependencies

### Data Sources
- **Alpha Vantage**: Primary market data (rate limited: 5/min, 25/day free tier)
- **yfinance**: Fallback market data, ticker validation
- **NewsAPI**: News fallback
- **SEC EDGAR**: Fundamentals fallback
- **Twitter/X API v2**: Social sentiment

### AI-Powered Research (Tavily)
- **News Enhancement** - Primary news source with full content extraction and AI summaries
- **Company Context** - Recent developments between earnings (products, leadership, risks, guidance)
- **Market Narrative** - External research on analyst sentiment and price drivers

### LLM Providers
- **Anthropic**: Claude models (recommended: claude-3-5-sonnet)
- **OpenAI**: GPT models
- **xAI**: Grok models (OpenAI-compatible client)

---

## Tavily AI Search Integration

Tavily provides AI-powered search capabilities that enhance the platform's research quality through three integration phases:

### Phase 1: Enhanced News (NewsAgent)
**File**: `src/agents/news_agent.py`
- Tavily is the **primary news source** (fallback to AV/NewsAPI if unavailable)
- Provides superior relevance scoring vs keyword-based NewsAPI
- Full article content extraction (not just snippets)
- AI-generated summaries (`tavily_summary`) included in news output
- No rate limiting issues (unlike Alpha Vantage 5/min)

**Configuration**:
```bash
TAVILY_ENABLED=true
TAVILY_NEWS_ENABLED=true
TAVILY_MAX_RESULTS=20
TAVILY_NEWS_DAYS=7
TAVILY_SEARCH_DEPTH=advanced  # or 'basic' for faster results
```

### Phase 2: Company Context (FundamentalsAgent)
**File**: `src/agents/fundamentals_agent.py`
- Fetches recent developments between quarterly earnings
- Categories: earnings highlights, product news, leadership changes, risks, guidance
- Provides context that may not appear in financial statements yet
- Stored in `tavily_context` field of fundamentals analysis

**Configuration**:
```bash
TAVILY_CONTEXT_ENABLED=true
```

### Phase 3: Market Narrative (SolutionAgent)
**File**: `src/agents/solution_agent.py`
- External market narrative research before LLM synthesis
- Searches for: analyst upgrades/downgrades, price target changes, "why stock is up/down today"
- Fed into LLM prompt as "Market Narrative (Tavily External Research)" section
- Helps ground AI reasoning in current market sentiment

### Shared Client
**File**: `src/tavily_client.py`
- Reusable async client wrapper for Tavily API
- Methods:
  - `search_news()` - Primary news search
  - `search_company_context()` - Multi-dimensional company research
  - `get_market_narrative()` - Market sentiment research
  - `extract_article_content()` - Deep content extraction

### Getting Started
1. Sign up at [tavily.com](https://tavily.com) (free tier available)
2. Add `TAVILY_API_KEY=your_key_here` to `.env`
3. Tavily automatically becomes the primary news source
4. Check diagnostics output to verify Tavily is being used:
   ```json
   {"tavily": {"enabled": true, "agents_using": ["news", "fundamentals"]}}
   ```

---

## Troubleshooting

### "Database is locked"
- WAL mode enabled by default
- Check for long-running transactions
- Increase `busy_timeout` if needed

### Alpha Vantage rate limit
- Check `AV_RATE_LIMIT_PER_MINUTE` / `AV_RATE_LIMIT_PER_DAY` settings
- Cache TTL may need adjustment
- Consider yfinance fallback

### Frontend can't connect to backend
- Check `VITE_API_URL` in frontend environment
- Verify CORS_ORIGINS includes frontend URL
- Check docker-compose networking

### Tests failing with API errors
- Ensure test config uses mock responses
- Check `conftest.py` fixtures are being used
- Mark real API tests with `@pytest.mark.slow`

### Tavily not being used
- Check `TAVILY_API_KEY` is set in `.env`
- Verify `TAVILY_ENABLED=true` and relevant feature flags
- Check diagnostics: `data_quality.tavily` in analysis output
- Tavily gracefully falls back to NewsAPI/AV if unavailable
