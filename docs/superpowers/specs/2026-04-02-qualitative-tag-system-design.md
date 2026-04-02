# Qualitative Tag System — Company Tagging & Screening

**Date:** 2026-04-02
**Status:** Approved
**Context:** CapRelay feature replication — fourth of 5 planned features

---

## Overview

A qualitative tagging system that automatically assigns predefined tags to companies during analysis (e.g., "recurring_revenue", "activist_involved", "pricing_power") and exposes a screening API to filter companies by tag combinations. Tags are extracted by a lightweight synthesis agent running in parallel, persisted via upsert (never auto-deleted), and queryable with recency filters.

---

## Architecture Decisions

| # | Decision | Choice | Alternatives |
|---|----------|--------|-------------|
| 1 | Scope | Single spec — DB + agent + API | Split DB/agent from API |
| 2 | Extraction timing | Lightweight synthesis agent (5th in gather) | Post-synthesis step; embedded in solution prompt |
| 3 | Tag taxonomy | Fixed (~35 predefined tags) | Open-ended; fixed + LLM extras |
| 4 | Tag confidence | Binary with evidence (no numeric score) | LLM confidence; LLM + guardrail clamp |
| 5 | Tag persistence | Upsert with last_seen, never auto-delete | Replace all each run; accumulate with stale threshold |
| 6 | Screening filters | Tags + recency (max_age_days) | Tags only; tags + fundamentals filters |

Full rationale in memory: `project_caprelay_tag_system_decisions.md`

---

## Database Schema

New table in `src/database.py` `initialize_database()`:

```sql
CREATE TABLE IF NOT EXISTS company_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    tag TEXT NOT NULL,
    category TEXT NOT NULL,
    evidence TEXT,
    source_agent TEXT DEFAULT 'tag_extractor',
    analysis_id INTEGER,
    first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ticker, tag)
);
CREATE INDEX IF NOT EXISTS idx_company_tags_ticker ON company_tags(ticker);
CREATE INDEX IF NOT EXISTS idx_company_tags_tag ON company_tags(tag);
CREATE INDEX IF NOT EXISTS idx_company_tags_category ON company_tags(category);
```

### DB Methods

**`upsert_company_tags(ticker, tags, analysis_id)`**
- `tags` is a list of `{"tag": str, "category": str, "evidence": str}`
- For each tag: `INSERT OR REPLACE` with updated `last_seen` and `evidence`
- Preserves `first_seen` on update (use `COALESCE` with existing value)

**`get_company_tags(ticker)`**
- Returns all tags for a ticker, ordered by category then tag name
- Includes `first_seen`, `last_seen`, `evidence`

**`screen_by_tags(tags, max_age_days=None)`**
- Finds tickers that have ALL specified tags
- If `max_age_days` is set, only counts tags where `last_seen >= now - max_age_days`
- Returns list of `{"ticker": str, "matching_tags": int, "total_tags": int}`

---

## Tag Taxonomy

```python
TAG_TAXONOMY = {
    "business_model": [
        "recurring_revenue", "transaction_based", "advertising_model",
        "platform_business", "hardware_dependent", "services_led",
        "subscription_transition",
    ],
    "corporate_events": [
        "activist_involved", "recent_ceo_change", "recent_cfo_change",
        "major_acquisition", "divestiture_underway", "restructuring",
        "ipo_recent", "spac_merger",
    ],
    "growth_drivers": [
        "pricing_power", "new_product_launch", "geographic_expansion",
        "market_share_gains", "cross_sell_opportunity", "ai_integration",
        "digital_transformation",
    ],
    "risk_flags": [
        "customer_concentration", "regulatory_risk", "debt_heavy",
        "margin_compression", "competitive_threat", "secular_decline",
        "accounting_concerns",
    ],
    "quality_indicators": [
        "high_insider_ownership", "consistent_buybacks", "dividend_grower",
        "strong_free_cash_flow", "high_roic", "network_effects",
        "switching_costs",
    ],
}

ALL_TAGS = {tag for tags in TAG_TAXONOMY.values() for tag in tags}  # 36 tags
TAG_TO_CATEGORY = {tag: cat for cat, tags in TAG_TAXONOMY.items() for tag in tags}
```

---

## TagExtractorAgent

Lightweight synthesis agent — single LLM call.

### Constructor

`__init__(ticker, config, agent_results)` — same pattern as all synthesis agents.

### fetch_data()

Returns `agent_results` as-is.

### analyze()

