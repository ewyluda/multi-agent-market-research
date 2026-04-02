# Earnings Review Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a single-pass LLM synthesis agent that produces structured earnings call digests with deterministic beat/miss computation and sector-specific KPI extraction.

**Architecture:** EarningsReviewAgent inherits BaseAgent, takes agent_results in constructor (like ThesisAgent/SolutionAgent). Deterministic beat/miss computed from EPS history. Single LLM pass extracts exec summary, KPIs, guidance deltas, quotes, thesis impact, one-offs. Sector KPI templates guide extraction. Runs parallel with solution+thesis in synthesis phase via asyncio.gather(). Partial results returned when transcript unavailable.

**Tech Stack:** Python, Pydantic, anthropic/openai SDKs, pytest

**Spec:** `docs/superpowers/specs/2026-04-02-earnings-review-agent-design.md`

---

### Task 1: Pydantic Models

**Files:**
- Modify: `src/models.py`
- Create: `tests/test_agents/test_earnings_review_agent.py`

- [ ] **Step 1: Create test file with model validation tests**

Create `tests/test_agents/test_earnings_review_agent.py`:

```python
"""Tests for EarningsReviewAgent — models, deterministic, LLM, guardrails."""

import pytest
from pydantic import ValidationError
from src.models import BeatMiss, GuidanceDelta, KPIRow, EarningsReviewOutput


class TestEarningsReviewModels:
    """Pydantic model validation tests."""

    def test_beat_miss_valid(self):
        bm = BeatMiss(
            metric="EPS",
            actual=2.40,
            estimate=2.15,
            surprise_pct=11.63,
            verdict="beat",
        )
        assert bm.verdict == "beat"
        assert bm.actual == 2.40

    def test_beat_miss_inline(self):
        bm = BeatMiss(
            metric="Revenue",
            actual=95.0,
            estimate=94.8,
            surprise_pct=0.2,
            verdict="inline",
        )
        assert bm.verdict == "inline"

    def test_guidance_delta_valid(self):
        gd = GuidanceDelta(
            metric="Revenue",
            prior_value="$90-92B",
            new_value="$93-95B",
            direction="raised",
        )
        assert gd.direction == "raised"

    def test_kpi_row_valid(self):
        kpi = KPIRow(
            metric="ARR",
            value="$5.2B",
            prior_value="$4.8B",
            yoy_change="+8.3%",
            source="call_disclosed",
        )
        assert kpi.source == "call_disclosed"

    def test_kpi_row_with_none_values(self):
        kpi = KPIRow(
            metric="Net Revenue Retention",
            value="112%",
            prior_value=None,
            yoy_change=None,
            source="reported",
        )
        assert kpi.prior_value is None

    def test_earnings_review_output_valid(self):
        output = EarningsReviewOutput(
            executive_summary="Strong quarter with EPS beat.",
            beat_miss=[BeatMiss(metric="EPS", actual=2.40, estimate=2.15, surprise_pct=11.63, verdict="beat")],
            guidance_deltas=[GuidanceDelta(metric="Revenue", prior_value="$90B", new_value="$93B", direction="raised")],
            kpi_table=[KPIRow(metric="ARR", value="$5.2B", prior_value=None, yoy_change=None, source="reported")],
            management_tone="confident",
            notable_quotes=["We see strong momentum in AI."],
            thesis_impact="Confirms bull case on growth.",
            one_offs=["$200M restructuring charge"],
            sector_template="Technology",
            data_completeness=0.85,
            data_sources_used=["earnings", "fundamentals"],
        )
        assert output.data_completeness == 0.85
        assert len(output.beat_miss) == 1

    def test_earnings_review_output_completeness_clamped(self):
        with pytest.raises(ValidationError):
            EarningsReviewOutput(
                executive_summary="x",
                beat_miss=[],
                guidance_deltas=[],
                kpi_table=[],
                management_tone="neutral",
                notable_quotes=[],
                thesis_impact="",
                one_offs=[],
                sector_template="default",
                data_completeness=1.5,
                data_sources_used=[],
            )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_agents/test_earnings_review_agent.py -v`
Expected: FAIL — `ImportError: cannot import name 'BeatMiss' from 'src.models'`

- [ ] **Step 3: Add Pydantic models to src/models.py**

Add at the end of `src/models.py`, after the Thesis Agent models section:

```python
# ── Earnings Review Agent models ──────────────────────────────────────────────


class BeatMiss(BaseModel):
    """Earnings beat/miss for a single metric (deterministic)."""
    metric: str = Field(..., description="Metric name: EPS, Revenue")
    actual: Optional[float] = Field(default=None, description="Reported value")
    estimate: Optional[float] = Field(default=None, description="Consensus estimate")
    surprise_pct: Optional[float] = Field(default=None, description="Surprise percentage")
    verdict: str = Field(..., description="beat, miss, or inline")


class GuidanceDelta(BaseModel):
    """Forward guidance change for a single metric."""
    metric: str = Field(..., description="Revenue, EPS, Gross Margin, etc.")
    prior_value: Optional[str] = Field(default=None, description="Prior guidance")
    new_value: Optional[str] = Field(default=None, description="New guidance")
    direction: str = Field(..., description="raised, lowered, maintained, introduced, withdrawn")


class KPIRow(BaseModel):
    """A single KPI from the earnings call."""
    metric: str = Field(..., description="KPI name")
    value: Optional[str] = Field(default=None, description="Current value")
    prior_value: Optional[str] = Field(default=None, description="Prior quarter value")
    yoy_change: Optional[str] = Field(default=None, description="Year-over-year change")
    source: str = Field(..., description="reported, call_disclosed, or calculated")


class EarningsReviewOutput(BaseModel):
    """Complete structured earnings review output."""
    executive_summary: str = Field(..., description="3-5 sentence key takeaways")
    beat_miss: List[BeatMiss] = Field(default=[], description="EPS + Revenue beat/miss")
    guidance_deltas: List[GuidanceDelta] = Field(default=[], description="Forward guidance changes")
    kpi_table: List[KPIRow] = Field(default=[], description="8-15 key metrics")
    management_tone: str = Field(..., description="confident, cautious, defensive, etc.")
    notable_quotes: List[str] = Field(default=[], description="2-3 notable management quotes")
    thesis_impact: str = Field(default="", description="How this quarter affects investment thesis")
    one_offs: List[str] = Field(default=[], description="Non-recurring items")
    sector_template: str = Field(default="default", description="Which sector template was used")
    data_completeness: float = Field(..., ge=0.0, le=1.0, description="0.0-1.0 data quality score")
    data_sources_used: List[str] = Field(default=[], description="Which agents contributed data")
    error: Optional[str] = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_agents/test_earnings_review_agent.py::TestEarningsReviewModels -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/models.py tests/test_agents/test_earnings_review_agent.py
git commit -m "feat(earnings-review): add Pydantic models for EarningsReviewOutput schema"
```

