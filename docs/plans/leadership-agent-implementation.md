# Leadership Evaluation Agent Implementation Plan

## Executive Summary

This document details the implementation of the **Leadership Evaluation Agent** for the Multi-Agent Market Research Platform. The agent evaluates company leadership quality using the **Four Capitals Framework** (Athena Alliance / McKinsey) and provides a structured scorecard with red flag detection.

**Status:** ✅ Completed  
**Implementation Date:** February 2026  
**Scope:** Backend agent, frontend dashboard tab, database schema, API integration

---

## Research Foundation

### Four Capitals Framework (Athena Alliance / McKinsey)

High-performing CEOs excel across four domains:

| Capital | Description | Key Indicators |
|---------|-------------|----------------|
| **Individual** | Self-reflection, vision clarity, cognitive focus, diverse experiences | CEO tenure, background, track record, education |
| **Relational** | Deep 1:1 relationships, behavioral integration at the top team | C-suite turnover, executive team stability |
| **Organizational** | Management rituals, accountability structures, culture hardwiring | Board independence, succession planning, governance |
| **Reputational** | Strategic storytelling, consistency between words and actions | ESG scores, external perception, compensation alignment |

### Supporting Research Areas

1. **CEO Performance Evaluation Dimensions**
   - Bottom-line Impact — Financial results, shareholder returns
   - Operational Impact — Customer satisfaction, product innovation, productivity
   - Leadership Effectiveness — Succession planning, stakeholder communication, organizational energy

2. **Board Assessment Best Practices (Spencer Stuart, Diligent)**
   - The "5 I's": Individuals, Information, Infrastructure, Innovation, Impact

3. **Leadership Assessment Methodology (Stanton Chase)**
   - Psychometric measurements, C-suite referencing, external benchmarking

4. **Red Flags to Watch**
   - High executive turnover (signals internal conflict)
   - Undisclosed related-party transactions
   - Key person dependencies (no succession plan)
   - Forecast variance >10% consistently
   - Poor cross-functional collaboration

---

## Implementation Architecture

### System Context

```
┌─────────────────────────────────────────────────────────────────┐
│                      Client (React)                              │
│                         │                                        │
│                         ▼                                        │
│              ┌──────────────────┐                               │
│              │  Leadership Tab  │                               │
│              └──────────────────┘                               │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FastAPI Backend                             │
│                         │                                        │
│                         ▼                                        │
│              ┌──────────────────┐                               │
│              │   Orchestrator   │                               │
│              └────────┬─────────┘                               │
│                       │                                          │
│         ┌─────────────┼─────────────┐                           │
│         ▼             ▼             ▼                           │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐                     │
│   │   News   │  │  Market  │  │Leadership│  ... other agents   │
│   │  Agent   │  │  Agent   │  │  Agent   │                     │
│   └──────────┘  └──────────┘  └────┬─────┘                     │
│                                    │                            │
│                                    ▼                            │
│                           ┌──────────────┐                      │
│                           │    Tavily    │                      │
│                           │  AI Search   │                      │
│                           └──────────────┘                      │
│                                                                 │
│  Leadership Agent Output:                                       │
│  - Four Capitals scorecard                                      │
│  - Red flag detection                                           │
│  - Executive summary                                            │
│  - Key metrics extraction                                       │
└─────────────────────────────────────────────────────────────────┘
```

---

## Technical Implementation

### Backend Components

#### 1. Leadership Agent (`src/agents/leadership_agent.py`)

**Class:** `LeadershipAgent(BaseAgent)`

**Research Queries (8 parallel searches):**
```python
RESEARCH_QUERIES = [
    "{company} {ticker} CEO background tenure experience education",
    "{company} {ticker} executive team C-suite management leadership",
    "{company} {ticker} board of directors independence composition",
    "{company} {ticker} CEO succession plan replacement",
    "{company} {ticker} executive compensation insider ownership equity",
    "{company} {ticker} leadership change CFO departure executive turnover",
    "{company} {ticker} corporate culture employee satisfaction Glassdoor",
    "{company} {ticker} ESG governance score rating board diversity",
]
```

