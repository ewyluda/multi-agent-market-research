# Narrative Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a two-pass LLM hybrid agent that weaves multi-year financial data into a coherent investment narrative with chronological year sections, thematic chapters, and selective quarterly inflection highlights.

**Architecture:** NarrativeAgent inherits BaseAgent, takes agent_results in constructor but also fetches its own historical data in `fetch_data()` (multi-year financials + transcripts from data provider). Pass 1 extracts per-year facts and cross-year themes. Pass 2 synthesizes narrative with year sections, thematic chapters, and company arc. No hard data gate — always produces output with transparent `data_completeness`. Runs parallel with solution+thesis+earnings_review in synthesis phase via asyncio.gather().

**Tech Stack:** Python, Pydantic, anthropic/openai SDKs, pytest

**Spec:** `docs/superpowers/specs/2026-04-02-narrative-agent-design.md`

---

### Task 1: Pydantic Models

**Files:**
- Modify: `src/models.py`
- Create: `tests/test_agents/test_narrative_agent.py`

- [ ] **Step 1: Create test file with model validation tests**

Create `tests/test_agents/test_narrative_agent.py`:

```python
"""Tests for NarrativeAgent — models, data fetching, LLM flow, guardrails."""

import pytest
from pydantic import ValidationError
from src.models import QuarterlyInflection, YearSection, NarrativeChapter, NarrativeOutput


class TestNarrativeModels:
    """Pydantic model validation tests."""

    def test_quarterly_inflection_valid(self):
        qi = QuarterlyInflection(
            quarter="Q2'25",
            headline="First China revenue decline in 3 years",
            details="China revenue fell 8% YoY driven by Huawei competition and macro weakness.",
            impact="negative",
        )
        assert qi.impact == "negative"
        assert qi.quarter == "Q2'25"

    def test_year_section_valid(self):
        ys = YearSection(
            year=2024,
            headline="Steady growth with services acceleration",
            revenue_trajectory="Revenue grew 8% to $383B driven by services.",
            margin_story="Gross margin expanded 100bps to 46% on services mix shift.",
            strategic_moves=["Vision Pro launch", "India manufacturing expansion"],
            management_commentary="CEO emphasized AI integration across product lines.",
            capital_allocation="$90B buyback authorization, 4% dividend increase.",
            quarterly_inflections=[
                QuarterlyInflection(
                    quarter="Q3'24",
                    headline="China weakness emerged",
                    details="First YoY decline in Greater China revenue.",
                    impact="negative",
                )
            ],
        )
        assert ys.year == 2024
        assert len(ys.quarterly_inflections) == 1
        assert len(ys.strategic_moves) == 2

    def test_year_section_no_inflections(self):
        ys = YearSection(
            year=2023,
            headline="Quiet year of consolidation",
            revenue_trajectory="Revenue flat at $355B.",
            margin_story="Margins held steady.",
            strategic_moves=[],
            management_commentary="Focus on operational efficiency.",
            capital_allocation="Continued buybacks.",
            quarterly_inflections=[],
        )
        assert len(ys.quarterly_inflections) == 0

    def test_narrative_chapter_valid(self):
        nc = NarrativeChapter(
            title="The Services Transition",
            years_covered="2023-2025",
            narrative="Apple's services business grew from 20% to 28% of revenue over three years.",
            evidence=["Services revenue $85B in 2023", "Services revenue $110B in 2025"],
        )
        assert nc.title == "The Services Transition"
        assert len(nc.evidence) == 2

    def test_narrative_output_valid(self):
        output = NarrativeOutput(
            company_arc="Apple transitioned from hardware dependence to a services-led model.",
            year_sections=[
                YearSection(
                    year=2024, headline="Growth year", revenue_trajectory="Up 8%.",
                    margin_story="Margins expanded.", strategic_moves=[], management_commentary="Positive.",
                    capital_allocation="Buybacks.", quarterly_inflections=[],
                )
            ],
            narrative_chapters=[
                NarrativeChapter(
                    title="AI Pivot", years_covered="2024-2025",
                    narrative="Invested heavily in AI.", evidence=["R&D up 20%"],
                )
            ],
            key_inflection_points=["Q3'24 China decline"],
            current_chapter="Navigating the AI transition while managing China headwinds.",
            years_covered=3,
            data_completeness=0.85,
            data_sources_used=["financials", "transcripts", "fundamentals"],
        )
        assert output.years_covered == 3
        assert len(output.year_sections) == 1
        assert len(output.narrative_chapters) == 1

    def test_narrative_output_completeness_clamped(self):
        with pytest.raises(ValidationError):
            NarrativeOutput(
                company_arc="x", year_sections=[], narrative_chapters=[],
                key_inflection_points=[], current_chapter="x",
                years_covered=0, data_completeness=1.5, data_sources_used=[],
            )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_agents/test_narrative_agent.py -v`
Expected: FAIL — `ImportError: cannot import name 'QuarterlyInflection' from 'src.models'`

- [ ] **Step 3: Add Pydantic models to src/models.py**

Add at the end of `src/models.py`, after the Earnings Review Agent models section:

```python
# ── Narrative Agent models ────────────────────────────────────────────────────


class QuarterlyInflection(BaseModel):
    """A quarter that represented a material inflection point."""
    quarter: str = Field(..., description="Quarter label, e.g. Q2'25")
    headline: str = Field(..., description="One-line summary of why this quarter mattered")
    details: str = Field(..., description="2-3 sentence explanation")
    impact: str = Field(..., description="positive, negative, or pivotal")


class YearSection(BaseModel):
    """Chronological section for one fiscal year."""
    year: int = Field(..., description="Fiscal year")
    headline: str = Field(..., description="One-line summary of the year")
    revenue_trajectory: str = Field(..., description="Revenue story for this year")
    margin_story: str = Field(..., description="Margin expansion/compression narrative")
    strategic_moves: List[str] = Field(default=[], description="M&A, divestitures, pivots, reorgs")
    management_commentary: str = Field(..., description="Key themes from earnings calls")
    capital_allocation: str = Field(..., description="Buybacks, dividends, capex, debt")
    quarterly_inflections: List[QuarterlyInflection] = Field(default=[], description="0-2 inflection quarters")


class NarrativeChapter(BaseModel):
    """A thematic narrative thread spanning multiple years."""
    title: str = Field(..., description="Chapter title, e.g. 'The Services Transition'")
    years_covered: str = Field(..., description="Year range, e.g. '2023-2025'")
    narrative: str = Field(..., description="3-5 sentence thematic narrative")
    evidence: List[str] = Field(default=[], description="Supporting data points")


class NarrativeOutput(BaseModel):
    """Complete multi-year financial narrative output."""
    company_arc: str = Field(..., description="3-5 sentence overarching story")
    year_sections: List[YearSection] = Field(default=[], description="Chronological year sections")
    narrative_chapters: List[NarrativeChapter] = Field(default=[], description="2-4 thematic threads")
    key_inflection_points: List[str] = Field(default=[], description="Top 3-5 trajectory-changing moments")
    current_chapter: str = Field(..., description="Where the company is now in its story")
    years_covered: int = Field(..., description="How many years of data were available")
    data_completeness: float = Field(..., ge=0.0, le=1.0, description="0.0-1.0 data quality score")
    data_sources_used: List[str] = Field(default=[], description="Which data sources contributed")
    error: Optional[str] = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_agents/test_narrative_agent.py::TestNarrativeModels -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/models.py tests/test_agents/test_narrative_agent.py
git commit -m "feat(narrative): add Pydantic models for NarrativeOutput schema"
```

---

### Task 2: NarrativeAgent — Data Fetching, Year Extraction, Completeness

**Files:**
- Create: `src/agents/narrative_agent.py`
- Modify: `tests/test_agents/test_narrative_agent.py`

- [ ] **Step 1: Write data fetching, year extraction, and completeness tests**

Append to `tests/test_agents/test_narrative_agent.py`:

```python
from unittest.mock import AsyncMock, MagicMock, patch
from src.agents.narrative_agent import NarrativeAgent


def _make_mock_financials(num_years=3):
    """Build mock financials with income_statement records for multiple years."""
    income = []
    for i in range(num_years):
        year = 2025 - i
        income.append({
            "period_ending": f"{year}-12-31",
            "fiscal_year": year,
            "revenue": (383 - i * 20) * 1e9,
            "gross_profit": (176 - i * 8) * 1e9,
            "operating_income": (115 - i * 5) * 1e9,
            "net_income": (97 - i * 4) * 1e9,
            "research_and_development": (27 + i * 1) * 1e9,
        })
    return {
        "income_statement": income,
        "balance_sheet": [{"period_ending": f"{2025-i}-12-31", "total_assets": 350e9} for i in range(num_years)],
        "cash_flow": [{"period_ending": f"{2025-i}-12-31", "free_cash_flow": 90e9} for i in range(num_years)],
        "data_source": "openbb",
    }


def _make_mock_transcripts(num_quarters=4):
    """Build mock transcript list."""
    transcripts = []
    for i in range(num_quarters):
        q = 4 - (i % 4)
        y = 2025 - (i // 4)
        transcripts.append({
            "quarter": q,
            "year": y,
            "date": f"{y}-{q*3:02d}-15",
            "content": f"Q{q} {y} earnings call transcript content. Management discussed growth and strategy.",
            "data_source": "fmp",
        })
    return transcripts


def _make_agent_results():
    """Build mock agent_results for latest analysis context."""
    return {
        "fundamentals": {
            "success": True,
            "data": {
                "company_name": "Apple Inc.",
                "sector": "Technology",
                "revenue": 383e9,
                "revenue_growth": 0.08,
                "gross_margin": 0.46,
                "business_description": "Designs consumer electronics and software.",
            },
        },
    }


class TestNarrativeDataFetching:
    """Tests for fetch_data() hybrid data sourcing."""

    @pytest.mark.asyncio
    async def test_fetch_data_calls_data_provider(self):
        agent = NarrativeAgent("AAPL", {"llm_config": {}, "NARRATIVE_YEARS": 3}, _make_agent_results())
        mock_dp = MagicMock()
        mock_dp.get_financials = AsyncMock(return_value=_make_mock_financials())
        mock_dp.get_earnings_transcripts = AsyncMock(return_value=_make_mock_transcripts())
        agent._data_provider = mock_dp

        result = await agent.fetch_data()

        mock_dp.get_financials.assert_called_once_with("AAPL")
        mock_dp.get_earnings_transcripts.assert_called_once_with("AAPL", num_quarters=12)
        assert "financials" in result
        assert "transcripts" in result
        assert "agent_results" in result

    @pytest.mark.asyncio
    async def test_fetch_data_default_years(self):
        agent = NarrativeAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        mock_dp = MagicMock()
        mock_dp.get_financials = AsyncMock(return_value=_make_mock_financials())
        mock_dp.get_earnings_transcripts = AsyncMock(return_value=_make_mock_transcripts())
        agent._data_provider = mock_dp

        await agent.fetch_data()

        # Default NARRATIVE_YEARS=3, so 3*4=12 quarters
        mock_dp.get_earnings_transcripts.assert_called_once_with("AAPL", num_quarters=12)


class TestNarrativeYearExtraction:
    """Tests for extracting years from financial data."""

    def test_extract_years_from_financials(self):
        agent = NarrativeAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        financials = _make_mock_financials(num_years=3)
        years = agent._extract_available_years(financials)
        assert years == [2023, 2024, 2025]

    def test_extract_years_empty_financials(self):
        agent = NarrativeAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        years = agent._extract_available_years(None)
        assert years == []

    def test_extract_years_empty_income(self):
        agent = NarrativeAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        years = agent._extract_available_years({"income_statement": []})
        assert years == []


class TestNarrativeCompleteness:
    """Tests for data completeness scoring."""

    def test_full_completeness(self):
        agent = NarrativeAgent("AAPL", {"llm_config": {}, "NARRATIVE_YEARS": 3}, _make_agent_results())
        score = agent._compute_data_completeness(
            financials=_make_mock_financials(3),
            transcripts=_make_mock_transcripts(12),
            num_years_requested=3,
        )
        assert score == pytest.approx(1.0, abs=0.01)

    def test_partial_financials(self):
        agent = NarrativeAgent("AAPL", {"llm_config": {}, "NARRATIVE_YEARS": 3}, _make_agent_results())
        score = agent._compute_data_completeness(
            financials=_make_mock_financials(1),
            transcripts=_make_mock_transcripts(12),
            num_years_requested=3,
        )
        # 1/3 * 0.60 + 1.0 * 0.30 + 0.10 = 0.20 + 0.30 + 0.10 = 0.60
        assert score == pytest.approx(0.60, abs=0.02)

    def test_no_transcripts(self):
        agent = NarrativeAgent("AAPL", {"llm_config": {}, "NARRATIVE_YEARS": 3}, _make_agent_results())
        score = agent._compute_data_completeness(
            financials=_make_mock_financials(3),
            transcripts=[],
            num_years_requested=3,
        )
        # 1.0 * 0.60 + 0 + 0.10 = 0.70
        assert score == pytest.approx(0.70, abs=0.01)

    def test_no_fundamentals_context(self):
        agent = NarrativeAgent("AAPL", {"llm_config": {}, "NARRATIVE_YEARS": 3}, {})
        score = agent._compute_data_completeness(
            financials=_make_mock_financials(3),
            transcripts=_make_mock_transcripts(12),
            num_years_requested=3,
        )
        # 1.0 * 0.60 + 1.0 * 0.30 + 0 = 0.90
        assert score == pytest.approx(0.90, abs=0.01)

    def test_no_data_at_all(self):
        agent = NarrativeAgent("AAPL", {"llm_config": {}, "NARRATIVE_YEARS": 3}, {})
        score = agent._compute_data_completeness(
            financials=None,
            transcripts=[],
            num_years_requested=3,
        )
        assert score == pytest.approx(0.0, abs=0.01)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_agents/test_narrative_agent.py::TestNarrativeDataFetching -v`