---

### Task 2: EarningsReviewAgent — Deterministic Beat/Miss & Sector Templates

**Files:**
- Create: `src/agents/earnings_review_agent.py`
- Modify: `tests/test_agents/test_earnings_review_agent.py`

- [ ] **Step 1: Write deterministic beat/miss and sector template tests**

Append to `tests/test_agents/test_earnings_review_agent.py`:

```python
from src.agents.earnings_review_agent import EarningsReviewAgent, SECTOR_KPI_TEMPLATES, DEFAULT_KPI_TEMPLATE


def _make_agent_results(
    earnings=True, fundamentals=True, market=True,
    has_transcript=True,
):
    """Build mock agent_results dict for earnings review tests."""
    results = {}
    if earnings:
        earnings_data = {
            "highlights": [
                {"tag": "BEAT", "text": "EPS beat by 12%"},
                {"tag": "NEW", "text": "Launched AI assistant product"},
            ],
            "guidance": [
                {"metric": "Revenue", "prior": "$90-92B", "current": "$93-95B", "direction": "raised"},
            ],
            "tone": "confident",
            "guidance_direction": "raised",
            "qa_highlights": [
                {"analyst": "John Smith", "firm": "Goldman Sachs", "topic": "AI spend",
                 "question": "What are your capex plans for AI?",
                 "answer": "We plan to increase AI investment significantly next year."},
            ],
            "tone_analysis": {"confidence": 78, "specificity": 65, "defensiveness": 20, "forward_looking": 72, "hedging": 30},
            "eps_history": [
                {"quarter": "Q1'26", "actual": 2.40, "estimate": 2.15, "surprise_pct": 11.63},
                {"quarter": "Q4'25", "actual": 2.10, "estimate": 2.05, "surprise_pct": 2.44},
                {"quarter": "Q3'25", "actual": 1.95, "estimate": 2.00, "surprise_pct": -2.50},
            ],
            "analysis": "Strong quarter driven by services growth.",
            "data_source": "fmp",
        }
        if not has_transcript:
            # Simulate EPS data available but no transcript analysis
            earnings_data = {
                "highlights": [],
                "guidance": [],
                "tone": "neutral",
                "guidance_direction": "maintained",
                "qa_highlights": [],
                "tone_analysis": {"confidence": 50, "specificity": 50, "defensiveness": 50, "forward_looking": 50, "hedging": 50},
                "eps_history": [
                    {"quarter": "Q1'26", "actual": 2.40, "estimate": 2.15, "surprise_pct": 11.63},
                ],
                "analysis": "No earnings call transcripts available for analysis.",
                "data_source": "none",
            }
        results["earnings"] = {"success": True, "data": earnings_data}
    else:
        results["earnings"] = {"success": False, "data": None, "error": "No earnings data"}

    if fundamentals:
        results["fundamentals"] = {
            "success": True,
            "data": {
                "company_name": "Apple Inc.",
                "sector": "Technology",
                "revenue": 383000000000,
                "revenue_growth": 0.08,
                "gross_margin": 0.46,
                "business_description": "Designs consumer electronics and software.",
                "data_source": "fmp",
            },
        }
    else:
        results["fundamentals"] = {"success": False, "data": None, "error": "Mock disabled"}

    if market:
        results["market"] = {
            "success": True,
            "data": {
                "current_price": 195.0,
                "high_52w": 220.0,
                "low_52w": 165.0,
                "price_change_1m": 0.05,
                "data_source": "fmp",
            },
        }
    else:
        results["market"] = {"success": False, "data": None, "error": "Mock disabled"}

    return results


class TestDeterministicBeatMiss:
    """Tests for deterministic EPS/revenue beat/miss computation."""

    def test_eps_beat(self):
        agent = EarningsReviewAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        beat_miss = agent._compute_beat_miss()
        eps = next((bm for bm in beat_miss if bm["metric"] == "EPS"), None)
        assert eps is not None
        assert eps["verdict"] == "beat"
        assert eps["actual"] == 2.40
        assert eps["estimate"] == 2.15
        assert eps["surprise_pct"] == 11.63

    def test_eps_miss(self):
        results = _make_agent_results()
        results["earnings"]["data"]["eps_history"] = [
            {"quarter": "Q1'26", "actual": 1.80, "estimate": 2.15, "surprise_pct": -16.28},
        ]
        agent = EarningsReviewAgent("AAPL", {"llm_config": {}}, results)
        beat_miss = agent._compute_beat_miss()
        eps = next((bm for bm in beat_miss if bm["metric"] == "EPS"), None)
        assert eps is not None
        assert eps["verdict"] == "miss"

    def test_eps_inline(self):
        results = _make_agent_results()
        results["earnings"]["data"]["eps_history"] = [
            {"quarter": "Q1'26", "actual": 2.15, "estimate": 2.14, "surprise_pct": 0.47},
        ]
        agent = EarningsReviewAgent("AAPL", {"llm_config": {}}, results)
        beat_miss = agent._compute_beat_miss()
        eps = next((bm for bm in beat_miss if bm["metric"] == "EPS"), None)
        assert eps is not None
        assert eps["verdict"] == "inline"

    def test_no_eps_history_returns_empty(self):
        results = _make_agent_results()
        results["earnings"]["data"]["eps_history"] = []
        agent = EarningsReviewAgent("AAPL", {"llm_config": {}}, results)
        beat_miss = agent._compute_beat_miss()
        assert len(beat_miss) == 0

    def test_no_earnings_data_returns_empty(self):
        results = _make_agent_results(earnings=False)
        agent = EarningsReviewAgent("AAPL", {"llm_config": {}}, results)
        beat_miss = agent._compute_beat_miss()
        assert len(beat_miss) == 0


class TestSectorTemplates:
    """Tests for sector KPI template selection."""

    def test_technology_sector_returns_tech_template(self):
        agent = EarningsReviewAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        template = agent._get_sector_template()
        assert template == SECTOR_KPI_TEMPLATES["Technology"]
        assert "ARR" in template

    def test_unknown_sector_returns_default(self):
        results = _make_agent_results()
        results["fundamentals"]["data"]["sector"] = "Space Mining"
        agent = EarningsReviewAgent("AAPL", {"llm_config": {}}, results)
        template = agent._get_sector_template()
        assert template == DEFAULT_KPI_TEMPLATE

    def test_no_fundamentals_returns_default(self):
        results = _make_agent_results(fundamentals=False)
        agent = EarningsReviewAgent("AAPL", {"llm_config": {}}, results)
        template = agent._get_sector_template()
        assert template == DEFAULT_KPI_TEMPLATE

    def test_sector_template_name_tracked(self):
        agent = EarningsReviewAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        name = agent._get_sector_template_name()
        assert name == "Technology"


class TestDataCompleteness:
    """Tests for deterministic completeness score."""

    def test_full_data_completeness(self):
        agent = EarningsReviewAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        score = agent._compute_data_completeness()
        assert score == pytest.approx(1.0, abs=0.01)

    def test_no_market_completeness(self):
        agent = EarningsReviewAgent("AAPL", {"llm_config": {}}, _make_agent_results(market=False))
        score = agent._compute_data_completeness()
        # Missing market (0.20) = 0.80
        assert score == pytest.approx(0.80, abs=0.01)

    def test_partial_earnings_completeness(self):
        agent = EarningsReviewAgent("AAPL", {"llm_config": {}}, _make_agent_results(has_transcript=False))
        score = agent._compute_data_completeness()
        # Earnings partial (0.15 instead of 0.50) + fundamentals(0.30) + market(0.20) = 0.65
        assert score == pytest.approx(0.65, abs=0.01)

    def test_no_earnings_completeness(self):
        agent = EarningsReviewAgent("AAPL", {"llm_config": {}}, _make_agent_results(earnings=False))
        score = agent._compute_data_completeness()
        # Missing earnings (0.50) = 0.50
        assert score == pytest.approx(0.50, abs=0.01)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_agents/test_earnings_review_agent.py::TestDeterministicBeatMiss -v`
