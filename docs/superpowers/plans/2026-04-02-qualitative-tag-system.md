# Qualitative Tag System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a qualitative tagging system that automatically classifies companies with predefined tags during analysis and exposes a screening API to filter companies by tag combinations.

**Architecture:** TagExtractorAgent (lightweight LLM synthesis agent) runs as 5th agent in synthesis gather. Tags persist to `company_tags` SQLite table via upsert (never auto-deleted). Three new API endpoints: screen by tags, get tags for ticker, manual tag CRUD. Fixed taxonomy of 36 tags across 5 categories.

**Tech Stack:** Python, SQLite, FastAPI, Pydantic, anthropic/openai SDKs, pytest

**Spec:** `docs/superpowers/specs/2026-04-02-qualitative-tag-system-design.md`

---

### Task 1: Pydantic Models

**Files:**
- Modify: `src/models.py`
- Create: `tests/test_agents/test_tag_extractor_agent.py`

- [ ] **Step 1: Create test file with model validation tests**

Create `tests/test_agents/test_tag_extractor_agent.py`:

```python
"""Tests for TagExtractorAgent — models, taxonomy, LLM flow."""

import pytest
from pydantic import ValidationError
from src.models import CompanyTag, TagExtractorOutput


class TestTagModels:
    """Pydantic model validation tests."""

    def test_company_tag_valid(self):
        tag = CompanyTag(
            tag="recurring_revenue",
            category="business_model",
            evidence="Services revenue 28% of total with high retention.",
        )
        assert tag.tag == "recurring_revenue"
        assert tag.category == "business_model"

    def test_company_tag_no_evidence(self):
        tag = CompanyTag(
            tag="debt_heavy",
            category="risk_flags",
        )
        assert tag.evidence is None

    def test_tag_extractor_output_valid(self):
        output = TagExtractorOutput(
            tags=[
                CompanyTag(tag="recurring_revenue", category="business_model", evidence="High retention."),
                CompanyTag(tag="ai_integration", category="growth_drivers", evidence="AI launched."),
            ],
            tags_count=2,
            data_sources_used=["fundamentals", "solution"],
        )
        assert output.tags_count == 2
        assert len(output.tags) == 2

    def test_tag_extractor_output_empty(self):
        output = TagExtractorOutput(
            tags=[],
            tags_count=0,
            data_sources_used=[],
        )
        assert output.tags_count == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_agents/test_tag_extractor_agent.py -v`
Expected: FAIL — `ImportError: cannot import name 'CompanyTag' from 'src.models'`

- [ ] **Step 3: Add Pydantic models to src/models.py**

Add at the end of `src/models.py`, after the Narrative Agent models section:

```python
# ── Tag Extractor Agent models ────────────────────────────────────────────────


class CompanyTag(BaseModel):
    """A single qualitative tag assigned to a company."""
    tag: str = Field(..., description="Tag name from taxonomy, e.g. 'recurring_revenue'")
    category: str = Field(..., description="Category: business_model, corporate_events, etc.")
    evidence: Optional[str] = Field(default=None, description="Brief evidence string")


class TagExtractorOutput(BaseModel):
    """Output from the tag extractor agent."""
    tags: List[CompanyTag] = Field(default=[], description="Extracted tags")
    tags_count: int = Field(default=0, description="Number of tags extracted")
    data_sources_used: List[str] = Field(default=[], description="Which agents contributed context")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_agents/test_tag_extractor_agent.py::TestTagModels -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/models.py tests/test_agents/test_tag_extractor_agent.py
git commit -m "feat(tags): add CompanyTag and TagExtractorOutput Pydantic models"
```

---

### Task 2: Database — company_tags Table & Methods

**Files:**
- Modify: `src/database.py`
- Modify: `tests/test_database.py`

- [ ] **Step 1: Write database tests**

Append to `tests/test_database.py`:

```python
from datetime import datetime, timedelta


class TestCompanyTags:
    """Tests for company_tags table and methods."""

    def test_company_tags_table_exists(self, db_manager, tmp_db_path):
        """company_tags table is created on initialization."""
        import sqlite3
        conn = sqlite3.connect(tmp_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='company_tags'")
        assert cursor.fetchone() is not None
        conn.close()

    def test_upsert_inserts_new_tags(self, db_manager):
        tags = [
            {"tag": "recurring_revenue", "category": "business_model", "evidence": "High retention"},
            {"tag": "pricing_power", "category": "growth_drivers", "evidence": "Strong moat"},
        ]
        db_manager.upsert_company_tags("AAPL", tags, analysis_id=1)
        result = db_manager.get_company_tags("AAPL")
        assert len(result) == 2
        tag_names = {t["tag"] for t in result}
        assert "recurring_revenue" in tag_names
        assert "pricing_power" in tag_names

    def test_upsert_updates_existing_tag(self, db_manager):
        tags1 = [{"tag": "recurring_revenue", "category": "business_model", "evidence": "Old evidence"}]
        db_manager.upsert_company_tags("AAPL", tags1, analysis_id=1)

        tags2 = [{"tag": "recurring_revenue", "category": "business_model", "evidence": "New evidence"}]
        db_manager.upsert_company_tags("AAPL", tags2, analysis_id=2)

        result = db_manager.get_company_tags("AAPL")
        assert len(result) == 1
        assert result[0]["evidence"] == "New evidence"
        assert result[0]["analysis_id"] == 2

    def test_upsert_preserves_first_seen(self, db_manager):
        tags = [{"tag": "debt_heavy", "category": "risk_flags", "evidence": "High leverage"}]
        db_manager.upsert_company_tags("AAPL", tags, analysis_id=1)
        result1 = db_manager.get_company_tags("AAPL")
        first_seen_1 = result1[0]["first_seen"]

        # Upsert again — first_seen should NOT change
        db_manager.upsert_company_tags("AAPL", tags, analysis_id=2)
        result2 = db_manager.get_company_tags("AAPL")
        assert result2[0]["first_seen"] == first_seen_1

    def test_get_tags_empty_ticker(self, db_manager):
        result = db_manager.get_company_tags("UNKNOWN")
        assert result == []

    def test_get_tags_ordered_by_category(self, db_manager):
        tags = [
            {"tag": "pricing_power", "category": "growth_drivers", "evidence": "Moat"},
            {"tag": "recurring_revenue", "category": "business_model", "evidence": "Subs"},
            {"tag": "debt_heavy", "category": "risk_flags", "evidence": "Leverage"},
        ]
        db_manager.upsert_company_tags("AAPL", tags, analysis_id=1)
        result = db_manager.get_company_tags("AAPL")
        categories = [t["category"] for t in result]
        assert categories == sorted(categories)

    def test_screen_by_tags_finds_matching_tickers(self, db_manager):
        db_manager.upsert_company_tags("AAPL", [
            {"tag": "recurring_revenue", "category": "business_model", "evidence": "Subs"},
            {"tag": "pricing_power", "category": "growth_drivers", "evidence": "Moat"},
        ], analysis_id=1)
        db_manager.upsert_company_tags("MSFT", [
            {"tag": "recurring_revenue", "category": "business_model", "evidence": "Cloud"},
            {"tag": "pricing_power", "category": "growth_drivers", "evidence": "Enterprise"},
        ], analysis_id=2)
        db_manager.upsert_company_tags("TSLA", [
            {"tag": "recurring_revenue", "category": "business_model", "evidence": "FSD subs"},
        ], analysis_id=3)

        # Both tags required — TSLA only has one
        result = db_manager.screen_by_tags(["recurring_revenue", "pricing_power"])
        tickers = {r["ticker"] for r in result}
        assert "AAPL" in tickers
        assert "MSFT" in tickers
        assert "TSLA" not in tickers

    def test_screen_by_tags_single_tag(self, db_manager):
        db_manager.upsert_company_tags("AAPL", [
            {"tag": "recurring_revenue", "category": "business_model", "evidence": "Subs"},
        ], analysis_id=1)
        db_manager.upsert_company_tags("TSLA", [
            {"tag": "recurring_revenue", "category": "business_model", "evidence": "FSD"},
        ], analysis_id=2)

        result = db_manager.screen_by_tags(["recurring_revenue"])
        assert len(result) == 2

    def test_screen_by_tags_empty_result(self, db_manager):
        result = db_manager.screen_by_tags(["nonexistent_tag"])
        assert result == []

    def test_screen_by_tags_with_max_age(self, db_manager):
        db_manager.upsert_company_tags("AAPL", [
            {"tag": "recurring_revenue", "category": "business_model", "evidence": "Subs"},
        ], analysis_id=1)

        # Manually backdate last_seen to 100 days ago
        with db_manager.get_connection() as conn:
            old_date = (datetime.utcnow() - timedelta(days=100)).isoformat()
            conn.execute(
                "UPDATE company_tags SET last_seen = ? WHERE ticker = 'AAPL'",
                (old_date,)
            )

        # max_age_days=90 should exclude AAPL
        result = db_manager.screen_by_tags(["recurring_revenue"], max_age_days=90)
        assert len(result) == 0

        # max_age_days=120 should include AAPL
        result = db_manager.screen_by_tags(["recurring_revenue"], max_age_days=120)
        assert len(result) == 1

    def test_delete_company_tag(self, db_manager):
        db_manager.upsert_company_tags("AAPL", [
            {"tag": "recurring_revenue", "category": "business_model", "evidence": "Subs"},
            {"tag": "debt_heavy", "category": "risk_flags", "evidence": "Leverage"},
        ], analysis_id=1)

        db_manager.delete_company_tags("AAPL", ["debt_heavy"])
        result = db_manager.get_company_tags("AAPL")
        assert len(result) == 1
        assert result[0]["tag"] == "recurring_revenue"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_database.py::TestCompanyTags -v`
Expected: FAIL — `AttributeError: 'DatabaseManager' object has no attribute 'upsert_company_tags'`

- [ ] **Step 3: Add company_tags table to initialize_database()**

In `src/database.py`, in `initialize_database()`, add before the line `self._ensure_alert_rule_schema(cursor)` (around line 634):

```python
            # Company qualitative tags
            cursor.execute("""
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
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_company_tags_ticker ON company_tags(ticker)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_company_tags_tag ON company_tags(tag)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_company_tags_category ON company_tags(category)")
```

- [ ] **Step 4: Add DB methods**

Add to `DatabaseManager` class in `src/database.py`:

```python
    def upsert_company_tags(self, ticker: str, tags: list, analysis_id: int):
        """Upsert company tags — insert new, update existing (preserves first_seen)."""
        with self.get_connection() as conn:
            for tag_data in tags:
                conn.execute("""
                    INSERT INTO company_tags (ticker, tag, category, evidence, analysis_id, first_seen, last_seen)
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ON CONFLICT(ticker, tag) DO UPDATE SET
                        evidence = excluded.evidence,
                        analysis_id = excluded.analysis_id,
                        last_seen = CURRENT_TIMESTAMP
                """, (
                    ticker,
                    tag_data["tag"],
                    tag_data["category"],
                    tag_data.get("evidence"),
                    analysis_id,
                ))

    def get_company_tags(self, ticker: str) -> list:
        """Get all tags for a ticker, ordered by category then tag."""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT tag, category, evidence, source_agent, analysis_id,
                       first_seen, last_seen
                FROM company_tags
                WHERE ticker = ?
                ORDER BY category, tag
            """, (ticker,))
            return [
                {
                    "tag": row[0], "category": row[1], "evidence": row[2],
                    "source_agent": row[3], "analysis_id": row[4],
                    "first_seen": row[5], "last_seen": row[6],
                }
                for row in cursor.fetchall()
            ]

    def screen_by_tags(self, tags: list, max_age_days: int = None) -> list:
        """Find tickers that have ALL specified tags, with optional recency filter."""
        if not tags:
            return []
        placeholders = ",".join("?" * len(tags))
        age_clause = ""
        params = list(tags)
        if max_age_days is not None:
            age_clause = "AND last_seen >= datetime('now', ?)"
            params.append(f"-{max_age_days} days")
        params.append(len(tags))

        with self.get_connection() as conn:
            cursor = conn.execute(f"""
                SELECT ticker, COUNT(DISTINCT tag) as matching_tags
                FROM company_tags
                WHERE tag IN ({placeholders})
                {age_clause}
                GROUP BY ticker
                HAVING COUNT(DISTINCT tag) = ?
            """, params)
            rows = cursor.fetchall()

        results = []
        for row in rows:
            ticker = row[0]
            all_tags = self.get_company_tags(ticker)
            results.append({
                "ticker": ticker,
                "matching_tags": row[1],
                "total_tags": len(all_tags),
                "tags": all_tags,
            })
        return results

    def delete_company_tags(self, ticker: str, tags: list):
        """Delete specific tags for a ticker (manual removal)."""
        if not tags:
            return
        placeholders = ",".join("?" * len(tags))
        with self.get_connection() as conn:
            conn.execute(
                f"DELETE FROM company_tags WHERE ticker = ? AND tag IN ({placeholders})",
                [ticker] + list(tags),
            )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_database.py::TestCompanyTags -v`
Expected: All 12 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/database.py tests/test_database.py
git commit -m "feat(tags): add company_tags table with upsert, get, screen, and delete methods"
```

---

### Task 3: TagExtractorAgent

**Files:**
- Create: `src/agents/tag_extractor_agent.py`
- Modify: `tests/test_agents/test_tag_extractor_agent.py`

- [ ] **Step 1: Write agent tests**

Append to `tests/test_agents/test_tag_extractor_agent.py`:

```python
from src.agents.tag_extractor_agent import TagExtractorAgent, TAG_TAXONOMY, ALL_TAGS, TAG_TO_CATEGORY


def _make_agent_results():
    """Build mock agent_results for tag extraction."""
    return {
        "fundamentals": {
            "success": True,
            "data": {
                "company_name": "Apple Inc.",
                "sector": "Technology",
                "revenue": 383e9,
                "gross_margin": 0.46,
                "business_description": "Designs consumer electronics and software services.",
                "data_source": "fmp",
            },
        },
        "news": {
            "success": True,
            "data": {
                "articles": [
                    {"title": "Apple AI push accelerates", "summary": "New AI features announced."},
                    {"title": "Services hit all-time high", "summary": "Recurring revenue grows."},
                ],
                "data_source": "tavily",
            },
        },
    }


class TestTagTaxonomy:
    """Tests for the fixed tag taxonomy."""

    def test_taxonomy_has_5_categories(self):
        assert len(TAG_TAXONOMY) == 5

    def test_all_tags_count(self):
        assert len(ALL_TAGS) == 36

    def test_tag_to_category_mapping(self):
        assert TAG_TO_CATEGORY["recurring_revenue"] == "business_model"
        assert TAG_TO_CATEGORY["activist_involved"] == "corporate_events"
        assert TAG_TO_CATEGORY["pricing_power"] == "growth_drivers"
        assert TAG_TO_CATEGORY["debt_heavy"] == "risk_flags"
        assert TAG_TO_CATEGORY["high_roic"] == "quality_indicators"

    def test_no_duplicate_tags_across_categories(self):
        all_tags = []
        for tags in TAG_TAXONOMY.values():
            all_tags.extend(tags)
        assert len(all_tags) == len(set(all_tags))


class TestTagExtractorContext:
    """Tests for context building from agent results."""

    def test_builds_context_from_agent_results(self):
        agent = TagExtractorAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        context = agent._build_context()
        assert "Apple Inc." in context
        assert "Technology" in context

    def test_handles_missing_agents(self):
        agent = TagExtractorAgent("AAPL", {"llm_config": {}}, {})
        context = agent._build_context()
        assert "AAPL" in context  # At minimum, ticker should be present

    def test_validates_tags_against_taxonomy(self):
        agent = TagExtractorAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        raw_tags = [
            {"tag": "recurring_revenue", "category": "business_model", "evidence": "Subs"},
            {"tag": "made_up_tag", "category": "business_model", "evidence": "Fake"},
            {"tag": "pricing_power", "category": "growth_drivers", "evidence": "Moat"},
        ]
        valid = agent._filter_valid_tags(raw_tags)
        assert len(valid) == 2
        assert all(t["tag"] in ALL_TAGS for t in valid)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_agents/test_tag_extractor_agent.py::TestTagTaxonomy -v`
Expected: FAIL — `ImportError: cannot import name 'TagExtractorAgent'`

- [ ] **Step 3: Implement TagExtractorAgent**

Create `src/agents/tag_extractor_agent.py`:

```python
"""Tag extractor agent — lightweight LLM agent for qualitative company classification."""

import asyncio
import json
import re
from typing import Dict, Any, List, Optional

import anthropic
from openai import OpenAI

from .base_agent import BaseAgent

# ─── Tag Taxonomy ────────────────────────────────────────────────────────────

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

ALL_TAGS = {tag for tags in TAG_TAXONOMY.values() for tag in tags}
TAG_TO_CATEGORY = {tag: cat for cat, tags in TAG_TAXONOMY.items() for tag in tags}