**Red Flag Detection Patterns:**
```python
RED_FLAG_PATTERNS = {
    "high_turnover": ["cfo resigned", "executive departure", ...],
    "succession_risk": ["ceo nearing retirement", "no succession plan", ...],
    "governance_issue": ["board conflict", "sec investigation", ...],
    "compensation_concern": ["excessive compensation", "pay misalignment", ...],
    "ethical_concern": ["workplace harassment", "toxic culture", ...],
}
```

**Grade Calculation:**
| Score Range | Grade |
|-------------|-------|
| 97-100 | A+ |
| 93-96 | A |
| 90-92 | A- |
| 87-89 | B+ |
| 83-86 | B |
| 80-82 | B- |
| 77-79 | C+ |
| 73-76 | C |
| 70-72 | C- |
| 60-69 | D |
| <60 | F |

#### 2. Pydantic Models (`src/models.py`)

```python
class LeadershipCapitalScore(BaseModel):
    score: float  # 0-100
    grade: str    # A+ through F
    insights: List[str]
    red_flags: List[str]

class LeadershipRedFlag(BaseModel):
    type: str      # high_turnover, succession_risk, etc.
    severity: str  # low, medium, high, critical
    description: str
    source: str

class LeadershipKeyMetrics(BaseModel):
    ceo_tenure_years: Optional[float]
    c_suite_turnover_12m: Optional[int]
    c_suite_turnover_24m: Optional[int]
    board_independence_pct: Optional[float]
    avg_board_tenure_years: Optional[float]
    institutional_ownership_pct: Optional[float]

class LeadershipScorecard(BaseModel):
    overall_score: float
    grade: str
    assessment_date: str
    four_capitals: Dict[str, LeadershipCapitalScore]
    key_metrics: LeadershipKeyMetrics
    red_flags: List[LeadershipRedFlag]
    executive_summary: str
    data_source: str
    research_queries: List[str]
```

#### 3. Database Schema (`src/database.py`)

**Table:** `leadership_scores`
```sql
CREATE TABLE leadership_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_id INTEGER NOT NULL,
    ticker TEXT NOT NULL,
    overall_score REAL,
    grade TEXT,
    individual_capital_score REAL,
    relational_capital_score REAL,
    organizational_capital_score REAL,
    reputational_capital_score REAL,
    key_metrics_json TEXT,
    red_flags_json TEXT,
    executive_summary TEXT,
    data_source TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (analysis_id) REFERENCES analyses(id)
);

CREATE INDEX idx_leadership_analysis_id ON leadership_scores(analysis_id);
CREATE INDEX idx_leadership_ticker ON leadership_scores(ticker);
```

**Methods Added:**
- `insert_leadership_score(analysis_id, ticker, scorecard_data)`
- `get_leadership_score(analysis_id)`
- `get_leadership_history(ticker, limit)`

#### 4. Orchestrator Integration (`src/orchestrator.py`)

**Agent Registry:**
```python
AGENT_REGISTRY = {
    # ... existing agents
    "leadership": {"class": LeadershipAgent, "requires": []},
}

DEFAULT_AGENTS = [
    "news", "market", "fundamentals", "technical", 
    "macro", "options", "leadership", "sentiment"
]
```

**Progress Map:**
```python
progress_map = {
    # ... existing mappings
    "leadership": 62,  # Between options (57) and technical (60)
}
```

---

### Frontend Components

#### 1. Leadership Panel (`frontend/src/components/LeadershipPanel.jsx`)

**Features:**
- **Grade Badge:** Large colored badge (A = green, B = blue, C = yellow, D/F = red)
- **Score Display:** Overall score (0-100) with animated progress bar
- **Red Flags Panel:** Prominent warning display with severity indicators
- **Four Capitals Grid:** 2x2 responsive grid showing all dimensions
- **Key Metrics Cards:** Horizontal row showing quantitative metrics
- **Executive Summary:** Collapsible narrative section