1. Extract concise context from agent_results:
   - Solution: recommendation, summary, key risks/opportunities
   - Fundamentals: sector, revenue, margins, business description
   - News: top 3 headlines
   - Thesis: bull/bear thesis summaries (if available)
2. Single LLM call with full taxonomy + context
3. Validate returned tags against `ALL_TAGS` (discard any not in taxonomy)
4. Return tag list

### LLM Prompt

```
You are a senior equity research analyst classifying a company based on qualitative attributes.

Given the analysis data below, select ALL tags that apply from the predefined taxonomy.
For each tag you select, provide a brief evidence string (1 sentence) explaining why.

ONLY select tags from this list — do not invent new tags:

[full taxonomy grouped by category]

Return JSON: {"tags": [{"tag": "tag_name", "category": "category_name", "evidence": "why"}]}

--- COMPANY ANALYSIS ---
[concise context]
```

### Output

```python
{
    "tags": [
        {"tag": "recurring_revenue", "category": "business_model", "evidence": "Services at 28% of revenue with high retention"},
        {"tag": "ai_integration", "category": "growth_drivers", "evidence": "AI assistant launched, R&D up 30%"},
    ],
    "tags_count": 2,
    "data_sources_used": ["fundamentals", "solution", "news"],
}
```

---

## API Endpoints

### `GET /api/screen`

Query params:
- `tags` (required): comma-separated tag names
- `max_age_days` (optional): only include tags seen within N days

Response:
```json
{
    "tags_queried": ["recurring_revenue", "pricing_power"],
    "max_age_days": 90,
    "results": [
        {"ticker": "AAPL", "matching_tags": 2, "total_tags": 8, "tags": [...]},
        {"ticker": "MSFT", "matching_tags": 2, "total_tags": 6, "tags": [...]}
    ],
    "count": 2
}
```

### `GET /api/tags/{ticker}`

Response:
```json
{
    "ticker": "AAPL",
    "tags": [
        {"tag": "recurring_revenue", "category": "business_model", "evidence": "...", "first_seen": "...", "last_seen": "..."},
    ],
    "count": 8
}
```

### `POST /api/tags/{ticker}`

Body:
```json
{
    "add": [{"tag": "activist_involved", "evidence": "Carl Icahn disclosed 5% stake"}],
    "remove": ["ipo_recent"]
}
```

Validates tags against `ALL_TAGS`. Returns updated tag list.

---

## Orchestrator Integration

### Synthesis Phase (5-way gather)

```python
final_analysis, thesis_result, earnings_review_result, narrative_result, tag_result = await asyncio.gather(
    self._run_solution_agent(ticker, agent_results),
    self._run_thesis_agent(ticker, agent_results),
    self._run_earnings_review_agent(ticker, agent_results),
    self._run_narrative_agent(ticker, agent_results),
    self._run_tag_extractor_agent(ticker, agent_results),
)
```

### Post-DB-Save Phase (tag persistence)

After `analysis_id` is available (same phase as perception snapshots):

```python
if analysis_id and tag_result:
    try:
        self.db_manager.upsert_company_tags(
            ticker, tag_result.get("tags", []), analysis_id
        )
    except Exception as e:
        self.logger.warning(f"Tag save failed: {e}")
```

Tags are NOT attached to `final_analysis` — they're persisted to their own table and queried via the API.

---

## File Changes

| File | Change | Lines (est.) |
|------|--------|-------------|
| `src/agents/tag_extractor_agent.py` | **New.** Lightweight LLM agent, fixed taxonomy, tag extraction. | ~150 |
| `src/database.py` | Add `company_tags` table, `upsert_company_tags()`, `get_company_tags()`, `screen_by_tags()`. | ~60 |
| `src/models.py` | Add `CompanyTag`, `TagExtractorOutput` models. | ~20 |
| `src/api.py` | Add 3 endpoints: `/api/screen`, `/api/tags/{ticker}` GET/POST. | ~60 |
| `src/orchestrator.py` | Import, registry, `_run_tag_extractor_agent()`, expand gather to 5, save tags post-DB. | ~40 |
| `tests/test_agents/test_tag_extractor_agent.py` | **New.** Taxonomy validation, LLM mocking, tag filtering. | ~120 |
| `tests/test_database.py` | Add tests for upsert, get, screen_by_tags. | ~50 |
| `tests/test_orchestrator.py` | Update synthesis tests for 5 parallel agents. | ~15 |

### Not in Scope
- Frontend screening UI
- Tag visualization in dashboard
- README/CLAUDE.md updates (after implementation)