class TagExtractorAgent(BaseAgent):
    """Lightweight agent that classifies companies with qualitative tags.

    Single LLM call with fixed taxonomy. Tags are validated against ALL_TAGS
    before returning. Runs in synthesis phase parallel with other agents.
    """

    def __init__(self, ticker: str, config: Dict[str, Any], agent_results: Dict[str, Any]):
        super().__init__(ticker, config)
        self.agent_results = agent_results

    async def fetch_data(self) -> Dict[str, Any]:
        return self.agent_results

    async def analyze(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        context = self._build_context()
        sources = self._get_available_sources()

        if not context.strip():
            return {"tags": [], "tags_count": 0, "data_sources_used": sources}

        try:
            prompt = self._build_prompt(context)
            llm_response = await self._call_llm(prompt)
            parsed = self._parse_llm_response(llm_response)
            raw_tags = parsed.get("tags", [])
        except Exception as e:
            self.logger.warning(f"Tag extraction failed for {self.ticker}: {e}")
            return {"tags": [], "tags_count": 0, "data_sources_used": sources}

        valid_tags = self._filter_valid_tags(raw_tags)

        return {
            "tags": valid_tags,
            "tags_count": len(valid_tags),
            "data_sources_used": sources,
        }

    # ─── Context Building ────────────────────────────────────────────────────

    def _build_context(self) -> str:
        """Build concise context string from agent results."""
        parts = [f"Ticker: {self.ticker}"]

        # Fundamentals
        fund = self._get_agent_data("fundamentals")
        if fund:
            parts.append(f"Company: {fund.get('company_name', self.ticker)}")
            parts.append(f"Sector: {fund.get('sector', 'N/A')}")
            rev = fund.get("revenue")
            if rev:
                parts.append(f"Revenue: ${rev/1e9:.1f}B")
            margin = fund.get("gross_margin")
            if margin is not None:
                parts.append(f"Gross Margin: {margin*100:.1f}%")
            desc = fund.get("business_description", "")
            if desc:
                parts.append(f"Business: {desc[:200]}")

        # Solution summary
        solution = self._get_agent_data("solution")
        if not solution:
            # Solution might be stored differently — check for recommendation/summary at top level
            pass
        if solution:
            parts.append(f"Recommendation: {solution.get('recommendation', 'N/A')}")
            summary = solution.get("summary", "")
            if summary:
                parts.append(f"Summary: {summary[:300]}")
            risks = solution.get("risks", [])
            if risks:
                parts.append(f"Risks: {'; '.join(risks[:3])}")
            opps = solution.get("opportunities", [])
            if opps:
                parts.append(f"Opportunities: {'; '.join(opps[:3])}")

        # News headlines
        news = self._get_agent_data("news")
        if news:
            articles = news.get("articles", [])[:3]
            headlines = [a.get("title", "") for a in articles if a.get("title")]
            if headlines:
                parts.append(f"Recent News: {'; '.join(headlines)}")

        # Thesis (if available)
        thesis_result = self.agent_results.get("thesis")
        if isinstance(thesis_result, dict) and not thesis_result.get("error"):
            bull = (thesis_result.get("bull_case") or {}).get("thesis", "")
            bear = (thesis_result.get("bear_case") or {}).get("thesis", "")
            if bull:
                parts.append(f"Bull Case: {bull[:200]}")
            if bear:
                parts.append(f"Bear Case: {bear[:200]}")

        return "\n".join(parts)

    def _get_agent_data(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """Safely extract data dict from an agent result."""
        result = self.agent_results.get(agent_name, {})
        if isinstance(result, dict) and result.get("success"):
            return result.get("data")
        return None

    def _get_available_sources(self) -> List[str]:
        """Get list of agents that contributed context."""
        sources = []
        for name in ("fundamentals", "news", "solution"):
            result = self.agent_results.get(name, {})
            if isinstance(result, dict) and result.get("success") and result.get("data"):
                sources.append(name)
        return sources

    # ─── Tag Validation ──────────────────────────────────────────────────────

    @staticmethod
    def _filter_valid_tags(raw_tags: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter tags to only those in the fixed taxonomy."""
        valid = []
        for t in raw_tags:
            tag_name = t.get("tag", "")
            if tag_name in ALL_TAGS:
                # Ensure category is correct
                t["category"] = TAG_TO_CATEGORY[tag_name]
                valid.append(t)
        return valid

    # ─── LLM Prompt ──────────────────────────────────────────────────────────

    def _build_prompt(self, context: str) -> str:
        """Build the LLM prompt with full taxonomy."""
        taxonomy_str = ""
        for category, tags in TAG_TAXONOMY.items():
            taxonomy_str += f"\n  {category}: {', '.join(tags)}"

        return f"""You are a senior equity research analyst classifying a company based on qualitative attributes.

Given the analysis data below, select ALL tags that apply from the predefined taxonomy.
For each tag you select, provide a brief evidence string (1 sentence) explaining why it applies.

ONLY select tags from this list — do NOT invent new tags:
{taxonomy_str}

Return a JSON object with EXACTLY this structure — no markdown, no explanation, just raw JSON:

{{"tags": [{{"tag": "tag_name", "category": "category_name", "evidence": "one sentence why"}}]}}

Rules:
- Only select tags supported by the data. Do not guess.
- Typically 3-8 tags per company. Do not over-tag.
- Evidence should cite specific data points, not vague claims.

--- COMPANY ANALYSIS ---
{context}
"""

    # ─── LLM Call ────────────────────────────────────────────────────────────

    async def _call_llm(self, prompt: str) -> str:
        """Call the configured LLM provider."""
        llm_config = self.config.get("llm_config", {})
        provider = llm_config.get("provider", "anthropic")
        if provider == "anthropic":
            return await self._call_anthropic(prompt, llm_config)
        elif provider in ("openai", "xai"):
            return await self._call_openai(prompt, llm_config)
        else:
            raise ValueError(f"Unsupported LLM provider: {provider!r}")

    async def _call_anthropic(self, prompt: str, llm_config: Dict[str, Any]) -> str:
        api_key = llm_config.get("api_key")
        if not api_key:
            raise ValueError("No Anthropic API key configured")
        client = anthropic.Anthropic(api_key=api_key)

        def _call():
            return client.messages.create(
                model=llm_config.get("model", "claude-3-5-sonnet-20241022"),
                max_tokens=llm_config.get("max_tokens", 2048),
                temperature=llm_config.get("temperature", 0.2),
                messages=[{"role": "user", "content": prompt}],
            )

        message = await asyncio.to_thread(_call)
        return message.content[0].text.strip()

    async def _call_openai(self, prompt: str, llm_config: Dict[str, Any]) -> str:
        api_key = llm_config.get("api_key")
        if not api_key:
            raise ValueError("No API key configured")
        kwargs = {}
        base_url = llm_config.get("base_url")
        if base_url:
            kwargs["base_url"] = base_url
        client = OpenAI(api_key=api_key, **kwargs)

        def _call():
            return client.chat.completions.create(
                model=llm_config.get("model", "gpt-4o"),
                max_tokens=llm_config.get("max_tokens", 2048),
                temperature=llm_config.get("temperature", 0.2),
                messages=[{"role": "user", "content": prompt}],
            )

        response = await asyncio.to_thread(_call)
        return response.choices[0].message.content.strip()

    # ─── Response Parsing ────────────────────────────────────────────────────

    @staticmethod
    def _parse_llm_response(raw: str) -> Dict[str, Any]:
        """Parse LLM JSON response, stripping markdown fences if present."""
        text = raw.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*\n?", "", text)
            text = re.sub(r"\n?```\s*$", "", text)
        return json.loads(text)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_agents/test_tag_extractor_agent.py -v`
Expected: All 11 tests PASS (4 model + 4 taxonomy + 3 context)

- [ ] **Step 5: Commit**

```bash
git add src/agents/tag_extractor_agent.py tests/test_agents/test_tag_extractor_agent.py
git commit -m "feat(tags): add TagExtractorAgent with fixed taxonomy, context building, and tag validation"
```

---

### Task 4: API Endpoints

**Files:**
- Modify: `src/api.py`
- Create: `tests/test_tag_api.py`

- [ ] **Step 1: Write API tests**

Create `tests/test_tag_api.py`:

```python
"""Tests for tag screening and CRUD API endpoints."""

import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from src.api import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def mock_db(monkeypatch):
    """Mock the db_manager on the app state."""
    mock = MagicMock()
    monkeypatch.setattr(app.state, "db_manager", mock, raising=False)
    # Also set app.state.db_manager for endpoints that use it
    if not hasattr(app.state, "db_manager"):
        app.state.db_manager = mock
    return mock


class TestScreenEndpoint:
    """Tests for GET /api/screen."""

    def test_screen_returns_matching_tickers(self, client, mock_db):
        mock_db.screen_by_tags.return_value = [
            {"ticker": "AAPL", "matching_tags": 2, "total_tags": 5, "tags": []},
        ]
        response = client.get("/api/screen?tags=recurring_revenue,pricing_power")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["results"][0]["ticker"] == "AAPL"
        mock_db.screen_by_tags.assert_called_once_with(
            ["recurring_revenue", "pricing_power"], max_age_days=None
        )

    def test_screen_with_max_age(self, client, mock_db):
        mock_db.screen_by_tags.return_value = []
        response = client.get("/api/screen?tags=recurring_revenue&max_age_days=90")
        assert response.status_code == 200
        mock_db.screen_by_tags.assert_called_once_with(
            ["recurring_revenue"], max_age_days=90
        )

    def test_screen_missing_tags_param(self, client):
        response = client.get("/api/screen")
        assert response.status_code == 422 or response.status_code == 400


class TestGetTagsEndpoint:
    """Tests for GET /api/tags/{ticker}."""

    def test_get_tags_returns_list(self, client, mock_db):
        mock_db.get_company_tags.return_value = [
            {"tag": "recurring_revenue", "category": "business_model", "evidence": "Subs",
             "first_seen": "2025-01-01", "last_seen": "2025-06-01"},
        ]
        response = client.get("/api/tags/AAPL")
        assert response.status_code == 200
        data = response.json()
        assert data["ticker"] == "AAPL"
        assert data["count"] == 1
        assert data["tags"][0]["tag"] == "recurring_revenue"

    def test_get_tags_empty(self, client, mock_db):
        mock_db.get_company_tags.return_value = []
        response = client.get("/api/tags/UNKNOWN")
        assert response.status_code == 200
        assert response.json()["count"] == 0


class TestPostTagsEndpoint:
    """Tests for POST /api/tags/{ticker}."""

    def test_add_tags(self, client, mock_db):
        mock_db.get_company_tags.return_value = [
            {"tag": "activist_involved", "category": "corporate_events", "evidence": "Icahn 5%",
             "first_seen": "2025-01-01", "last_seen": "2025-06-01"},
        ]
        response = client.post("/api/tags/AAPL", json={
            "add": [{"tag": "activist_involved", "evidence": "Carl Icahn disclosed 5% stake"}],
        })
        assert response.status_code == 200
        mock_db.upsert_company_tags.assert_called_once()

    def test_remove_tags(self, client, mock_db):
        mock_db.get_company_tags.return_value = []
        response = client.post("/api/tags/AAPL", json={
            "remove": ["ipo_recent"],
        })
        assert response.status_code == 200
        mock_db.delete_company_tags.assert_called_once_with("AAPL", ["ipo_recent"])

    def test_add_invalid_tag_rejected(self, client, mock_db):
        mock_db.get_company_tags.return_value = []
        response = client.post("/api/tags/AAPL", json={
            "add": [{"tag": "made_up_tag", "evidence": "Fake"}],
        })
        assert response.status_code == 400 or response.status_code == 422
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_tag_api.py -v`
Expected: FAIL — 404 for `/api/screen` (endpoint doesn't exist yet)

- [ ] **Step 3: Add API endpoints to src/api.py**

Add to `src/api.py` (after existing endpoint blocks, before the health check):

```python
# ─── Tag Screening & CRUD ────────────────────────────────────────────────────

from .agents.tag_extractor_agent import ALL_TAGS, TAG_TO_CATEGORY


@app.get("/api/screen")
async def screen_by_tags(tags: str, max_age_days: int = None):
    """Screen companies by qualitative tag combinations."""
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    if not tag_list:
        return JSONResponse(status_code=400, content={"error": "tags parameter required"})

    db = app.state.db_manager
    results = db.screen_by_tags(tag_list, max_age_days=max_age_days)

    return {
        "tags_queried": tag_list,
        "max_age_days": max_age_days,
        "results": results,
        "count": len(results),
    }


@app.get("/api/tags/{ticker}")
async def get_company_tags(ticker: str):
    """Get all qualitative tags for a company."""
    db = app.state.db_manager
    tags = db.get_company_tags(ticker.upper())
    return {
        "ticker": ticker.upper(),
        "tags": tags,
        "count": len(tags),
    }


@app.post("/api/tags/{ticker}")
async def update_company_tags(ticker: str, body: dict):
    """Manually add or remove tags for a company."""
    db = app.state.db_manager
    ticker = ticker.upper()

    # Add tags
    add_tags = body.get("add", [])
    if add_tags:
        # Validate all tags are in taxonomy
        invalid = [t["tag"] for t in add_tags if t.get("tag") not in ALL_TAGS]
        if invalid:
            return JSONResponse(
                status_code=400,
                content={"error": f"Invalid tags: {invalid}. Must be from predefined taxonomy."},
            )
        # Enrich with correct category
        enriched = []
        for t in add_tags:
            enriched.append({
                "tag": t["tag"],
                "category": TAG_TO_CATEGORY[t["tag"]],
                "evidence": t.get("evidence", "Manual tag"),
            })
        db.upsert_company_tags(ticker, enriched, analysis_id=None)

    # Remove tags
    remove_tags = body.get("remove", [])
    if remove_tags:
        db.delete_company_tags(ticker, remove_tags)

    # Return updated tags
    tags = db.get_company_tags(ticker)
    return {
        "ticker": ticker,
        "tags": tags,
        "count": len(tags),
    }
```

Note: `JSONResponse` should already be imported in `api.py`. If not, add: `from fastapi.responses import JSONResponse`

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_tag_api.py -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/api.py tests/test_tag_api.py
git commit -m "feat(tags): add /api/screen, /api/tags/{ticker} GET/POST endpoints"
```

---

### Task 5: Orchestrator Integration (5-way gather + tag persistence)

**Files:**
- Modify: `src/orchestrator.py`
- Modify: `tests/test_orchestrator.py`

- [ ] **Step 1: Write orchestrator integration tests**

Append to `tests/test_orchestrator.py`:

```python
class TestTagExtractorIntegration:
    """Tests for tag extractor integration in synthesis phase."""

    def test_tag_extractor_in_registry(self, test_config):
        orch = Orchestrator(config=test_config)
        assert "tag_extractor" in orch.AGENT_REGISTRY

    def test_tag_extractor_not_in_default_agents(self, test_config):
        orch = Orchestrator(config=test_config)
        assert "tag_extractor" not in orch.DEFAULT_AGENTS

    @pytest.mark.asyncio
    async def test_tags_saved_after_analysis(self, test_config, tmp_path):
        """Tag extractor results are persisted to DB after analysis_id is available."""
        db_path = str(tmp_path / "test.db")
        db_manager = DatabaseManager(db_path)
        orch = Orchestrator(config=test_config, db_manager=db_manager)

        mock_tag_data = {
            "tags": [
                {"tag": "recurring_revenue", "category": "business_model", "evidence": "Services"},
                {"tag": "ai_integration", "category": "growth_drivers", "evidence": "AI launched"},
            ],
            "tags_count": 2,
            "data_sources_used": ["fundamentals"],
        }

        with (
            patch("src.orchestrator.NewsAgent") as MockNews,
            patch("src.orchestrator.MarketAgent") as MockMarket,
            patch("src.orchestrator.FundamentalsAgent") as MockFund,
            patch("src.orchestrator.TechnicalAgent") as MockTech,
            patch("src.orchestrator.MacroAgent") as MockMacro,
            patch("src.orchestrator.OptionsAgent") as MockOptions,
            patch("src.orchestrator.EarningsAgent") as MockEarnings,
            patch("src.orchestrator.LeadershipAgent") as MockLeadership,
            patch("src.orchestrator.SentimentAgent") as MockSent,
            patch("src.orchestrator.SolutionAgent") as MockSolution,
            patch("src.orchestrator.ThesisAgent") as MockThesis,
            patch("src.orchestrator.EarningsReviewAgent") as MockReview,
            patch("src.orchestrator.NarrativeAgent") as MockNarrative,
            patch("src.orchestrator.TagExtractorAgent") as MockTagExtractor,
        ):
            for mock_cls, name in [
                (MockNews, "news"), (MockMarket, "market"),
                (MockFund, "fundamentals"), (MockTech, "technical"),
                (MockMacro, "macro"), (MockOptions, "options"),
                (MockEarnings, "earnings"), (MockLeadership, "leadership"),
            ]:
                mock_cls.return_value.execute = AsyncMock(return_value=_make_agent_result(name))

            MockSent.return_value.set_context_data = MagicMock()
            MockSent.return_value.execute = AsyncMock(return_value=_make_agent_result("sentiment"))
            MockSolution.return_value.execute = AsyncMock(return_value=_make_solution_result())
            MockThesis.return_value.execute = AsyncMock(return_value={"success": True, "data": {"thesis_summary": "Test."}})
            MockReview.return_value.execute = AsyncMock(return_value={"success": True, "data": {"executive_summary": "Test."}})
            MockNarrative.return_value.execute = AsyncMock(return_value={"success": True, "data": {"company_arc": "Test."}})
            MockTagExtractor.return_value.execute = AsyncMock(return_value={"success": True, "data": mock_tag_data})

            result = await orch.analyze_ticker("AAPL")

        assert result["success"] is True
        # Verify tags were saved to DB
        saved_tags = db_manager.get_company_tags("AAPL")
        assert len(saved_tags) == 2
        tag_names = {t["tag"] for t in saved_tags}
        assert "recurring_revenue" in tag_names
        assert "ai_integration" in tag_names

    @pytest.mark.asyncio
    async def test_tag_failure_is_nonblocking(self, test_config, tmp_path):
        db_path = str(tmp_path / "test.db")
        db_manager = DatabaseManager(db_path)
        orch = Orchestrator(config=test_config, db_manager=db_manager)

        with (
            patch("src.orchestrator.NewsAgent") as MockNews,
            patch("src.orchestrator.MarketAgent") as MockMarket,
            patch("src.orchestrator.FundamentalsAgent") as MockFund,
            patch("src.orchestrator.TechnicalAgent") as MockTech,
            patch("src.orchestrator.MacroAgent") as MockMacro,
            patch("src.orchestrator.OptionsAgent") as MockOptions,
            patch("src.orchestrator.EarningsAgent") as MockEarnings,
            patch("src.orchestrator.LeadershipAgent") as MockLeadership,
            patch("src.orchestrator.SentimentAgent") as MockSent,
            patch("src.orchestrator.SolutionAgent") as MockSolution,
            patch("src.orchestrator.ThesisAgent") as MockThesis,
            patch("src.orchestrator.EarningsReviewAgent") as MockReview,
            patch("src.orchestrator.NarrativeAgent") as MockNarrative,
            patch("src.orchestrator.TagExtractorAgent") as MockTagExtractor,
        ):
            for mock_cls, name in [
                (MockNews, "news"), (MockMarket, "market"),
                (MockFund, "fundamentals"), (MockTech, "technical"),
                (MockMacro, "macro"), (MockOptions, "options"),
                (MockEarnings, "earnings"), (MockLeadership, "leadership"),
            ]:
                mock_cls.return_value.execute = AsyncMock(return_value=_make_agent_result(name))

            MockSent.return_value.set_context_data = MagicMock()
            MockSent.return_value.execute = AsyncMock(return_value=_make_agent_result("sentiment"))
            MockSolution.return_value.execute = AsyncMock(return_value=_make_solution_result())
            MockThesis.return_value.execute = AsyncMock(return_value={"success": True, "data": {"thesis_summary": "Test."}})
            MockReview.return_value.execute = AsyncMock(return_value={"success": True, "data": {"executive_summary": "Test."}})
            MockNarrative.return_value.execute = AsyncMock(return_value={"success": True, "data": {"company_arc": "Test."}})
            MockTagExtractor.return_value.execute = AsyncMock(side_effect=Exception("LLM exploded"))

            result = await orch.analyze_ticker("AAPL")

        assert result["success"] is True
        # No tags saved, but analysis completed
        saved_tags = db_manager.get_company_tags("AAPL")
        assert len(saved_tags) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_orchestrator.py::TestTagExtractorIntegration -v`
Expected: FAIL — `cannot import name 'TagExtractorAgent'`

- [ ] **Step 3: Add import and registry**

In `src/orchestrator.py`, add after the NarrativeAgent import:

```python
from .agents.tag_extractor_agent import TagExtractorAgent
```

Add to `AGENT_REGISTRY`:

```python
"tag_extractor": {"class": TagExtractorAgent, "requires": []},
```

- [ ] **Step 4: Add _run_tag_extractor_agent() method**

Add after `_run_narrative_agent()`:

```python
    async def _run_tag_extractor_agent(
        self,
        ticker: str,
        agent_results: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Run tag extractor for qualitative classification (non-blocking)."""
        try:
            tag_agent = TagExtractorAgent(ticker, self.config, agent_results)
            self._inject_shared_resources(tag_agent)
            timeout = self.config.get("AGENT_TIMEOUT", 30)
            result = await asyncio.wait_for(
                tag_agent.execute(),
                timeout=timeout,
            )
            if result.get("success"):
                return result.get("data")
            else:
                self.logger.warning(f"Tag extractor failed for {ticker}: {result.get('error')}")
                return None
        except asyncio.TimeoutError:
            self.logger.warning(f"Tag extractor timed out for {ticker}")
            return None
        except Exception as e:
            self.logger.warning(f"Tag extractor error for {ticker}: {e}")
            return None
```

- [ ] **Step 5: Expand asyncio.gather() to 5 agents**

Replace the 4-way gather:

```python
            final_analysis, thesis_result, earnings_review_result, narrative_result = await asyncio.gather(
                self._run_solution_agent(ticker, agent_results),
                self._run_thesis_agent(ticker, agent_results),
                self._run_earnings_review_agent(ticker, agent_results),
                self._run_narrative_agent(ticker, agent_results),
            )
            if thesis_result:
                final_analysis["thesis"] = thesis_result
            if earnings_review_result:
                final_analysis["earnings_review"] = earnings_review_result
            if narrative_result:
                final_analysis["narrative"] = narrative_result
```

With:

```python
            final_analysis, thesis_result, earnings_review_result, narrative_result, tag_result = await asyncio.gather(
                self._run_solution_agent(ticker, agent_results),
                self._run_thesis_agent(ticker, agent_results),
                self._run_earnings_review_agent(ticker, agent_results),
                self._run_narrative_agent(ticker, agent_results),
                self._run_tag_extractor_agent(ticker, agent_results),
            )
            if thesis_result:
                final_analysis["thesis"] = thesis_result
            if earnings_review_result:
                final_analysis["earnings_review"] = earnings_review_result
            if narrative_result:
                final_analysis["narrative"] = narrative_result
```

- [ ] **Step 6: Add tag persistence in post-DB-save phase**

In `analyze_ticker()`, find the section after `analysis_id` is set where perception snapshots are saved (around line 369). Add AFTER the perception/inflection block (but before thesis health):

```python
            # Persist company tags
            if analysis_id and tag_result:
                try:
                    tags_to_save = tag_result.get("tags", [])
                    if tags_to_save:
                        self.db_manager.upsert_company_tags(ticker, tags_to_save, analysis_id)
                        self.logger.info(f"Saved {len(tags_to_save)} tags for {ticker}")
                except Exception as e:
                    self.logger.warning(f"Tag save failed for {ticker}: {e}")
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `python -m pytest tests/test_orchestrator.py -v`
Expected: All tests PASS (existing + 4 new)

- [ ] **Step 8: Commit**

```bash
git add src/orchestrator.py tests/test_orchestrator.py
git commit -m "feat(tags): integrate TagExtractorAgent into synthesis phase (5-way gather) with post-save persistence"
```

---

### Task 6: LLM Mock Tests & Full Verification

**Files:**
- Modify: `tests/test_agents/test_tag_extractor_agent.py`

- [ ] **Step 1: Write LLM mock tests**

Append to `tests/test_agents/test_tag_extractor_agent.py`:

```python
import json as json_module
from unittest.mock import patch as mock_patch, AsyncMock as MockAsync


MOCK_LLM_RESPONSE = json_module.dumps({
    "tags": [
        {"tag": "recurring_revenue", "category": "business_model", "evidence": "Services at 28% of revenue with high retention"},
        {"tag": "services_led", "category": "business_model", "evidence": "Services growing faster than hardware"},
        {"tag": "ai_integration", "category": "growth_drivers", "evidence": "AI assistant launched across product line"},
        {"tag": "pricing_power", "category": "growth_drivers", "evidence": "Premium pricing maintained despite competition"},
        {"tag": "consistent_buybacks", "category": "quality_indicators", "evidence": "$90B buyback authorization"},
        {"tag": "strong_free_cash_flow", "category": "quality_indicators", "evidence": "FCF of $90B annually"},
    ],
})


class TestTagExtractorLLMFlow:
    """Tests for LLM-based tag extraction."""

    @pytest.mark.asyncio
    async def test_full_flow_extracts_valid_tags(self):
        agent = TagExtractorAgent("AAPL", {"llm_config": {"provider": "none"}}, _make_agent_results())

        async def mock_call_llm(prompt):
            return MOCK_LLM_RESPONSE

        with mock_patch.object(agent, "_call_llm", side_effect=mock_call_llm):
            result = await agent.analyze(agent.agent_results)

        assert result["tags_count"] == 6
        tag_names = {t["tag"] for t in result["tags"]}
        assert "recurring_revenue" in tag_names
        assert "ai_integration" in tag_names

    @pytest.mark.asyncio
    async def test_invalid_tags_filtered_out(self):
        agent = TagExtractorAgent("AAPL", {"llm_config": {"provider": "none"}}, _make_agent_results())

        response_with_invalid = json_module.dumps({
            "tags": [
                {"tag": "recurring_revenue", "category": "business_model", "evidence": "Valid"},
                {"tag": "totally_made_up", "category": "nonsense", "evidence": "Invalid"},
            ],
        })

        async def mock_call_llm(prompt):
            return response_with_invalid

        with mock_patch.object(agent, "_call_llm", side_effect=mock_call_llm):
            result = await agent.analyze(agent.agent_results)

        assert result["tags_count"] == 1
        assert result["tags"][0]["tag"] == "recurring_revenue"

    @pytest.mark.asyncio
    async def test_llm_failure_returns_empty(self):
        agent = TagExtractorAgent("AAPL", {"llm_config": {"provider": "none"}}, _make_agent_results())

        async def mock_fail(prompt):
            raise Exception("LLM unavailable")

        with mock_patch.object(agent, "_call_llm", side_effect=mock_fail):
            result = await agent.analyze(agent.agent_results)

        assert result["tags_count"] == 0
        assert result["tags"] == []

    @pytest.mark.asyncio
    async def test_empty_context_returns_empty(self):
        agent = TagExtractorAgent("AAPL", {"llm_config": {"provider": "none"}}, {})

        result = await agent.analyze({})

        assert result["tags_count"] == 0


class TestTagExtractorPrompt:
    """Tests for prompt construction."""

    def test_prompt_contains_taxonomy(self):
        agent = TagExtractorAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        context = agent._build_context()
        prompt = agent._build_prompt(context)
        assert "recurring_revenue" in prompt
        assert "activist_involved" in prompt
        assert "business_model" in prompt
        assert "risk_flags" in prompt

    def test_prompt_contains_company_context(self):
        agent = TagExtractorAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        context = agent._build_context()
        prompt = agent._build_prompt(context)
        assert "Apple Inc." in prompt
        assert "Technology" in prompt
```

- [ ] **Step 2: Run all tag extractor tests**

Run: `python -m pytest tests/test_agents/test_tag_extractor_agent.py -v`
Expected: All tests PASS (4 model + 4 taxonomy + 3 context + 4 LLM + 2 prompt = 17)

- [ ] **Step 3: Run the full test suite**

Run: `python -m pytest tests/ -v --tb=short`
Expected: All tests PASS, no regressions.

- [ ] **Step 4: Commit**

```bash
git add tests/test_agents/test_tag_extractor_agent.py
git commit -m "test(tags): add LLM mock tests, prompt validation, and invalid tag filtering tests"
```