**Grade Color Coding:**
| Grade | Color Class | Hex |
|-------|-------------|-----|
| A | `text-success` / `bg-success` | #22c55e |
| B | `text-accent-blue` / `bg-accent-blue` | #3b82f6 |
| C | `text-warning` / `bg-warning` | #eab308 |
| D/F | `text-danger` / `bg-danger` | #ef4444 |

#### 2. Analysis Tabs (`frontend/src/components/AnalysisTabs.jsx`)

Added Leadership tab to the navigation:
```javascript
const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'risk', label: 'Risks' },
  { id: 'opportunities', label: 'Opportunities' },
  { id: 'leadership', label: 'Leadership' },  // NEW
  { id: 'diagnostics', label: 'Diagnostics' },
];
```

#### 3. Dashboard Integration (`frontend/src/components/Dashboard.jsx`)

Added Leadership tab content rendering with Framer Motion animations.

---

## Output Schema

### Complete Leadership Scorecard

```json
{
  "overall_score": 78,
  "grade": "B+",
  "assessment_date": "2026-02-20T20:00:00Z",
  "four_capitals": {
    "individual": {
      "score": 82,
      "grade": "A-",
      "insights": [
        "CEO has 13+ years tenure with strong operational background",
        "Proven track record of strategic transformation"
      ],
      "red_flags": []
    },
    "relational": {
      "score": 75,
      "grade": "B",
      "insights": [
        "Low C-suite turnover over past 24 months",
        "Strong executive team cohesion"
      ],
      "red_flags": [
        "Recent CFO departure within 18 months"
      ]
    },
    "organizational": {
      "score": 71,
      "grade": "B-",
      "insights": [
        "85% independent board members",
        "Clear succession planning framework"
      ],
      "red_flags": [
        "Recent restructuring may impact accountability structures"
      ]
    },
    "reputational": {
      "score": 84,
      "grade": "A-",
      "insights": [
        "High ESG governance scores",
        "Consistent strategic communication",
        "Strong external stakeholder relationships"
      ],
      "red_flags": []
    }
  },
  "key_metrics": {
    "ceo_tenure_years": 13.2,
    "c_suite_turnover_12m": 1,
    "c_suite_turnover_24m": 2,
    "board_independence_pct": 85,
    "avg_board_tenure_years": 7.5,
    "institutional_ownership_pct": 72
  },
  "red_flags": [
    {
      "type": "high_turnover",
      "severity": "medium",
      "description": "CFO departed within 18 months, indicating potential internal conflict",
      "source": "news_search"
    }
  ],
  "executive_summary": "Strong leadership team with demonstrated track record of execution. CEO tenure of 13+ years provides stability, while recent CFO departure warrants monitoring. Board governance is solid with 85% independent directors and clear succession planning.",
  "data_source": "tavily",
  "research_queries": [
    "Apple AAPL CEO background tenure experience education",
    "Apple AAPL executive team C-suite management leadership",
    ...
  ],
  "article_count": 24
}
```

---

## Testing

### Test Coverage (`tests/test_agents/test_leadership_agent.py`)

**Unit Tests:**
- `test_fetch_data_success()` — Tavily search integration
- `test_fetch_data_tavily_unavailable()` — Fallback handling
- `test_analyze_produces_scorecard()` — Output schema validation
- `test_analyze_detects_red_flags()` — Red flag detection
- `test_analyze_extracts_metrics()` — Metric extraction

**Grading Tests:**
- `test_grade_calculation_a_plus()` through `test_grade_calculation_f()`

**Red Flag Detection Tests:**
- `test_detect_high_turnover()`
- `test_detect_governance_issue()`
- `test_detect_succession_risk()`