Expected: FAIL — `ImportError: cannot import name 'NarrativeAgent'`

- [ ] **Step 3: Implement NarrativeAgent**

Create `src/agents/narrative_agent.py`:

```python
"""Narrative agent — two-pass LLM multi-year financial story engine."""

import asyncio
import json
import re
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

import anthropic
from openai import OpenAI

from .base_agent import BaseAgent


class NarrativeAgent(BaseAgent):
    """Agent that weaves multi-year financial data into a coherent investment narrative.

    Hybrid agent: fetches its own historical data in fetch_data() AND consumes
    agent_results for latest analysis context. Two-pass LLM:
        Pass 1 ("The Researcher"): Extracts per-year facts and cross-year themes.
        Pass 2 ("The Storyteller"): Synthesizes narrative with year sections and chapters.

    Runs in the synthesis phase, parallel with Solution, Thesis, and EarningsReview.
    """

    def __init__(self, ticker: str, config: Dict[str, Any], agent_results: Dict[str, Any]):
        super().__init__(ticker, config)
        self.agent_results = agent_results

    async def fetch_data(self) -> Dict[str, Any]:
        """Fetch multi-year financials and transcripts from data provider."""
        dp = getattr(self, "_data_provider", None)
        if not dp:
            return {"financials": None, "transcripts": [], "agent_results": self.agent_results}

        num_years = self.config.get("NARRATIVE_YEARS", 3)
        num_quarters = num_years * 4

        financials_task = dp.get_financials(self.ticker)
        transcripts_task = dp.get_earnings_transcripts(self.ticker, num_quarters=num_quarters)

        financials, transcripts = await asyncio.gather(
            financials_task, transcripts_task, return_exceptions=True
        )

        financials = financials if isinstance(financials, dict) else None
        transcripts = transcripts if isinstance(transcripts, list) else []

        self.logger.info(
            f"Narrative: fetched financials ({bool(financials)}) and "
            f"{len(transcripts)} transcripts for {self.ticker}"
        )

        return {
            "financials": financials,
            "transcripts": transcripts,
            "agent_results": self.agent_results,
        }

    async def analyze(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        financials = raw_data.get("financials")
        transcripts = raw_data.get("transcripts", [])
        num_years = self.config.get("NARRATIVE_YEARS", 3)

        available_years = self._extract_available_years(financials)
        completeness = self._compute_data_completeness(financials, transcripts, num_years)
        sources = self._get_data_sources(financials, transcripts)

        if not available_years:
            return self._empty_result(completeness, sources)

        # Pass 1: Extract per-year facts
        try:
            pass1_prompt = self._build_pass1_prompt(financials, transcripts, available_years)
            pass1_response = await self._call_llm(pass1_prompt)
            extracted_facts = self._parse_llm_response(pass1_response)
        except Exception as e:
            self.logger.warning(f"Narrative Pass 1 failed for {self.ticker}: {e}")
            return self._empty_result(completeness, sources)

        # Pass 2: Synthesize narrative
        try:
            pass2_prompt = self._build_pass2_prompt(extracted_facts, self.ticker)
            pass2_response = await self._call_llm(pass2_prompt)
            narrative_raw = self._parse_llm_response(pass2_response)
        except Exception as e:
            self.logger.warning(f"Narrative Pass 2 failed for {self.ticker}: {e}, using Pass 1 fallback")
            return self._pass1_fallback(extracted_facts, available_years, completeness, sources)

        narrative_raw["years_covered"] = len(available_years)
        narrative_raw["data_completeness"] = completeness
        narrative_raw["data_sources_used"] = sources

        # Guardrails
        from ..llm_guardrails import validate_narrative_output
        validated, warnings = validate_narrative_output(narrative_raw)
        if warnings:
            validated["guardrail_warnings"] = warnings
        return validated

    # ─── Year Extraction ─────────────────────────────────────────────────────

    def _extract_available_years(self, financials: Optional[Dict[str, Any]]) -> List[int]:
        """Extract sorted list of unique years from income statement data."""
        if not financials:
            return []
        income = financials.get("income_statement", [])
        if not income:
            return []
        years = set()
        for record in income:
            fy = record.get("fiscal_year")
            if fy:
                years.add(int(fy))
            else:
                date_str = record.get("period_ending", "")
                if date_str:
                    try:
                        years.add(datetime.fromisoformat(date_str.replace("Z", "")).year)
                    except (ValueError, TypeError):
                        pass
        return sorted(years)

    # ─── Data Completeness ───────────────────────────────────────────────────

    def _compute_data_completeness(
        self,
        financials: Optional[Dict[str, Any]],
        transcripts: List[Dict[str, Any]],
        num_years_requested: int,
    ) -> float:
        """Compute data completeness score (0.0-1.0)."""
        score = 0.0

        # Financial coverage (0.60 weight)
        years_available = len(self._extract_available_years(financials))
        if num_years_requested > 0 and years_available > 0:
            financial_coverage = min(years_available / num_years_requested, 1.0)
            score += financial_coverage * 0.60

        # Transcript coverage (0.30 weight)
        if transcripts and len(transcripts) > 0:
            expected_quarters = num_years_requested * 4
            transcript_coverage = min(len(transcripts) / expected_quarters, 1.0)
            score += transcript_coverage * 0.30

        # Fundamentals context (0.10 weight)
        fund_result = self.agent_results.get("fundamentals", {})
        if isinstance(fund_result, dict) and fund_result.get("success") and fund_result.get("data"):
            score += 0.10

        return round(score, 2)

    def _get_data_sources(
        self,
        financials: Optional[Dict[str, Any]],
        transcripts: List[Dict[str, Any]],
    ) -> List[str]:
        """Get list of data sources used."""
        sources = []
        if financials:
            sources.append("financials")
        if transcripts:
            sources.append("transcripts")
        fund_result = self.agent_results.get("fundamentals", {})
        if isinstance(fund_result, dict) and fund_result.get("success"):
            sources.append("fundamentals")
        return sources

    def _get_agent_data(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """Safely extract data dict from agent results."""
        result = self.agent_results.get(agent_name, {})
        if isinstance(result, dict) and result.get("success"):
            return result.get("data")
        return None

    # ─── LLM Prompts ────────────────────────────────────────────────────────

    def _build_pass1_prompt(
        self,
        financials: Optional[Dict[str, Any]],
        transcripts: List[Dict[str, Any]],
        available_years: List[int],
    ) -> str:
        """Build Pass 1 fact extraction prompt."""
        # Format income statements
        income = financials.get("income_statement", []) if financials else []
        income_str = ""
        for record in income:
            fy = record.get("fiscal_year", "?")
            rev = record.get("revenue")
            rev_str = f"${rev/1e9:.1f}B" if rev else "N/A"
            gp = record.get("gross_profit")
            gp_str = f"${gp/1e9:.1f}B" if gp else "N/A"
            oi = record.get("operating_income")
            oi_str = f"${oi/1e9:.1f}B" if oi else "N/A"
            ni = record.get("net_income")
            ni_str = f"${ni/1e9:.1f}B" if ni else "N/A"
            rd = record.get("research_and_development")
            rd_str = f"${rd/1e9:.1f}B" if rd else "N/A"
            income_str += f"  FY{fy}: Revenue {rev_str} | Gross Profit {gp_str} | Operating Income {oi_str} | Net Income {ni_str} | R&D {rd_str}\n"

        # Format transcript excerpts (limit per transcript to keep tokens manageable)
        transcript_str = ""
        for t in transcripts[:8]:  # Cap at 8 quarters
            q, y = t.get("quarter", "?"), t.get("year", "?")
            content = t.get("content", "")[:2000]  # Truncate each transcript
            transcript_str += f"\n  --- Q{q}/{y} ---\n  {content}\n"

        # Fundamentals context
        fund_data = self._get_agent_data("fundamentals") or {}
        company = fund_data.get("company_name", self.ticker)
        sector = fund_data.get("sector", "N/A")
        desc = fund_data.get("business_description", "")

        years_range = f"{available_years[0]}-{available_years[-1]}" if len(available_years) > 1 else str(available_years[0])

        return f"""You are a senior equity research analyst extracting key facts from multi-year financial data for {self.ticker} ({company}).

IMPORTANT RULES:
- Only extract facts from the provided data. Do NOT infer events not mentioned.
- For inflection_quarters, only flag quarters where something MATERIALLY changed — not routine quarters.
- Be specific with numbers — cite revenue, margins, growth rates.

Return a JSON object with EXACTLY these keys — no markdown, no explanation, just raw JSON:

{{
  "per_year": [
    {{
      "year": 2024,
      "revenue": "$XB",
      "revenue_growth": "X%",
      "gross_margin": "X%",
      "operating_margin": "X%",
      "key_events": ["2-4 material events"],
      "management_themes": ["2-4 recurring themes from earnings calls"],
      "capital_moves": ["significant capital allocation decisions"],
      "inflection_quarters": [
        {{"quarter": "QX'YY", "event": "one sentence describing what changed"}}
      ]
    }}
  ],
  "cross_year_themes": ["3-5 themes that span multiple years"]
}}

--- COMPANY ---
{company} | Sector: {sector}
{desc}

--- INCOME STATEMENTS ({years_range}) ---
{income_str}
--- EARNINGS CALL EXCERPTS ---
{transcript_str}
"""

    def _build_pass2_prompt(self, extracted_facts: Dict[str, Any], ticker: str) -> str:
        """Build Pass 2 narrative synthesis prompt."""
        facts_json = json.dumps(extracted_facts, indent=2)
        return f"""You are a senior equity analyst who has covered {ticker} for years. Write the narrative that connects these financial results and management commentary into a coherent investment story.

Rules:
1. Every claim must trace to the extracted facts. Do not introduce new data.
2. Narrative chapters must span MULTIPLE years — single-year themes belong in year sections, not chapters.
3. Quarterly inflections: only include genuinely significant quarters (0-2 per year).
4. Year sections should be chronological (oldest to newest).
5. The company_arc should read like the opening paragraph of a long-form equity research piece.

Return a JSON object with EXACTLY these keys — no markdown, no explanation, just raw JSON:

{{
  "company_arc": "3-5 sentence overarching story connecting the years",
  "year_sections": [
    {{
      "year": 2024,
      "headline": "One-line summary of this year",
      "revenue_trajectory": "Revenue story with numbers",
      "margin_story": "Margin expansion/compression with numbers",
      "strategic_moves": ["key strategic actions"],
      "management_commentary": "Key themes from management",
      "capital_allocation": "Buybacks, dividends, capex, debt",
      "quarterly_inflections": [
        {{"quarter": "QX'YY", "headline": "One line", "details": "2-3 sentences", "impact": "positive|negative|pivotal"}}
      ]
    }}
  ],
  "narrative_chapters": [
    {{
      "title": "Thematic title spanning years",
      "years_covered": "YYYY-YYYY",
      "narrative": "3-5 sentence thematic narrative",
      "evidence": ["2-4 supporting data points from the facts"]
    }}
  ],
  "key_inflection_points": ["Top 3-5 moments that changed the trajectory"],
  "current_chapter": "1-2 sentences on where the company is now in its story"
}}

--- EXTRACTED FACTS ---

{facts_json}
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
                max_tokens=llm_config.get("max_tokens", 4096),
                temperature=llm_config.get("temperature", 0.4),
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
                max_tokens=llm_config.get("max_tokens", 4096),
                temperature=llm_config.get("temperature", 0.4),
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

    # ─── Fallback Results ────────────────────────────────────────────────────

    def _empty_result(self, completeness: float, sources: List[str]) -> Dict[str, Any]:
        """Return empty result when no historical data is available."""
        return {
            "company_arc": f"Insufficient historical data to construct a financial narrative for {self.ticker}.",
            "year_sections": [],
            "narrative_chapters": [],
            "key_inflection_points": [],
            "current_chapter": "",
            "years_covered": 0,
            "data_completeness": completeness,
            "data_sources_used": sources,
            "error": "No multi-year financial data available.",
        }

    def _pass1_fallback(
        self,
        extracted_facts: Dict[str, Any],
        available_years: List[int],
        completeness: float,
        sources: List[str],
    ) -> Dict[str, Any]:
        """Fallback when Pass 2 fails — surface extracted facts as year sections."""
        year_sections = []
        for py in extracted_facts.get("per_year", []):
            year_sections.append({
                "year": py.get("year", 0),
                "headline": f"FY{py.get('year', '?')}: Revenue {py.get('revenue', 'N/A')}",
                "revenue_trajectory": f"Revenue: {py.get('revenue', 'N/A')}, growth: {py.get('revenue_growth', 'N/A')}",
                "margin_story": f"Gross margin: {py.get('gross_margin', 'N/A')}, operating margin: {py.get('operating_margin', 'N/A')}",
                "strategic_moves": py.get("key_events", []),
                "management_commentary": "; ".join(py.get("management_themes", [])),
                "capital_allocation": "; ".join(py.get("capital_moves", [])),
                "quarterly_inflections": [],
            })
        return {
            "company_arc": f"Partial narrative for {self.ticker} — fact extraction succeeded but narrative synthesis failed.",
            "year_sections": year_sections,
            "narrative_chapters": [],
            "key_inflection_points": [],
            "current_chapter": "",
            "years_covered": len(available_years),
            "data_completeness": completeness,
            "data_sources_used": sources,
            "extracted_facts": extracted_facts,
            "pass2_failed": True,
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_agents/test_narrative_agent.py::TestNarrativeDataFetching tests/test_agents/test_narrative_agent.py::TestNarrativeYearExtraction tests/test_agents/test_narrative_agent.py::TestNarrativeCompleteness -v`
Expected: All 12 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/agents/narrative_agent.py tests/test_agents/test_narrative_agent.py
git commit -m "feat(narrative): add NarrativeAgent with hybrid data fetching, year extraction, and completeness scoring"
```

---

### Task 3: LLM Guardrails — validate_narrative_output()

**Files:**
- Modify: `src/llm_guardrails.py`
- Modify: `tests/test_agents/test_narrative_agent.py`

- [ ] **Step 1: Write guardrail tests**

Append to `tests/test_agents/test_narrative_agent.py`:

```python
from src.llm_guardrails import validate_narrative_output