Expected: FAIL — `ImportError: cannot import name 'EarningsReviewAgent'`

- [ ] **Step 3: Implement EarningsReviewAgent**

Create `src/agents/earnings_review_agent.py`:

```python
"""Earnings review agent — structured earnings digest with deterministic beat/miss and sector KPIs."""

import asyncio
import json
import re
from typing import Dict, Any, List, Optional, Tuple

import anthropic
from openai import OpenAI

from .base_agent import BaseAgent

# ─── Sector KPI Templates ───────────────────────────────────────────────────

SECTOR_KPI_TEMPLATES = {
    "Technology": ["Revenue Growth", "Gross Margin", "Operating Margin", "R&D % of Revenue",
                   "Free Cash Flow", "Customer Count", "ARR", "Net Revenue Retention"],
    "Financial Services": ["Net Interest Margin", "Provision Ratio", "Loan Growth",
                           "CET1 Ratio", "ROE", "Efficiency Ratio", "Net Charge-offs"],
    "Consumer Cyclical": ["Same-Store Sales", "E-commerce Mix", "Inventory Turns",
                          "Gross Margin", "Average Transaction Value", "Store Count"],
    "Healthcare": ["Revenue Growth", "Pipeline Updates", "R&D Spend", "Gross Margin",
                   "Patient Volume", "Reimbursement Rates"],
    "Industrials": ["Book-to-Bill Ratio", "Backlog", "Utilization Rate", "Organic Growth",
                    "Margin Expansion", "Free Cash Flow Conversion"],
    "Communication Services": ["Subscriber Growth", "ARPU", "Churn Rate", "Content Spend",
                               "Ad Revenue Growth", "Engagement Metrics"],
    "Semiconductors": ["Book-to-Bill", "ASPs", "Utilization", "Design Wins",
                       "Inventory Days", "Gross Margin"],
}

DEFAULT_KPI_TEMPLATE = ["Revenue Growth", "Gross Margin", "Operating Margin",
                        "Free Cash Flow", "Debt/EBITDA", "Capex"]

# ─── Completeness Weights ────────────────────────────────────────────────────

_COMPLETENESS_WEIGHTS = {
    "earnings": 0.50,
    "fundamentals": 0.30,
    "market": 0.20,
}


class EarningsReviewAgent(BaseAgent):
    """Agent that produces structured earnings call digests.

    Deterministic beat/miss from EPS history + single-pass LLM for
    exec summary, KPI extraction, guidance deltas, quotes, thesis impact.

    Runs in the synthesis phase, parallel with SolutionAgent and ThesisAgent.
    """

    def __init__(self, ticker: str, config: Dict[str, Any], agent_results: Dict[str, Any]):
        super().__init__(ticker, config)
        self.agent_results = agent_results

    async def fetch_data(self) -> Dict[str, Any]:
        return self.agent_results

    async def analyze(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        earnings_data = self._get_agent_data("earnings")
        completeness = self._compute_data_completeness()
        sources = self._get_available_sources()

        # Deterministic beat/miss (always computed if EPS data exists)
        beat_miss = self._compute_beat_miss()
        sector_template_name = self._get_sector_template_name()

        # Check if we have enough data for LLM analysis
        has_transcript = self._has_transcript_data()
        if not has_transcript:
            return self._partial_result(beat_miss, sector_template_name, completeness, sources)

        if not earnings_data:
            return self._empty_result(sources)

        # Single-pass LLM for structured extraction
        try:
            prompt = self._build_prompt()
            llm_response = await self._call_llm(prompt)
            parsed = self._parse_llm_response(llm_response)
        except Exception as e:
            self.logger.warning(f"Earnings review LLM failed for {self.ticker}: {e}")
            return self._partial_result(beat_miss, sector_template_name, completeness, sources)

        result = {
            "executive_summary": parsed.get("executive_summary", ""),
            "beat_miss": beat_miss,
            "guidance_deltas": parsed.get("guidance_deltas", []),
            "kpi_table": parsed.get("kpi_table", []),
            "management_tone": parsed.get("management_tone", "neutral"),
            "notable_quotes": parsed.get("notable_quotes", []),
            "thesis_impact": parsed.get("thesis_impact", ""),
            "one_offs": parsed.get("one_offs", []),
            "sector_template": sector_template_name,
            "data_completeness": completeness,
            "data_sources_used": sources,
        }

        # Guardrails
        from ..llm_guardrails import validate_earnings_review_output
        validated, warnings = validate_earnings_review_output(result, self.agent_results)
        if warnings:
            validated["guardrail_warnings"] = warnings
        return validated

    # ─── Deterministic Computation ───────────────────────────────────────────

    def _compute_beat_miss(self) -> List[Dict[str, Any]]:
        """Compute deterministic beat/miss from EPS history."""
        earnings_data = self._get_agent_data("earnings")
        if not earnings_data:
            return []

        results = []
        eps_history = earnings_data.get("eps_history", [])
        if eps_history:
            latest = eps_history[0]
            actual = latest.get("actual")
            estimate = latest.get("estimate")
            surprise_pct = latest.get("surprise_pct")
            if actual is not None and estimate is not None:
                if surprise_pct is None:
                    surprise_pct = ((actual - estimate) / abs(estimate) * 100) if estimate != 0 else 0.0
                    surprise_pct = round(surprise_pct, 2)
                verdict = "beat" if surprise_pct > 1.0 else "miss" if surprise_pct < -1.0 else "inline"
                results.append({
                    "metric": "EPS",
                    "actual": actual,
                    "estimate": estimate,
                    "surprise_pct": surprise_pct,
                    "verdict": verdict,
                })
        return results

    def _get_sector_template(self) -> List[str]:
        """Get sector-specific KPI template."""
        fund_data = self._get_agent_data("fundamentals")
        if not fund_data:
            return DEFAULT_KPI_TEMPLATE
        sector = fund_data.get("sector", "")
        return SECTOR_KPI_TEMPLATES.get(sector, DEFAULT_KPI_TEMPLATE)

    def _get_sector_template_name(self) -> str:
        """Get the name of the sector template being used."""
        fund_data = self._get_agent_data("fundamentals")
        if not fund_data:
            return "default"
        sector = fund_data.get("sector", "")
        return sector if sector in SECTOR_KPI_TEMPLATES else "default"

    def _has_transcript_data(self) -> bool:
        """Check if meaningful transcript analysis is available."""
        earnings_data = self._get_agent_data("earnings")
        if not earnings_data:
            return False
        # If highlights are empty and analysis says "No earnings call transcripts", no transcript
        highlights = earnings_data.get("highlights", [])
        data_source = earnings_data.get("data_source", "")
        return len(highlights) > 0 and data_source != "none"

    # ─── Data Completeness ───────────────────────────────────────────────────

    def _compute_data_completeness(self) -> float:
        """Compute deterministic data completeness score (0.0-1.0)."""
        score = 0.0
        for agent_name, weight in _COMPLETENESS_WEIGHTS.items():
            result = self.agent_results.get(agent_name, {})
            if not (isinstance(result, dict) and result.get("success") and result.get("data")):
                continue
            if agent_name == "earnings":
                # Partial credit if EPS only (no transcript)
                if self._has_transcript_data():
                    score += weight  # Full 0.50
                else:
                    score += 0.15  # Partial credit
            else:
                score += weight
        return round(score, 2)

    def _get_available_sources(self) -> List[str]:
        """Get list of agents that have data."""
        sources = []
        for agent_name in _COMPLETENESS_WEIGHTS:
            result = self.agent_results.get(agent_name, {})
            if isinstance(result, dict) and result.get("success") and result.get("data"):
                sources.append(agent_name)
        return sources

    def _get_agent_data(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """Safely extract data dict from an agent result."""
        result = self.agent_results.get(agent_name, {})
        if isinstance(result, dict) and result.get("success"):
            return result.get("data")
        return None

    # ─── LLM Prompt ──────────────────────────────────────────────────────────

    def _build_prompt(self) -> str:
        """Build the single-pass LLM prompt for earnings review extraction."""
        earnings_data = self._get_agent_data("earnings") or {}
        fund_data = self._get_agent_data("fundamentals") or {}
        market_data = self._get_agent_data("market") or {}

        sector_template = self._get_sector_template()
        template_str = ", ".join(sector_template)

        # Format earnings context
        highlights = earnings_data.get("highlights", [])
        highlights_str = "\n".join(
            f"  [{h.get('tag', '?')}] {h.get('text', '')}" for h in highlights[:6]
        ) or "  No highlights available."

        guidance = earnings_data.get("guidance", [])
        guidance_str = "\n".join(
            f"  {g.get('metric', '?')}: {g.get('prior', '?')} → {g.get('current', '?')} ({g.get('direction', '?')})"
            for g in guidance[:5]
        ) or "  No guidance data."

        qa = earnings_data.get("qa_highlights", [])
        qa_str = "\n".join(
            f"  {q.get('analyst', '?')} ({q.get('firm', '?')}): {q.get('topic', '?')}\n    Q: {q.get('question', '')}\n    A: {q.get('answer', '')}"
            for q in qa[:4]
        ) or "  No Q&A highlights."

        tone = earnings_data.get("tone_analysis", {})
        tone_str = ", ".join(f"{k}: {v}" for k, v in tone.items()) if tone else "N/A"

        eps_history = earnings_data.get("eps_history", [])[:4]
        eps_str = " | ".join(
            f"{e.get('quarter', '?')}: ${e.get('actual', '?')} vs ${e.get('estimate', '?')} ({e.get('surprise_pct', 0):+.1f}%)"
            for e in eps_history
        ) or "N/A"

        analysis = earnings_data.get("analysis", "")

        # Format fundamentals context
        company = fund_data.get("company_name", self.ticker)
        sector = fund_data.get("sector", "N/A")
        revenue = fund_data.get("revenue")
        rev_str = f"${revenue / 1e9:.1f}B" if revenue else "N/A"
        margin = fund_data.get("gross_margin")
        margin_str = f"{margin * 100:.1f}%" if margin is not None else "N/A"

        # Format market context
        price = market_data.get("current_price", "N/A")
        high52 = market_data.get("high_52w", "N/A")
        low52 = market_data.get("low_52w", "N/A")
        chg1m = market_data.get("price_change_1m")
        chg_str = f"{chg1m * 100:+.1f}%" if chg1m is not None else "N/A"

        return f"""You are a senior equity research analyst writing a structured earnings review for {self.ticker} ({company}).

Produce a structured digest of this earnings call. Return a JSON object with EXACTLY these keys — no markdown, no explanation, just raw JSON:

{{
  "executive_summary": "3-5 sentence summary of the key takeaways from this earnings call",
  "guidance_deltas": [
    {{"metric": "Revenue|EPS|Gross Margin|...", "prior_value": "prior guidance or N/A", "new_value": "new guidance", "direction": "raised|lowered|maintained|introduced|withdrawn"}}
  ],
  "kpi_table": [
    {{"metric": "KPI name", "value": "current value", "prior_value": "prior quarter or null", "yoy_change": "YoY change or null", "source": "reported|call_disclosed|calculated"}}
  ],
  "management_tone": "confident|cautious|defensive|evasive|optimistic",
  "notable_quotes": ["2-3 short, impactful management quotes"],
  "thesis_impact": "1-2 sentences on how this quarter affects the investment thesis",
  "one_offs": ["Non-recurring items that distort reported results"]
}}

Rules:
- kpi_table: Prioritize these sector-specific metrics: [{template_str}]. Also include any additional KPIs disclosed on the call that are NOT in this list.
- kpi_table source field: "reported" = in financial statements, "call_disclosed" = mentioned only on the call, "calculated" = you derived it.
- guidance_deltas: Extract all forward guidance changes. Compare to prior quarter guidance if available.
- notable_quotes: Short (1-2 sentences), direct quotes from management that are most investment-relevant.
- one_offs: Only include items that are genuinely non-recurring and material.
- thesis_impact: Be specific about what changed for the investment thesis — don't just restate the summary.

--- COMPANY ---
{company} | Sector: {sector} | Revenue: {rev_str} | Gross Margin: {margin_str}
Price: ${price} | 52w: ${low52}-${high52} | 1M Change: {chg_str}

--- EARNINGS HIGHLIGHTS ---
{highlights_str}

--- GUIDANCE ---
{guidance_str}

--- Q&A HIGHLIGHTS ---
{qa_str}

--- TONE ANALYSIS ---
{tone_str}

--- EPS HISTORY ---
{eps_str}

--- ANALYST NARRATIVE ---
{analysis}
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
                temperature=llm_config.get("temperature", 0.3),
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
                temperature=llm_config.get("temperature", 0.3),
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

    def _empty_result(self, sources: List[str]) -> Dict[str, Any]:
        """Return empty result when no earnings data available."""
        return {
            "executive_summary": f"No earnings data available for {self.ticker}.",
            "beat_miss": [],
            "guidance_deltas": [],
            "kpi_table": [],
            "management_tone": "unknown",
            "notable_quotes": [],
            "thesis_impact": "",
            "one_offs": [],
            "sector_template": self._get_sector_template_name(),
            "data_completeness": 0.0,
            "data_sources_used": sources,
            "error": "No earnings data available.",
        }

    def _partial_result(
        self,
        beat_miss: List[Dict[str, Any]],
        sector_template_name: str,
        completeness: float,
        sources: List[str],
    ) -> Dict[str, Any]:
        """Return partial result with deterministic fields when transcript unavailable."""
        return {
            "executive_summary": f"No earnings transcript available for detailed review of {self.ticker}.",
            "beat_miss": beat_miss,
            "guidance_deltas": [],
            "kpi_table": [],
            "management_tone": "unknown",
            "notable_quotes": [],
            "thesis_impact": "",
            "one_offs": [],
            "sector_template": sector_template_name,
            "data_completeness": completeness,
            "data_sources_used": sources,
            "partial": True,
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_agents/test_earnings_review_agent.py::TestDeterministicBeatMiss tests/test_agents/test_earnings_review_agent.py::TestSectorTemplates tests/test_agents/test_earnings_review_agent.py::TestDataCompleteness -v`
Expected: All 13 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/agents/earnings_review_agent.py tests/test_agents/test_earnings_review_agent.py
git commit -m "feat(earnings-review): add EarningsReviewAgent with deterministic beat/miss, sector templates, and LLM prompt"
```

---

### Task 3: LLM Guardrails — validate_earnings_review_output()

**Files:**
- Modify: `src/llm_guardrails.py`
- Modify: `tests/test_agents/test_earnings_review_agent.py`

- [ ] **Step 1: Write guardrail tests**

Append to `tests/test_agents/test_earnings_review_agent.py`:

```python
from src.llm_guardrails import validate_earnings_review_output