**Integration Tests:**
- `test_integration_comprehensive_analysis()`
- `test_execute_success()`
- `test_execute_handles_errors()`

---

## Future Enhancements (Out of Scope)

The following features were identified as valuable additions but are out of scope for the initial implementation:

### 1. Insider Trading Analysis
- **Feature:** Track Form 4 SEC filings for executive buying/selling patterns
- **Value:** Detect executive conviction (buying) or concerns (selling)
- **Implementation:** Integrate with SEC EDGAR API for real-time filing alerts
- **Priority:** High

### 2. Social Sentiment Tracking
- **Feature:** Monitor CEO social media presence and sentiment
- **Value:** Real-time perception tracking, crisis detection
- **Implementation:** Twitter/X API v2 integration, sentiment analysis
- **Priority:** Medium

### 3. Compensation Analysis
- **Feature:** Compare executive pay to performance metrics
- **Value:** Pay-for-performance alignment assessment
- **Implementation:** Parse proxy statements (DEF 14A), compare to TSR
- **Priority:** Medium

### 4. Peer Benchmarking
- **Feature:** Compare leadership scores to industry peers
- **Value:** Relative leadership quality assessment
- **Implementation:** Cross-sectional analysis within sectors
- **Priority:** Medium

### 5. Historical Tracking
- **Feature:** Show leadership score trends over time
- **Value:** Detect deterioration or improvement patterns
- **Implementation:** Time-series analysis of stored leadership_scores
- **Priority:** Low

### 6. Board Member Deep Dive
- **Feature:** Individual board member profiles and track records
- **Value:** Assess board quality at individual level
- **Implementation:** LinkedIn/SEC data integration
- **Priority:** Low

### 7. Glassdoor Integration
- **Feature:** Real-time employee sentiment data
- **Value:** Organizational capital validation
- **Implementation:** Glassdoor API or web scraping
- **Priority:** Low

---

## Configuration

### Environment Variables

```bash
# Leadership Agent (optional - defaults to enabled)
LEADERSHIP_AGENT_ENABLED=true
LEADERSHIP_RESEARCH_DEPTH=advanced  # basic or advanced
```

### Feature Flag

The Leadership Agent is enabled by default. To disable:

```python
# In orchestrator or config
config["LEADERSHIP_AGENT_ENABLED"] = False
```

---

## API Usage

The Leadership Agent primarily uses:

1. **Tavily AI Search** — Leadership research (primary source)
2. **yfinance** — Company name lookup (fallback)
3. **LLM (Claude/OpenAI/xAI)** — Executive summary generation

**Rate Limit Impact:** Minimal (Tavily quotas separate from Alpha Vantage)

---

## Success Metrics

### Functional Success
- ✅ Leadership Agent executes successfully
- ✅ Four Capitals Framework scoring implemented
- ✅ Red flag detection working
- ✅ Frontend Leadership tab displays data
- ✅ Database persistence working
- ✅ Tests passing

### Quality Metrics
- Leadership scores correlate with known strong/weak leadership
- Red flags match documented executive changes
- Grade distribution follows bell curve (mostly B-range)
- Executive summaries are coherent and relevant

---

## References

1. **Athena Alliance / McKinsey** — Four Capitals Framework
2. **Spencer Stuart** — Board Effectiveness: The 5 I's
3. **Diligent** — Board Assessment Best Practices
4. **Stanton Chase** — Leadership Assessment Methodology

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-02-20 | AI Assistant | Initial implementation completed |

---

## Related Files

- `src/agents/leadership_agent.py` — Agent implementation
- `src/models.py` — Pydantic models
- `src/database.py` — Database schema and methods
- `src/orchestrator.py` — Agent registration
- `frontend/src/components/LeadershipPanel.jsx` — UI component
- `frontend/src/components/AnalysisTabs.jsx` — Tab navigation
- `frontend/src/components/Dashboard.jsx` — Integration
- `tests/test_agents/test_leadership_agent.py` — Test suite