def _make_valid_narrative():
    """Build a valid narrative output dict."""
    return {
        "company_arc": "Apple transitioned from hardware to services over three years.",
        "year_sections": [
            {
                "year": 2023, "headline": "Consolidation year",
                "revenue_trajectory": "Revenue flat.", "margin_story": "Margins held.",
                "strategic_moves": [], "management_commentary": "Efficiency focus.",
                "capital_allocation": "Buybacks.", "quarterly_inflections": [],
            },
            {
                "year": 2024, "headline": "Growth resumed",
                "revenue_trajectory": "Revenue up 8%.", "margin_story": "Margins expanded.",
                "strategic_moves": ["Vision Pro launch"], "management_commentary": "AI focus.",
                "capital_allocation": "$90B buyback.",
                "quarterly_inflections": [
                    {"quarter": "Q3'24", "headline": "China decline", "details": "First decline.", "impact": "negative"},
                ],
            },
            {
                "year": 2025, "headline": "AI acceleration",
                "revenue_trajectory": "Revenue up 12%.", "margin_story": "Services mix lift.",
                "strategic_moves": ["AI assistant launch"], "management_commentary": "AI monetization.",
                "capital_allocation": "Continued buybacks.", "quarterly_inflections": [],
            },
        ],
        "narrative_chapters": [
            {
                "title": "The Services Transition",
                "years_covered": "2023-2025",
                "narrative": "Services grew from 20% to 28% of revenue.",
                "evidence": ["Services $85B in 2023", "Services $110B in 2025"],
            },
        ],
        "key_inflection_points": ["Q3'24 China decline", "AI assistant launch 2025"],
        "current_chapter": "Navigating AI transition.",
        "years_covered": 3,
        "data_completeness": 0.85,
        "data_sources_used": ["financials", "transcripts"],
    }