def _make_valid_review():
    """Build a valid earnings review output dict."""
    return {
        "executive_summary": "Strong quarter with EPS beat and raised guidance.",
        "beat_miss": [{"metric": "EPS", "actual": 2.40, "estimate": 2.15, "surprise_pct": 11.63, "verdict": "beat"}],
        "guidance_deltas": [{"metric": "Revenue", "prior_value": "$90-92B", "new_value": "$93-95B", "direction": "raised"}],
        "kpi_table": [
            {"metric": "Gross Margin", "value": "46%", "prior_value": "45%", "yoy_change": "+1pp", "source": "reported"},
            {"metric": "ARR", "value": "$5.2B", "prior_value": "$4.8B", "yoy_change": "+8.3%", "source": "call_disclosed"},
        ],
        "management_tone": "confident",
        "notable_quotes": ["We see strong momentum in AI."],
        "thesis_impact": "Confirms bull case on growth.",
        "one_offs": ["$200M restructuring charge"],
        "sector_template": "Technology",
        "data_completeness": 0.85,
        "data_sources_used": ["earnings", "fundamentals"],
    }


class TestEarningsReviewGuardrails:
    """Tests for validate_earnings_review_output() in llm_guardrails.py."""

    def test_valid_review_passes_cleanly(self):
        review = _make_valid_review()
        validated, warnings = validate_earnings_review_output(review, _make_agent_results())
        assert validated["executive_summary"] != ""
        assert isinstance(warnings, list)

    def test_unreasonable_kpi_flagged(self):
        review = _make_valid_review()
        review["kpi_table"].append(
            {"metric": "Gross Margin", "value": "150%", "prior_value": None, "yoy_change": None, "source": "reported"}
        )
        validated, warnings = validate_earnings_review_output(review, _make_agent_results())
        assert any("margin" in w.lower() or "unreasonable" in w.lower() or "150" in w for w in warnings)

    def test_guidance_tone_contradiction_flagged(self):
        review = _make_valid_review()
        review["guidance_deltas"] = [{"metric": "Revenue", "prior_value": "$90B", "new_value": "$95B", "direction": "raised"}]
        results = _make_agent_results()
        results["earnings"]["data"]["tone"] = "defensive"
        validated, warnings = validate_earnings_review_output(review, results)
        assert any("guidance" in w.lower() or "tone" in w.lower() or "contradict" in w.lower() for w in warnings)

    def test_data_completeness_overridden(self):
        review = _make_valid_review()
        review["data_completeness"] = 0.99
        validated, warnings = validate_earnings_review_output(review, _make_agent_results())
        assert validated["data_completeness"] != 0.99

    def test_beat_miss_sanity_check(self):
        review = _make_valid_review()
        # Verdict says beat but surprise is negative
        review["beat_miss"] = [{"metric": "EPS", "actual": 1.80, "estimate": 2.15, "surprise_pct": -16.28, "verdict": "beat"}]
        validated, warnings = validate_earnings_review_output(review, _make_agent_results())
        assert any("beat" in w.lower() or "verdict" in w.lower() or "mismatch" in w.lower() for w in warnings)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_agents/test_earnings_review_agent.py::TestEarningsReviewGuardrails -v`
Expected: FAIL — `ImportError: cannot import name 'validate_earnings_review_output'`

- [ ] **Step 3: Implement validate_earnings_review_output()**

Add at the end of `src/llm_guardrails.py`:

```python
# ─── Earnings Review Output ────────────────────────────────────────────────