class TestNarrativeGuardrails:
    """Tests for validate_narrative_output() in llm_guardrails.py."""

    def test_valid_narrative_passes(self):
        narrative = _make_valid_narrative()
        validated, warnings = validate_narrative_output(narrative)
        assert validated["company_arc"] != ""
        assert isinstance(warnings, list)

    def test_year_ordering_flagged(self):
        narrative = _make_valid_narrative()
        # Reverse year order (should be chronological)
        narrative["year_sections"].reverse()
        validated, warnings = validate_narrative_output(narrative)
        assert any("order" in w.lower() or "chronolog" in w.lower() for w in warnings)

    def test_too_many_inflections_flagged(self):
        narrative = _make_valid_narrative()
        # Add 4 inflections to one year (>3 is suspicious)
        narrative["year_sections"][1]["quarterly_inflections"] = [
            {"quarter": f"Q{i}'24", "headline": f"Event {i}", "details": "Details.", "impact": "pivotal"}
            for i in range(1, 5)
        ]
        validated, warnings = validate_narrative_output(narrative)
        assert any("inflection" in w.lower() for w in warnings)

    def test_single_year_chapter_flagged(self):
        narrative = _make_valid_narrative()
        narrative["narrative_chapters"] = [
            {
                "title": "Single Year Theme",
                "years_covered": "2024",
                "narrative": "Only about one year.",
                "evidence": [],
            },
        ]
        validated, warnings = validate_narrative_output(narrative)
        assert any("chapter" in w.lower() or "span" in w.lower() for w in warnings)

    def test_data_completeness_preserved(self):
        narrative = _make_valid_narrative()
        narrative["data_completeness"] = 0.85
        validated, warnings = validate_narrative_output(narrative)
        # Completeness should be preserved (not overridden — narrative doesn't have agent_results in guardrails)
        assert validated["data_completeness"] == 0.85
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_agents/test_narrative_agent.py::TestNarrativeGuardrails -v`
Expected: FAIL — `ImportError: cannot import name 'validate_narrative_output'`

- [ ] **Step 3: Implement validate_narrative_output()**

Add at the end of `src/llm_guardrails.py`:

```python
# ─── Narrative Output ──────────────────────────────────────────────────────


def validate_narrative_output(
    narrative: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[str]]:
    """Validate narrative agent output.

    Checks:
        1. Year ordering — year_sections should be chronological.
        2. Inflection plausibility — flag years with more than 3 quarterly inflections.
        3. Chapter spanning — warn if a narrative chapter covers only 1 year.

    Note: data_completeness is computed by the agent itself (not overridden here)
    because the narrative agent has different inputs than the standard agent_results pattern.

    Returns:
        (validated_narrative, warnings)
    """
    warnings: List[str] = []
    validated = dict(narrative)

    # 1. Year ordering
    year_sections = validated.get("year_sections", [])
    if len(year_sections) >= 2:
        years = [ys.get("year", 0) for ys in year_sections]
        if years != sorted(years):
            warnings.append(
                f"Year sections not in chronological order: {years}. Expected ascending."
            )

    # 2. Inflection plausibility
    for ys in year_sections:
        inflections = ys.get("quarterly_inflections", [])
        year = ys.get("year", "?")
        if len(inflections) > 3:
            warnings.append(
                f"Year {year} has {len(inflections)} quarterly inflections "
                f"(expected 0-2 significant ones, max 3)"
            )

    # 3. Chapter spanning
    for ch in validated.get("narrative_chapters", []):
        years_covered = ch.get("years_covered", "")
        title = ch.get("title", "?")
        # Check if it looks like a single year (no dash/range)
        if years_covered and "-" not in years_covered:
            warnings.append(
                f"Narrative chapter '{title}' covers only '{years_covered}' — "
                f"chapters should span multiple years"
            )

    return validated, warnings
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_agents/test_narrative_agent.py::TestNarrativeGuardrails -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/llm_guardrails.py tests/test_agents/test_narrative_agent.py
git commit -m "feat(narrative): add validate_narrative_output() guardrails — year ordering, inflection count, chapter spanning"
```

---

### Task 4: Orchestrator Integration

**Files:**
- Modify: `src/orchestrator.py`
- Modify: `tests/test_orchestrator.py`

- [ ] **Step 1: Write orchestrator integration tests**

Append to `tests/test_orchestrator.py`:

```python
class TestNarrativeIntegration:
    """Tests for narrative agent integration in synthesis phase."""

    def test_narrative_in_registry(self, test_config):
        orch = Orchestrator(config=test_config)
        assert "narrative" in orch.AGENT_REGISTRY

    def test_narrative_not_in_default_agents(self, test_config):
        orch = Orchestrator(config=test_config)
        assert "narrative" not in orch.DEFAULT_AGENTS

    @pytest.mark.asyncio
    async def test_narrative_runs_parallel_in_synthesis(self, test_config, tmp_path):
        db_path = str(tmp_path / "test.db")
        db_manager = DatabaseManager(db_path)
        orch = Orchestrator(config=test_config, db_manager=db_manager)

        mock_narrative_data = {
            "company_arc": "Test narrative arc.",
            "year_sections": [],
            "narrative_chapters": [],
            "key_inflection_points": [],
            "current_chapter": "Now.",
            "years_covered": 3,
            "data_completeness": 0.8,
            "data_sources_used": ["financials"],
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
            MockNarrative.return_value.execute = AsyncMock(return_value={"success": True, "data": mock_narrative_data})

            result = await orch.analyze_ticker("AAPL")

        assert result["success"] is True
        assert "narrative" in result["analysis"]
        assert result["analysis"]["narrative"]["company_arc"] == "Test narrative arc."

    @pytest.mark.asyncio
    async def test_narrative_failure_is_nonblocking(self, test_config, tmp_path):
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
            MockNarrative.return_value.execute = AsyncMock(side_effect=Exception("LLM exploded"))

            result = await orch.analyze_ticker("AAPL")

        assert result["success"] is True
        assert result["analysis"].get("narrative") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_orchestrator.py::TestNarrativeIntegration -v`
Expected: FAIL — `cannot import name 'NarrativeAgent'`

- [ ] **Step 3: Add import and registry entry**

In `src/orchestrator.py`, add after the EarningsReviewAgent import:

```python
from .agents.narrative_agent import NarrativeAgent
```

Add to `AGENT_REGISTRY`:

```python
"narrative": {"class": NarrativeAgent, "requires": []},
```

- [ ] **Step 4: Add _run_narrative_agent() method**

Add after `_run_earnings_review_agent()` in `src/orchestrator.py`:

```python
    async def _run_narrative_agent(
        self,
        ticker: str,
        agent_results: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Run narrative agent for multi-year financial story (non-blocking).

        Args:
            ticker: Stock ticker
            agent_results: Results from all data agents

        Returns:
            Narrative output dict, or None on failure
        """
        try:
            narrative_agent = NarrativeAgent(ticker, self.config, agent_results)
            self._inject_shared_resources(narrative_agent)
            timeout = self.config.get("AGENT_TIMEOUT", 30)
            result = await asyncio.wait_for(
                narrative_agent.execute(),
                timeout=timeout,
            )
            if result.get("success"):
                return result.get("data")
            else:
                self.logger.warning(f"Narrative agent failed for {ticker}: {result.get('error')}")
                return None
        except asyncio.TimeoutError:
            self.logger.warning(f"Narrative agent timed out for {ticker}")
            return None
        except Exception as e:
            self.logger.warning(f"Narrative agent error for {ticker}: {e}")
            return None
```

- [ ] **Step 5: Expand asyncio.gather() to 4 agents**

In `analyze_ticker()`, replace:

```python
            final_analysis, thesis_result, earnings_review_result = await asyncio.gather(
                self._run_solution_agent(ticker, agent_results),
                self._run_thesis_agent(ticker, agent_results),
                self._run_earnings_review_agent(ticker, agent_results),
            )
            if thesis_result:
                final_analysis["thesis"] = thesis_result
            if earnings_review_result:
                final_analysis["earnings_review"] = earnings_review_result
```

With:

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

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_orchestrator.py -v`
Expected: All tests PASS (existing + 4 new)

- [ ] **Step 7: Commit**

```bash
git add src/orchestrator.py tests/test_orchestrator.py
git commit -m "feat(narrative): integrate NarrativeAgent into orchestrator synthesis phase (4-way gather)"
```

---

### Task 5: LLM Mock Tests & End-to-End

**Files:**
- Modify: `tests/test_agents/test_narrative_agent.py`

- [ ] **Step 1: Write LLM mock tests and prompt tests**

Append to `tests/test_agents/test_narrative_agent.py`:

```python
import json as json_module


MOCK_PASS1_RESPONSE = json_module.dumps({
    "per_year": [
        {
            "year": 2023, "revenue": "$355B", "revenue_growth": "1%",
            "gross_margin": "44%", "operating_margin": "29%",
            "key_events": ["iPhone 15 launch"],
            "management_themes": ["Operational efficiency"],
            "capital_moves": ["Continued buybacks"],
            "inflection_quarters": [],
        },
        {
            "year": 2024, "revenue": "$383B", "revenue_growth": "8%",
            "gross_margin": "46%", "operating_margin": "31%",
            "key_events": ["Vision Pro launch", "AI features announced"],
            "management_themes": ["AI integration", "Services growth"],
            "capital_moves": ["$90B buyback authorization"],
            "inflection_quarters": [
                {"quarter": "Q3'24", "event": "First China revenue decline in 3 years"},
            ],
        },
        {
            "year": 2025, "revenue": "$430B", "revenue_growth": "12%",
            "gross_margin": "47%", "operating_margin": "32%",
            "key_events": ["AI assistant launch", "India expansion"],
            "management_themes": ["AI monetization", "Geographic diversification"],
            "capital_moves": ["Increased capex for AI infrastructure"],
            "inflection_quarters": [],
        },
    ],
    "cross_year_themes": [
        "Services transition accelerating",
        "China exposure becoming a headwind",
        "AI as the next growth vector",
    ],
})

MOCK_PASS2_RESPONSE = json_module.dumps({
    "company_arc": "Over three years Apple evolved from a mature hardware company into an AI-powered services platform, navigating China headwinds while accelerating growth.",
    "year_sections": [
        {
            "year": 2023, "headline": "Consolidation: Flat revenue, margin preservation",
            "revenue_trajectory": "Revenue flat at $355B as iPhone cycle matured.",
            "margin_story": "Gross margin held at 44% through operational discipline.",
            "strategic_moves": ["iPhone 15 launch"],
            "management_commentary": "Focus on operational efficiency and services scale.",
            "capital_allocation": "Continued aggressive buyback program.",
            "quarterly_inflections": [],
        },
        {
            "year": 2024, "headline": "Inflection: Growth resumes, Vision Pro bets big",
            "revenue_trajectory": "Revenue accelerated to $383B (+8%) driven by services and iPhone upgrades.",
            "margin_story": "Gross margin expanded to 46% on services mix shift.",
            "strategic_moves": ["Vision Pro launch", "AI features announced across product line"],
            "management_commentary": "CEO pivoted messaging to AI integration as the next platform shift.",
            "capital_allocation": "$90B buyback authorization — largest in tech history.",
            "quarterly_inflections": [
                {"quarter": "Q3'24", "headline": "China cracks emerge", "details": "First YoY revenue decline in Greater China, driven by Huawei competition and macro headwinds.", "impact": "negative"},
            ],
        },
        {
            "year": 2025, "headline": "Acceleration: AI-driven growth hits its stride",
            "revenue_trajectory": "Revenue surged to $430B (+12%), the fastest growth in 4 years.",
            "margin_story": "Gross margin expanded further to 47% as AI services monetized.",
            "strategic_moves": ["AI assistant launch", "India manufacturing expansion"],
            "management_commentary": "AI monetization became the dominant narrative on earnings calls.",
            "capital_allocation": "Capex rose 30% for AI infrastructure while buybacks continued.",
            "quarterly_inflections": [],
        },
    ],
    "narrative_chapters": [
        {
            "title": "The Services Flywheel",
            "years_covered": "2023-2025",
            "narrative": "Services grew from 20% to 28% of revenue, becoming the primary margin driver and providing recurring revenue that smoothed hardware cycles.",
            "evidence": ["Services grew from $85B to $110B", "Gross margin expansion of 300bps driven by mix"],
        },
        {
            "title": "The China Question",
            "years_covered": "2024-2025",
            "narrative": "China shifted from growth engine to headwind as Huawei's resurgence and macro weakness eroded market share.",
            "evidence": ["Q3'24 first China decline", "Management pivoted messaging to India opportunity"],
        },
    ],
    "key_inflection_points": [
        "Q3'24: First China revenue decline signaled geographic risk",
        "Vision Pro launch marked Apple's next hardware bet",
        "2025 AI assistant launch as platform shift catalyst",
    ],
    "current_chapter": "Apple is in the early innings of AI monetization, with services growth providing a floor while China remains the key risk variable.",
})


class TestNarrativeLLMFlow:
    """Tests for two-pass LLM flow with mocked responses."""

    @pytest.mark.asyncio
    async def test_full_two_pass_flow(self):
        agent = NarrativeAgent("AAPL", {"llm_config": {"provider": "none"}, "NARRATIVE_YEARS": 3}, _make_agent_results())
        call_count = 0

        async def mock_call_llm(prompt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return MOCK_PASS1_RESPONSE
            return MOCK_PASS2_RESPONSE

        mock_financials = _make_mock_financials(3)
        mock_transcripts = _make_mock_transcripts(12)

        with patch.object(agent, "_call_llm", side_effect=mock_call_llm):
            with patch("src.llm_guardrails.validate_narrative_output", return_value=({
                **json_module.loads(MOCK_PASS2_RESPONSE),
                "years_covered": 3,
                "data_completeness": 1.0,
                "data_sources_used": ["financials", "transcripts", "fundamentals"],
            }, [])):
                result = await agent.analyze({
                    "financials": mock_financials,
                    "transcripts": mock_transcripts,
                    "agent_results": _make_agent_results(),
                })

        assert call_count == 2
        assert result["company_arc"] != ""
        assert len(result["year_sections"]) == 3
        assert len(result["narrative_chapters"]) == 2
        assert result["years_covered"] == 3

    @pytest.mark.asyncio
    async def test_pass1_failure_returns_empty(self):
        agent = NarrativeAgent("AAPL", {"llm_config": {"provider": "none"}, "NARRATIVE_YEARS": 3}, _make_agent_results())

        async def mock_fail(prompt):
            raise Exception("LLM unavailable")

        with patch.object(agent, "_call_llm", side_effect=mock_fail):
            result = await agent.analyze({
                "financials": _make_mock_financials(3),
                "transcripts": _make_mock_transcripts(12),
                "agent_results": _make_agent_results(),
            })

        assert "error" in result or "insufficient" in result.get("company_arc", "").lower()
        assert result["year_sections"] == []

    @pytest.mark.asyncio
    async def test_pass2_failure_returns_fallback(self):
        agent = NarrativeAgent("AAPL", {"llm_config": {"provider": "none"}, "NARRATIVE_YEARS": 3}, _make_agent_results())
        call_count = 0

        async def mock_call_llm(prompt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return MOCK_PASS1_RESPONSE
            raise Exception("Pass 2 failed")

        with patch.object(agent, "_call_llm", side_effect=mock_call_llm):
            result = await agent.analyze({
                "financials": _make_mock_financials(3),
                "transcripts": _make_mock_transcripts(12),
                "agent_results": _make_agent_results(),
            })

        assert result.get("pass2_failed") is True
        assert len(result["year_sections"]) == 3
        assert "extracted_facts" in result

    @pytest.mark.asyncio
    async def test_no_financials_returns_empty(self):
        agent = NarrativeAgent("AAPL", {"llm_config": {"provider": "none"}}, _make_agent_results())

        result = await agent.analyze({
            "financials": None,
            "transcripts": [],
            "agent_results": _make_agent_results(),
        })

        assert result["years_covered"] == 0
        assert result["year_sections"] == []


class TestNarrativePrompt:
    """Tests for prompt construction."""

    def test_pass1_prompt_contains_ticker(self):
        agent = NarrativeAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        financials = _make_mock_financials(3)
        transcripts = _make_mock_transcripts(4)
        years = agent._extract_available_years(financials)
        prompt = agent._build_pass1_prompt(financials, transcripts, years)
        assert "AAPL" in prompt

    def test_pass1_prompt_contains_financials(self):
        agent = NarrativeAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        financials = _make_mock_financials(3)
        transcripts = _make_mock_transcripts(4)
        years = agent._extract_available_years(financials)
        prompt = agent._build_pass1_prompt(financials, transcripts, years)
        assert "FY2025" in prompt or "2025" in prompt
        assert "FY2023" in prompt or "2023" in prompt

    def test_pass2_prompt_contains_facts(self):
        agent = NarrativeAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        facts = json_module.loads(MOCK_PASS1_RESPONSE)
        prompt = agent._build_pass2_prompt(facts, "AAPL")
        assert "AAPL" in prompt
        assert "$355B" in prompt  # 2023 revenue from facts

    def test_pass1_prompt_includes_guardrail_instructions(self):
        agent = NarrativeAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        financials = _make_mock_financials(3)
        transcripts = _make_mock_transcripts(4)
        years = agent._extract_available_years(financials)
        prompt = agent._build_pass1_prompt(financials, transcripts, years)
        assert "Do NOT infer" in prompt or "Do not infer" in prompt
```

- [ ] **Step 2: Run all narrative agent tests**

Run: `python -m pytest tests/test_agents/test_narrative_agent.py -v`
Expected: All tests PASS (6 models + 12 data/completeness + 5 guardrails + 4 LLM + 4 prompt = 31)

- [ ] **Step 3: Commit**

```bash
git add tests/test_agents/test_narrative_agent.py
git commit -m "test(narrative): add LLM mock tests, prompt validation, and end-to-end flow tests"
```

---

### Task 6: Full Test Suite Verification

**Files:** None modified — verification only.

- [ ] **Step 1: Run the full test suite**

Run: `python -m pytest tests/ -v --tb=short`
Expected: All tests PASS, no regressions.

- [ ] **Step 2: Run narrative-specific tests with coverage**

Run: `python -m pytest tests/test_agents/test_narrative_agent.py --cov=src.agents.narrative_agent --cov=src.llm_guardrails --cov-report=term-missing -v`
Expected: Good coverage of narrative_agent.py and the new guardrails function.

- [ ] **Step 3: Commit any test fixes if needed**

Only if the full suite revealed issues.