def validate_earnings_review_output(
    review: Dict[str, Any],
    agent_results: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[str]]:
    """Validate earnings review agent output.

    Checks:
        1. Beat/miss sanity — verdict matches surprise_pct direction.
        2. KPI value validation — flag unreasonable values.
        3. Guidance/tone consistency — flag raised guidance with defensive tone.
        4. Data completeness override — deterministic recalculation.

    Returns:
        (validated_review, warnings)
    """
    warnings: List[str] = []
    validated = dict(review)

    # 1. Beat/miss sanity
    for bm in validated.get("beat_miss", []):
        surprise = bm.get("surprise_pct")
        verdict = bm.get("verdict", "")
        if surprise is not None:
            expected_verdict = "beat" if surprise > 1.0 else "miss" if surprise < -1.0 else "inline"
            if verdict != expected_verdict:
                warnings.append(
                    f"Beat/miss verdict mismatch for {bm.get('metric', '?')}: "
                    f"verdict='{verdict}' but surprise={surprise:.1f}% implies '{expected_verdict}'"
                )

    # 2. KPI value validation
    for kpi in validated.get("kpi_table", []):
        value_str = (kpi.get("value") or "").strip()
        metric_lower = kpi.get("metric", "").lower()
        # Check percentage values > 100% for margin-type metrics
        if "margin" in metric_lower or "retention" in metric_lower:
            pct_match = re.search(r"([\d.]+)\s*%", value_str)
            if pct_match:
                pct_val = float(pct_match.group(1))
                # Net Revenue Retention can exceed 100%, margins generally shouldn't exceed ~80%
                if "retention" not in metric_lower and pct_val > 100:
                    warnings.append(
                        f"Unreasonable KPI value: {kpi['metric']} = {value_str} (margin > 100%)"
                    )

    # 3. Guidance/tone consistency
    guidance_deltas = validated.get("guidance_deltas", [])
    has_raised = any(g.get("direction") == "raised" for g in guidance_deltas)
    earnings_result = agent_results.get("earnings", {})
    earnings_data = earnings_result.get("data") if isinstance(earnings_result, dict) else None
    if earnings_data and has_raised:
        tone = earnings_data.get("tone", "")
        if tone in ("defensive", "evasive"):
            warnings.append(
                f"Guidance/tone contradiction: guidance raised but EarningsAgent tone is '{tone}'"
            )

    # 4. Data completeness override
    completeness_weights = {"earnings": 0.50, "fundamentals": 0.30, "market": 0.20}
    deterministic_completeness = 0.0
    for agent_name, weight in completeness_weights.items():
        result = agent_results.get(agent_name, {})
        if isinstance(result, dict) and result.get("success") and result.get("data"):
            if agent_name == "earnings":
                data = result.get("data", {})
                highlights = data.get("highlights", [])
                data_source = data.get("data_source", "")
                if len(highlights) > 0 and data_source != "none":
                    deterministic_completeness += weight
                else:
                    deterministic_completeness += 0.15
            else:
                deterministic_completeness += weight
    validated["data_completeness"] = round(deterministic_completeness, 2)

    return validated, warnings
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_agents/test_earnings_review_agent.py::TestEarningsReviewGuardrails -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/llm_guardrails.py tests/test_agents/test_earnings_review_agent.py
git commit -m "feat(earnings-review): add validate_earnings_review_output() guardrails"
```

---

### Task 4: Orchestrator Integration

**Files:**
- Modify: `src/orchestrator.py`
- Modify: `tests/test_orchestrator.py`

- [ ] **Step 1: Write orchestrator integration tests**

Append to `tests/test_orchestrator.py`:

```python
class TestEarningsReviewIntegration:
    """Tests for earnings review agent integration in synthesis phase."""

    def test_earnings_review_in_registry(self, test_config):
        """Earnings review agent is registered in AGENT_REGISTRY."""
        orch = Orchestrator(config=test_config)
        assert "earnings_review" in orch.AGENT_REGISTRY

    def test_earnings_review_not_in_default_agents(self, test_config):
        """Earnings review is NOT in DEFAULT_AGENTS."""
        orch = Orchestrator(config=test_config)
        assert "earnings_review" not in orch.DEFAULT_AGENTS

    @pytest.mark.asyncio
    async def test_earnings_review_runs_parallel_with_solution_and_thesis(self, test_config, tmp_path):
        """Earnings review runs in synthesis phase and result is attached."""
        db_path = str(tmp_path / "test.db")
        db_manager = DatabaseManager(db_path)
        orch = Orchestrator(config=test_config, db_manager=db_manager)

        mock_review_data = {
            "executive_summary": "Strong quarter.",
            "beat_miss": [{"metric": "EPS", "actual": 2.40, "estimate": 2.15, "surprise_pct": 11.63, "verdict": "beat"}],
            "guidance_deltas": [],
            "kpi_table": [],
            "management_tone": "confident",
            "notable_quotes": [],
            "thesis_impact": "",
            "one_offs": [],
            "sector_template": "Technology",
            "data_completeness": 0.8,
            "data_sources_used": ["earnings", "fundamentals"],
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
            MockThesis.return_value.execute = AsyncMock(return_value={
                "success": True, "data": {"thesis_summary": "Test thesis."},
            })
            MockReview.return_value.execute = AsyncMock(return_value={
                "success": True, "data": mock_review_data,
            })

            result = await orch.analyze_ticker("AAPL")

        assert result["success"] is True
        assert "earnings_review" in result["analysis"]
        assert result["analysis"]["earnings_review"]["executive_summary"] == "Strong quarter."

    @pytest.mark.asyncio
    async def test_earnings_review_failure_is_nonblocking(self, test_config, tmp_path):
        """If earnings review fails, analysis still completes."""
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
            MockThesis.return_value.execute = AsyncMock(return_value={
                "success": True, "data": {"thesis_summary": "Test thesis."},
            })
            MockReview.return_value.execute = AsyncMock(side_effect=Exception("LLM exploded"))

            result = await orch.analyze_ticker("AAPL")

        assert result["success"] is True
        assert result["analysis"].get("earnings_review") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_orchestrator.py::TestEarningsReviewIntegration -v`
Expected: FAIL — `cannot import name 'EarningsReviewAgent'`

- [ ] **Step 3: Add import and registry entry**

In `src/orchestrator.py`, add after the ThesisAgent import:

```python
from .agents.earnings_review_agent import EarningsReviewAgent
```

Add to `AGENT_REGISTRY`:

```python
"earnings_review": {"class": EarningsReviewAgent, "requires": []},
```

- [ ] **Step 4: Add _run_earnings_review_agent() method**

Add after `_run_thesis_agent()` in `src/orchestrator.py`:

```python
    async def _run_earnings_review_agent(
        self,
        ticker: str,
        agent_results: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Run earnings review agent for structured earnings digest (non-blocking).

        Args:
            ticker: Stock ticker
            agent_results: Results from all data agents

        Returns:
            Earnings review output dict, or None on failure
        """
        try:
            review_agent = EarningsReviewAgent(ticker, self.config, agent_results)
            self._inject_shared_resources(review_agent)
            timeout = self.config.get("AGENT_TIMEOUT", 30)
            result = await asyncio.wait_for(
                review_agent.execute(),
                timeout=timeout,
            )
            if result.get("success"):
                return result.get("data")
            else:
                self.logger.warning(f"Earnings review agent failed for {ticker}: {result.get('error')}")
                return None
        except asyncio.TimeoutError:
            self.logger.warning(f"Earnings review agent timed out for {ticker}")
            return None
        except Exception as e:
            self.logger.warning(f"Earnings review agent error for {ticker}: {e}")
            return None
```

- [ ] **Step 5: Expand asyncio.gather() to 3 agents**

In `analyze_ticker()`, replace:

```python
            final_analysis, thesis_result = await asyncio.gather(
                self._run_solution_agent(ticker, agent_results),
                self._run_thesis_agent(ticker, agent_results),
            )
            if thesis_result:
                final_analysis["thesis"] = thesis_result
```

With:

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

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_orchestrator.py -v`
Expected: All tests PASS (existing + 4 new)

- [ ] **Step 7: Commit**

```bash
git add src/orchestrator.py tests/test_orchestrator.py
git commit -m "feat(earnings-review): integrate EarningsReviewAgent into orchestrator synthesis phase"
```

---

### Task 5: LLM Mock Tests & End-to-End

**Files:**
- Modify: `tests/test_agents/test_earnings_review_agent.py`

- [ ] **Step 1: Write LLM mock tests and prompt tests**

Append to `tests/test_agents/test_earnings_review_agent.py`:

```python
import json as json_module
from unittest.mock import patch as mock_patch, AsyncMock as MockAsync


MOCK_LLM_RESPONSE = json_module.dumps({
    "executive_summary": "Apple delivered a strong Q1 with EPS beating estimates by 12%. Revenue guidance raised to $93-95B.",
    "guidance_deltas": [
        {"metric": "Revenue", "prior_value": "$90-92B", "new_value": "$93-95B", "direction": "raised"},
    ],
    "kpi_table": [
        {"metric": "Gross Margin", "value": "46%", "prior_value": "45%", "yoy_change": "+1pp", "source": "reported"},
        {"metric": "ARR", "value": "$5.2B", "prior_value": "$4.8B", "yoy_change": "+8.3%", "source": "call_disclosed"},
        {"metric": "R&D % of Revenue", "value": "7.2%", "prior_value": "6.8%", "yoy_change": "+0.4pp", "source": "calculated"},
    ],
    "management_tone": "confident",
    "notable_quotes": [
        "We see strong momentum in AI and expect it to be a meaningful revenue driver.",
        "Our services business continues to hit all-time highs.",
    ],
    "thesis_impact": "Confirms the bull case — growth is accelerating and guidance raise signals management confidence.",
    "one_offs": ["$200M restructuring charge related to workforce optimization"],
})


class TestEarningsReviewLLMFlow:
    """Tests for single-pass LLM flow with mocked responses."""

    @pytest.mark.asyncio
    async def test_full_flow_with_llm(self):
        agent = EarningsReviewAgent("AAPL", {"llm_config": {"provider": "none"}}, _make_agent_results())

        async def mock_call_llm(prompt):
            return MOCK_LLM_RESPONSE

        with mock_patch.object(agent, "_call_llm", side_effect=mock_call_llm):
            with mock_patch("src.llm_guardrails.validate_earnings_review_output", return_value=({
                **json_module.loads(MOCK_LLM_RESPONSE),
                "beat_miss": [{"metric": "EPS", "actual": 2.40, "estimate": 2.15, "surprise_pct": 11.63, "verdict": "beat"}],
                "sector_template": "Technology",
                "data_completeness": 1.0,
                "data_sources_used": ["earnings", "fundamentals", "market"],
            }, [])):
                result = await agent.analyze(agent.agent_results)

        assert result["executive_summary"] != ""
        assert len(result["beat_miss"]) >= 1
        assert result["beat_miss"][0]["verdict"] == "beat"
        assert len(result["kpi_table"]) >= 3
        assert result["management_tone"] == "confident"
        assert result["sector_template"] == "Technology"

    @pytest.mark.asyncio
    async def test_llm_failure_returns_partial(self):
        agent = EarningsReviewAgent("AAPL", {"llm_config": {"provider": "none"}}, _make_agent_results())

        async def mock_fail(prompt):
            raise Exception("LLM unavailable")

        with mock_patch.object(agent, "_call_llm", side_effect=mock_fail):
            result = await agent.analyze(agent.agent_results)

        # Should still have deterministic beat/miss
        assert result.get("partial") is True
        assert len(result["beat_miss"]) >= 1
        assert result["beat_miss"][0]["verdict"] == "beat"
        assert result["kpi_table"] == []

    @pytest.mark.asyncio
    async def test_no_transcript_returns_partial(self):
        results = _make_agent_results(has_transcript=False)
        agent = EarningsReviewAgent("AAPL", {"llm_config": {"provider": "none"}}, results)

        call_count = 0

        async def mock_call_llm(prompt):
            nonlocal call_count
            call_count += 1
            return "{}"

        with mock_patch.object(agent, "_call_llm", side_effect=mock_call_llm):
            result = await agent.analyze(results)

        assert call_count == 0  # LLM not called for partial
        assert result.get("partial") is True
        assert len(result["beat_miss"]) >= 1

    @pytest.mark.asyncio
    async def test_no_earnings_returns_empty(self):
        results = _make_agent_results(earnings=False)
        agent = EarningsReviewAgent("AAPL", {"llm_config": {"provider": "none"}}, results)

        result = await agent.analyze(results)

        assert "error" in result
        assert result["data_completeness"] == 0.0
        assert result["beat_miss"] == []


class TestEarningsReviewPrompt:
    """Tests for prompt construction."""

    def test_prompt_contains_ticker(self):
        agent = EarningsReviewAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        prompt = agent._build_prompt()
        assert "AAPL" in prompt

    def test_prompt_contains_sector_template(self):
        agent = EarningsReviewAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        prompt = agent._build_prompt()
        assert "ARR" in prompt  # Technology template includes ARR

    def test_prompt_contains_eps_history(self):
        agent = EarningsReviewAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        prompt = agent._build_prompt()
        assert "2.40" in prompt or "Q1'26" in prompt

    def test_prompt_contains_market_context(self):
        agent = EarningsReviewAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        prompt = agent._build_prompt()
        assert "195" in prompt or "220" in prompt  # price or 52w high
```

- [ ] **Step 2: Run all earnings review tests**

Run: `python -m pytest tests/test_agents/test_earnings_review_agent.py -v`
Expected: All tests PASS (7 models + 13 deterministic + 5 guardrails + 4 LLM + 4 prompt = 33)

- [ ] **Step 3: Commit**

```bash
git add tests/test_agents/test_earnings_review_agent.py
git commit -m "test(earnings-review): add LLM mock tests, prompt validation, and end-to-end flow tests"
```

---

### Task 6: Full Test Suite Verification

**Files:** None modified — verification only.

- [ ] **Step 1: Run the full test suite**

Run: `python -m pytest tests/ -v --tb=short`
Expected: All tests PASS, no regressions. (One pre-existing failure in `test_data_quality.py::TestTavilyCompanyContext::test_context_has_items` is known and unrelated.)

- [ ] **Step 2: Run earnings-review-specific tests with coverage**

Run: `python -m pytest tests/test_agents/test_earnings_review_agent.py --cov=src.agents.earnings_review_agent --cov=src.llm_guardrails --cov-report=term-missing -v`
Expected: Good coverage of earnings_review_agent.py and the new guardrails function.

- [ ] **Step 3: Commit any test fixes if needed**

Only if the full suite revealed issues.
