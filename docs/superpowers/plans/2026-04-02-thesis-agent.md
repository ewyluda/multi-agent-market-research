# Thesis Agent (Bull/Bear Debate Engine) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a two-pass LLM synthesis agent that generates structured bull/bear investment debates, running in parallel with the solution agent.

**Architecture:** ThesisAgent inherits BaseAgent, takes agent_results in constructor (like SolutionAgent). Pass 1 extracts key facts from tiered agent data. Pass 2 generates structured bull/bear debate from extracted facts. Three-layer guardrails validate output. Runs in parallel with solution agent via asyncio.gather().

**Tech Stack:** Python, Pydantic, anthropic/openai SDKs, pytest

**Spec:** `docs/superpowers/specs/2026-04-02-thesis-agent-design.md`

---

### Task 1: Pydantic Models

**Files:**
- Modify: `src/models.py`
- Test: `tests/test_agents/test_thesis_agent.py` (create)

- [ ] **Step 1: Create test file with model validation tests**

Create `tests/test_agents/test_thesis_agent.py`:

```python
"""Tests for ThesisAgent — models, data gate, prompts, guardrails."""

import pytest
from src.models import TensionPoint, ManagementQuestion, ThesisCase, ThesisOutput


class TestThesisModels:
    """Pydantic model validation tests."""

    def test_tension_point_valid(self):
        tp = TensionPoint(
            topic="Revenue Sustainability",
            bull_view="Strong recurring revenue base with 95% retention.",
            bear_view="Growth is decelerating and new customer acquisition costs are rising.",
            evidence=["NRR at 95%", "CAC up 20% YoY"],
            resolution_catalyst="Next quarter's earnings will show if retention holds.",
        )
        assert tp.topic == "Revenue Sustainability"
        assert len(tp.evidence) == 2

    def test_management_question_valid(self):
        mq = ManagementQuestion(
            role="CEO",
            question="What is your strategy for international expansion?",
            context="Revenue from international markets has grown 40% but is still only 15% of total.",
        )
        assert mq.role == "CEO"

    def test_management_question_role_must_be_ceo_or_cfo(self):
        mq = ManagementQuestion(
            role="CTO",
            question="What about tech debt?",
            context="Context here.",
        )
        # Model accepts any string for role — no enum constraint
        assert mq.role == "CTO"

    def test_thesis_case_valid(self):
        tc = ThesisCase(
            thesis="Strong fundamentals and accelerating growth justify premium valuation.",
            key_drivers=["Revenue growth", "Margin expansion", "TAM expansion"],
            catalysts=["Q2 earnings beat", "New product launch in H2"],
        )
        assert len(tc.key_drivers) == 3

    def test_thesis_output_valid(self):
        output = ThesisOutput(
            bull_case=ThesisCase(
                thesis="Bull thesis.",
                key_drivers=["Driver 1"],
                catalysts=["Catalyst 1"],
            ),
            bear_case=ThesisCase(
                thesis="Bear thesis.",
                key_drivers=["Driver 1"],
                catalysts=["Catalyst 1"],
            ),
            tension_points=[
                TensionPoint(
                    topic="Growth",
                    bull_view="Growing fast.",
                    bear_view="Growth slowing.",
                    evidence=["Rev +20%"],
                    resolution_catalyst="Next earnings.",
                )
            ],
            management_questions=[
                ManagementQuestion(
                    role="CEO",
                    question="Strategy?",
                    context="Important because...",
                )
            ],
            thesis_summary="Summary paragraph.",
            data_completeness=0.85,
            data_sources_used=["fundamentals", "news", "earnings"],
        )
        assert output.data_completeness == 0.85
        assert len(output.tension_points) == 1

    def test_thesis_output_data_completeness_clamped(self):
        """data_completeness must be between 0.0 and 1.0."""
        with pytest.raises(Exception):
            ThesisOutput(
                bull_case=ThesisCase(thesis="x", key_drivers=[], catalysts=[]),
                bear_case=ThesisCase(thesis="x", key_drivers=[], catalysts=[]),
                tension_points=[],
                management_questions=[],
                thesis_summary="x",
                data_completeness=1.5,
                data_sources_used=[],
            )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_agents/test_thesis_agent.py -v`
Expected: FAIL — `ImportError: cannot import name 'TensionPoint' from 'src.models'`

- [ ] **Step 3: Add Pydantic models to src/models.py**

Add at the end of `src/models.py`:

```python
class TensionPoint(BaseModel):
    """A point of debate between bull and bear investment theses."""
    topic: str = Field(..., description="Debate topic, e.g. 'Revenue Sustainability'")
    bull_view: str = Field(..., description="Bull argument (2-3 sentences)")
    bear_view: str = Field(..., description="Bear counter-argument (2-3 sentences)")
    evidence: List[str] = Field(default=[], description="2-4 supporting data points")
    resolution_catalyst: str = Field(..., description="What would settle this debate")


class ManagementQuestion(BaseModel):
    """A question for company management derived from thesis tensions."""
    role: str = Field(..., description="Target executive role: CEO, CFO, etc.")
    question: str = Field(..., description="The question itself")
    context: str = Field(..., description="Why this question matters for the thesis")


class ThesisCase(BaseModel):
    """One side of the investment debate (bull or bear)."""
    thesis: str = Field(..., description="2-3 sentence core thesis")
    key_drivers: List[str] = Field(default=[], description="3-5 primary drivers")
    catalysts: List[str] = Field(default=[], description="Near-term catalysts")


class ThesisOutput(BaseModel):
    """Complete bull/bear investment thesis output."""
    bull_case: ThesisCase
    bear_case: ThesisCase
    tension_points: List[TensionPoint] = Field(default=[], description="3-8 debate points")
    management_questions: List[ManagementQuestion] = Field(default=[], description="5-7 questions")
    thesis_summary: str = Field(..., description="One-paragraph synthesis")
    data_completeness: float = Field(..., ge=0.0, le=1.0, description="0.0-1.0 data quality score")
    data_sources_used: List[str] = Field(default=[], description="Which agents contributed data")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_agents/test_thesis_agent.py::TestThesisModels -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/models.py tests/test_agents/test_thesis_agent.py
git commit -m "feat(thesis): add Pydantic models for ThesisOutput schema"
```

---

### Task 2: ThesisAgent Skeleton — Data Gate & Tiered Extraction

**Files:**
- Create: `src/agents/thesis_agent.py`
- Modify: `tests/test_agents/test_thesis_agent.py`

- [ ] **Step 1: Write data gate and extraction tests**

Append to `tests/test_agents/test_thesis_agent.py`:

```python
from src.agents.thesis_agent import ThesisAgent


def _make_agent_results(
    fundamentals=True, news=True, earnings=True, market=True,
    technical=True, macro=True, options=True, leadership=True,
):
    """Build mock agent_results dict with configurable agent success."""
    results = {}
    if fundamentals:
        results["fundamentals"] = {
            "success": True,
            "data": {
                "company_name": "Apple Inc.",
                "sector": "Technology",
                "market_cap": 3000000000000,
                "revenue": 383000000000,
                "revenue_growth": 0.08,
                "net_income": 97000000000,
                "gross_margin": 0.46,
                "pe_ratio": 32.5,
                "debt_to_equity": 1.73,
                "business_description": "Designs consumer electronics and software.",
                "analyst_estimates": {"target_mean": 210, "target_high": 250},
                "insider_trading": [{"owner_name": "Tim Cook", "transaction_type": "Sale", "shares": 50000}],
                "data_source": "fmp",
            },
        }
    if news:
        results["news"] = {
            "success": True,
            "data": {
                "articles": [
                    {"title": "Apple AI push accelerates", "summary": "New AI features announced.", "sentiment": 0.6},
                    {"title": "iPhone sales slow in China", "summary": "Market share declining.", "sentiment": -0.3},
                ],
                "news_sentiment": 0.15,
                "data_source": "tavily",
            },
        }
    if earnings:
        results["earnings"] = {
            "success": True,
            "data": {
                "highlights": [{"tag": "BEAT", "text": "EPS beat by 12%"}],
                "guidance": [{"metric": "Revenue", "prior": "$90-92B", "current": "$93-95B", "direction": "raised"}],
                "tone": "confident",
                "guidance_direction": "raised",
                "qa_highlights": [{"analyst": "John", "firm": "GS", "topic": "AI spend", "question": "Capex plans?", "answer": "Increasing investment."}],
                "eps_history": [{"quarter": "Q1'26", "actual": 2.40, "estimate": 2.15, "surprise_pct": 11.63}],
                "data_source": "fmp",
            },
        }
    if market:
        results["market"] = {
            "success": True,
            "data": {
                "current_price": 195.0,
                "high_52w": 220.0,
                "low_52w": 165.0,
                "avg_volume": 55000000,
                "price_change_1m": 0.05,
                "price_change_3m": -0.02,
                "data_source": "fmp",
            },
        }
    if technical:
        results["technical"] = {
            "success": True,
            "data": {
                "rsi": 58.0,
                "macd_signal": "bullish",
                "sma_50": 190.0,
                "sma_200": 185.0,
                "support": 188.0,
                "resistance": 205.0,
                "data_source": "fmp",
            },
        }
    if macro:
        results["macro"] = {
            "success": True,
            "data": {
                "fed_funds_rate": 4.5,
                "cpi_yoy": 2.8,
                "gdp_growth": 2.1,
                "unemployment_rate": 3.9,
                "yield_curve_spread": 0.15,
                "data_source": "fred",
            },
        }
    if options:
        results["options"] = {
            "success": True,
            "data": {
                "put_call_ratio": 0.85,
                "iv_percentile": 42.0,
                "unusual_activity": [],
                "data_source": "yfinance",
            },
        }
    if leadership:
        results["leadership"] = {
            "success": True,
            "data": {
                "overall_score": 82.0,
                "grade": "B+",
                "executive_summary": "Strong, stable leadership team with long tenures.",
                "red_flags": [],
                "data_source": "llm",
            },
        }
    # Mark missing agents as failed
    all_agents = {
        "fundamentals": fundamentals, "news": news, "earnings": earnings,
        "market": market, "technical": technical, "macro": macro,
        "options": options, "leadership": leadership,
    }
    for name, present in all_agents.items():
        if not present:
            results[name] = {"success": False, "data": None, "error": "Mock disabled"}
    return results


class TestThesisDataGate:
    """Tests for minimum data requirements."""

    def test_gate_passes_with_all_data(self):
        agent = ThesisAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        passes, sources = agent._check_data_gate()
        assert passes is True
        assert "fundamentals" in sources

    def test_gate_fails_without_fundamentals(self):
        agent = ThesisAgent("AAPL", {"llm_config": {}}, _make_agent_results(fundamentals=False))
        passes, sources = agent._check_data_gate()
        assert passes is False

    def test_gate_fails_without_any_secondary(self):
        results = _make_agent_results(news=False, earnings=False, market=False)
        agent = ThesisAgent("AAPL", {"llm_config": {}}, results)
        passes, sources = agent._check_data_gate()
        assert passes is False

    def test_gate_passes_with_fundamentals_and_news_only(self):
        results = _make_agent_results(earnings=False, market=False, technical=False, macro=False, options=False, leadership=False)
        agent = ThesisAgent("AAPL", {"llm_config": {}}, results)
        passes, sources = agent._check_data_gate()
        assert passes is True
        assert "news" in sources


class TestThesisDataCompleteness:
    """Tests for deterministic completeness score."""

    def test_full_data_completeness(self):
        agent = ThesisAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        score = agent._compute_data_completeness()
        assert score == pytest.approx(1.0, abs=0.01)

    def test_partial_data_completeness(self):
        results = _make_agent_results(technical=False, macro=False, options=False)
        agent = ThesisAgent("AAPL", {"llm_config": {}}, results)
        score = agent._compute_data_completeness()
        # Missing: technical(0.05) + macro(0.05) + options(0.05) = 0.15
        assert score == pytest.approx(0.85, abs=0.01)

    def test_minimal_data_completeness(self):
        results = _make_agent_results(
            earnings=False, market=False, technical=False,
            macro=False, options=False, leadership=False,
        )
        agent = ThesisAgent("AAPL", {"llm_config": {}}, results)
        score = agent._compute_data_completeness()
        # Only fundamentals(0.30) + news(0.15) = 0.45
        assert score == pytest.approx(0.45, abs=0.01)


class TestThesisTieredExtraction:
    """Tests for tiered data extraction from agent results."""

    def test_extract_rich_context_includes_fundamentals(self):
        agent = ThesisAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        rich, metrics = agent._extract_tiered_data()
        assert "Apple Inc." in rich
        assert "383" in rich  # revenue
        assert "Technology" in rich

    def test_extract_rich_context_includes_news(self):
        agent = ThesisAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        rich, metrics = agent._extract_tiered_data()
        assert "AI push" in rich or "Apple AI" in rich

    def test_extract_metrics_includes_rsi(self):
        agent = ThesisAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        rich, metrics = agent._extract_tiered_data()
        assert "RSI" in metrics or "58" in metrics

    def test_extract_handles_missing_agents(self):
        results = _make_agent_results(technical=False, macro=False, options=False, leadership=False)
        agent = ThesisAgent("AAPL", {"llm_config": {}}, results)
        rich, metrics = agent._extract_tiered_data()
        # Should not crash, just omit missing sections
        assert "Apple Inc." in rich
        assert "RSI" not in metrics
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_agents/test_thesis_agent.py::TestThesisDataGate -v`
Expected: FAIL — `ImportError: cannot import name 'ThesisAgent'`

- [ ] **Step 3: Implement ThesisAgent skeleton**

Create `src/agents/thesis_agent.py`:

```python
"""Thesis agent — two-pass LLM bull/bear investment debate engine."""

import asyncio
import json
import re
import logging
from typing import Dict, Any, List, Optional, Tuple

import anthropic
from openai import OpenAI

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)

# Weights for data completeness scoring (sum to 1.0)
_COMPLETENESS_WEIGHTS = {
    "fundamentals": 0.30,
    "news": 0.15,
    "earnings": 0.20,
    "leadership": 0.10,
    "market": 0.10,
    "technical": 0.05,
    "macro": 0.05,
    "options": 0.05,
}


class ThesisAgent(BaseAgent):
    """Agent that generates structured bull/bear investment debates.

    Two-pass LLM approach:
        Pass 1 ("The Analyst"): Extracts key investment facts from tiered agent data.
        Pass 2 ("The Debater"): Generates structured bull/bear thesis from extracted facts.

    Runs in the synthesis phase, parallel with SolutionAgent.
    """

    def __init__(self, ticker: str, config: Dict[str, Any], agent_results: Dict[str, Any]):
        super().__init__(ticker, config)
        self.agent_results = agent_results

    async def fetch_data(self) -> Dict[str, Any]:
        return self.agent_results

    async def analyze(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        # Check data gate
        gate_passes, sources = self._check_data_gate()
        if not gate_passes:
            self.logger.warning(f"Thesis data gate failed for {self.ticker} — insufficient data")
            return self._empty_result(sources)

        completeness = self._compute_data_completeness()
        rich_context, key_metrics = self._extract_tiered_data()

        # Pass 1: Extract facts
        try:
            pass1_prompt = self._build_pass1_prompt(rich_context, key_metrics)
            pass1_response = await self._call_llm(pass1_prompt)
            extracted_facts = self._parse_llm_response(pass1_response)
        except Exception as e:
            self.logger.warning(f"Thesis Pass 1 failed for {self.ticker}: {e}")
            return self._empty_result(sources)

        # Pass 2: Generate debate
        try:
            pass2_prompt = self._build_pass2_prompt(extracted_facts)
            pass2_response = await self._call_llm(pass2_prompt)
            thesis_raw = self._parse_llm_response(pass2_response)
        except Exception as e:
            self.logger.warning(f"Thesis Pass 2 failed for {self.ticker}: {e}, using Pass 1 fallback")
            return self._pass1_fallback(extracted_facts, completeness, sources)

        # Attach deterministic fields (override LLM values)
        thesis_raw["data_completeness"] = completeness
        thesis_raw["data_sources_used"] = sources

        # Guardrails (imported at call time to avoid circular imports)
        from ..llm_guardrails import validate_thesis_output
        validated, warnings = validate_thesis_output(thesis_raw, extracted_facts, self.agent_results)
        if warnings:
            validated["guardrail_warnings"] = warnings

        return validated

    # ─── Data Gate ───────────────────────────────────────────────────────────

    def _check_data_gate(self) -> Tuple[bool, List[str]]:
        """Check minimum data requirements. Returns (passes, sources_available)."""
        sources = []
        for agent_name in _COMPLETENESS_WEIGHTS:
            result = self.agent_results.get(agent_name, {})
            if isinstance(result, dict) and result.get("success") and result.get("data"):
                sources.append(agent_name)

        # Gate: fundamentals required + at least one of news/earnings/market
        has_fundamentals = "fundamentals" in sources
        has_secondary = any(s in sources for s in ("news", "earnings", "market"))

        return (has_fundamentals and has_secondary), sources

    def _compute_data_completeness(self) -> float:
        """Compute deterministic data completeness score (0.0-1.0)."""
        score = 0.0
        for agent_name, weight in _COMPLETENESS_WEIGHTS.items():
            result = self.agent_results.get(agent_name, {})
            if isinstance(result, dict) and result.get("success") and result.get("data"):
                score += weight
        return round(score, 2)

    # ─── Tiered Data Extraction ──────────────────────────────────────────────

    def _extract_tiered_data(self) -> Tuple[str, str]:
        """Extract tiered context from agent results.

        Returns:
            (rich_context, key_metrics) — both as formatted strings for the LLM prompt.
        """
        rich_parts = []
        metric_parts = []

        # Rich: Fundamentals
        fund_data = self._get_agent_data("fundamentals")
        if fund_data:
            rich_parts.append(self._format_fundamentals(fund_data))

        # Rich: News
        news_data = self._get_agent_data("news")
        if news_data:
            rich_parts.append(self._format_news(news_data))

        # Rich: Earnings
        earnings_data = self._get_agent_data("earnings")
        if earnings_data:
            rich_parts.append(self._format_earnings(earnings_data))

        # Rich: Leadership
        leadership_data = self._get_agent_data("leadership")
        if leadership_data:
            rich_parts.append(self._format_leadership(leadership_data))

        # Key metrics: Technical
        tech_data = self._get_agent_data("technical")
        if tech_data:
            metric_parts.append(self._format_technical_metrics(tech_data))

        # Key metrics: Macro
        macro_data = self._get_agent_data("macro")
        if macro_data:
            metric_parts.append(self._format_macro_metrics(macro_data))

        # Key metrics: Options
        options_data = self._get_agent_data("options")
        if options_data:
            metric_parts.append(self._format_options_metrics(options_data))

        # Key metrics: Market
        market_data = self._get_agent_data("market")
        if market_data:
            metric_parts.append(self._format_market_metrics(market_data))

        return "\n\n".join(rich_parts), "\n\n".join(metric_parts)

    def _get_agent_data(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """Safely extract data dict from an agent result."""
        result = self.agent_results.get(agent_name, {})
        if isinstance(result, dict) and result.get("success"):
            return result.get("data")
        return None

    @staticmethod
    def _format_fundamentals(data: Dict[str, Any]) -> str:
        name = data.get("company_name", "Unknown")
        sector = data.get("sector", "N/A")
        mcap = data.get("market_cap")
        mcap_str = f"${mcap / 1e9:.1f}B" if mcap else "N/A"
        revenue = data.get("revenue")
        rev_str = f"${revenue / 1e9:.1f}B" if revenue else "N/A"
        rev_growth = data.get("revenue_growth")
        rev_growth_str = f"{rev_growth * 100:.1f}%" if rev_growth is not None else "N/A"
        margin = data.get("gross_margin")
        margin_str = f"{margin * 100:.1f}%" if margin is not None else "N/A"
        pe = data.get("pe_ratio", "N/A")
        dte = data.get("debt_to_equity", "N/A")
        desc = data.get("business_description", "")
        estimates = data.get("analyst_estimates", {})
        target_mean = estimates.get("target_mean", "N/A")
        target_high = estimates.get("target_high", "N/A")
        insiders = data.get("insider_trading", [])
        insider_str = ""
        if insiders:
            lines = []
            for t in insiders[:3]:
                lines.append(f"  - {t.get('owner_name', '?')}: {t.get('transaction_type', '?')} {t.get('shares', '?')} shares")
            insider_str = "\nRecent Insider Trading:\n" + "\n".join(lines)

        return f"""FUNDAMENTALS — {name}
Sector: {sector} | Market Cap: {mcap_str}
Revenue: {rev_str} (Growth: {rev_growth_str}) | Gross Margin: {margin_str}
P/E: {pe} | Debt/Equity: {dte}
Analyst Targets: Mean ${target_mean}, High ${target_high}
Business: {desc}{insider_str}"""

    @staticmethod
    def _format_news(data: Dict[str, Any]) -> str:
        articles = data.get("articles", [])[:5]
        sentiment = data.get("news_sentiment", "N/A")
        lines = [f"NEWS (Overall Sentiment: {sentiment})"]
        for a in articles:
            lines.append(f"  - {a.get('title', 'Untitled')}: {a.get('summary', '')}")
        return "\n".join(lines)

    @staticmethod
    def _format_earnings(data: Dict[str, Any]) -> str:
        tone = data.get("tone", "N/A")
        direction = data.get("guidance_direction", "N/A")
        lines = [f"EARNINGS (Tone: {tone}, Guidance: {direction})"]
        for h in data.get("highlights", [])[:4]:
            lines.append(f"  [{h.get('tag', '?')}] {h.get('text', '')}")
        for g in data.get("guidance", [])[:3]:
            lines.append(f"  Guidance — {g.get('metric', '?')}: {g.get('prior', '?')} → {g.get('current', '?')} ({g.get('direction', '?')})")
        for qa in data.get("qa_highlights", [])[:2]:
            lines.append(f"  Q&A — {qa.get('analyst', '?')} ({qa.get('firm', '?')}): {qa.get('topic', '?')}")
        eps = data.get("eps_history", [])[:4]
        if eps:
            eps_strs = [f"{e['quarter']}: ${e['actual']} vs ${e['estimate']} ({e['surprise_pct']:+.1f}%)" for e in eps if 'quarter' in e]
            if eps_strs:
                lines.append(f"  EPS History: {' | '.join(eps_strs)}")
        return "\n".join(lines)

    @staticmethod
    def _format_leadership(data: Dict[str, Any]) -> str:
        score = data.get("overall_score", "N/A")
        grade = data.get("grade", "N/A")
        summary = data.get("executive_summary", "N/A")
        flags = data.get("red_flags", [])
        lines = [f"LEADERSHIP (Score: {score}, Grade: {grade})", f"  {summary}"]
        if flags:
            for f in flags[:3]:
                desc = f.get("description", str(f)) if isinstance(f, dict) else str(f)
                lines.append(f"  Red Flag: {desc}")
        return "\n".join(lines)

    @staticmethod
    def _format_technical_metrics(data: Dict[str, Any]) -> str:
        rsi = data.get("rsi", "N/A")
        macd = data.get("macd_signal", "N/A")
        sma50 = data.get("sma_50", "N/A")
        sma200 = data.get("sma_200", "N/A")
        support = data.get("support", "N/A")
        resistance = data.get("resistance", "N/A")
        return f"TECHNICAL: RSI {rsi} | MACD {macd} | 50-SMA ${sma50} | 200-SMA ${sma200} | Support ${support} | Resistance ${resistance}"

    @staticmethod
    def _format_macro_metrics(data: Dict[str, Any]) -> str:
        return (
            f"MACRO: Fed Funds {data.get('fed_funds_rate', 'N/A')}% | "
            f"CPI {data.get('cpi_yoy', 'N/A')}% | "
            f"GDP {data.get('gdp_growth', 'N/A')}% | "
            f"Unemployment {data.get('unemployment_rate', 'N/A')}% | "
            f"Yield Spread {data.get('yield_curve_spread', 'N/A')}"
        )

    @staticmethod
    def _format_options_metrics(data: Dict[str, Any]) -> str:
        pcr = data.get("put_call_ratio", "N/A")
        iv = data.get("iv_percentile", "N/A")
        unusual = data.get("unusual_activity", [])
        unusual_str = f" | Unusual: {len(unusual)} signals" if unusual else ""
        return f"OPTIONS: Put/Call {pcr} | IV Percentile {iv}%{unusual_str}"

    @staticmethod
    def _format_market_metrics(data: Dict[str, Any]) -> str:
        price = data.get("current_price", "N/A")
        high = data.get("high_52w", "N/A")
        low = data.get("low_52w", "N/A")
        vol = data.get("avg_volume")
        vol_str = f"{vol / 1e6:.1f}M" if vol else "N/A"
        chg1m = data.get("price_change_1m")
        chg1m_str = f"{chg1m * 100:+.1f}%" if chg1m is not None else "N/A"
        chg3m = data.get("price_change_3m")
        chg3m_str = f"{chg3m * 100:+.1f}%" if chg3m is not None else "N/A"
        return f"MARKET: Price ${price} | 52w High ${high} / Low ${low} | Vol {vol_str} | 1M {chg1m_str} | 3M {chg3m_str}"

    # ─── LLM Prompts ────────────────────────────────────────────────────────

    def _build_pass1_prompt(self, rich_context: str, key_metrics: str) -> str:
        """Build the Pass 1 fact extraction prompt."""
        return f"""You are a senior equity research analyst. Extract the key investment-relevant facts from this data for {self.ticker}.

IMPORTANT RULES:
- Only extract facts that appear in the provided data. Do NOT infer metrics not present.
- If a data point seems contradictory (e.g., revenue growth positive but guidance lowered), flag the contradiction explicitly rather than resolving it.
- Be specific — cite numbers, not vague claims.

Return a JSON object with EXACTLY these keys — no markdown, no explanation, just raw JSON:

{{
  "company_context": "2-3 sentence business summary with sector and scale",
  "key_financials": ["5-8 most important financial data points with numbers"],
  "recent_developments": ["3-5 material recent events or news items"],
  "management_signals": ["3-5 signals from earnings calls or leadership assessment"],
  "macro_technical_context": ["2-4 relevant macro or technical factors"],
  "potential_tensions": ["4-8 areas where reasonable investors could disagree — phrase each as a debatable question"]
}}

--- COMPANY DATA ---

{rich_context}

--- KEY METRICS ---

{key_metrics}
"""

    def _build_pass2_prompt(self, extracted_facts: Dict[str, Any]) -> str:
        """Build the Pass 2 debate generation prompt."""
        facts_json = json.dumps(extracted_facts, indent=2)
        return f"""You are a buy-side portfolio manager preparing a structured investment debate for {self.ticker}.

Given the extracted facts below, construct a bull/bear thesis. Rules:

1. Every evidence item MUST trace to a fact from the extraction. Do not introduce new data points.
2. If bull and bear views on a tension point don't actually conflict, discard that point — only include genuine disagreements.
3. Tension points should be specific to this company, not generic market concerns.
4. Management questions should reference specific tensions — not boilerplate.
5. Adapt the number of tension points and questions to how much is genuinely debatable (minimum 3 tension points, maximum 8).

Return a JSON object with EXACTLY these keys — no markdown, no explanation, just raw JSON:

{{
  "bull_case": {{
    "thesis": "2-3 sentence core bull thesis",
    "key_drivers": ["3-5 primary bull drivers"],
    "catalysts": ["2-4 near-term bull catalysts"]
  }},
  "bear_case": {{
    "thesis": "2-3 sentence core bear thesis",
    "key_drivers": ["3-5 primary bear drivers"],
    "catalysts": ["2-4 near-term bear catalysts"]
  }},
  "tension_points": [
    {{
      "topic": "Short descriptive label",
      "bull_view": "Bull argument with evidence (2-3 sentences)",
      "bear_view": "Bear counter-argument with evidence (2-3 sentences)",
      "evidence": ["2-4 data points from the extraction supporting this debate"],
      "resolution_catalyst": "Specific event or data point that would settle this"
    }}
  ],
  "management_questions": [
    {{
      "role": "CEO or CFO",
      "question": "The specific question",
      "context": "Why this matters for the investment thesis"
    }}
  ],
  "thesis_summary": "One paragraph synthesizing the overall investment debate — what is the core disagreement and what would resolve it?"
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
        else:
            return await self._call_openai(prompt, llm_config)

    async def _call_anthropic(self, prompt: str, llm_config: Dict[str, Any]) -> str:
        api_key = llm_config.get("api_key")
        if not api_key:
            raise ValueError("No Anthropic API key configured")
        client = anthropic.Anthropic(api_key=api_key)

        def _call():
            return client.messages.create(
                model=llm_config.get("model", "claude-3-5-sonnet-20241022"),
                max_tokens=llm_config.get("max_tokens", 4096),
                temperature=0.4,
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
                temperature=0.4,
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
        """Return empty result when data gate fails."""
        return {
            "bull_case": {"thesis": "", "key_drivers": [], "catalysts": []},
            "bear_case": {"thesis": "", "key_drivers": [], "catalysts": []},
            "tension_points": [],
            "management_questions": [],
            "thesis_summary": f"Insufficient data to generate investment thesis for {self.ticker}.",
            "data_completeness": 0.0,
            "data_sources_used": sources,
            "error": "Data gate failed — fundamentals required plus at least one of: news, earnings, market.",
        }

    def _pass1_fallback(
        self,
        extracted_facts: Dict[str, Any],
        completeness: float,
        sources: List[str],
    ) -> Dict[str, Any]:
        """Fallback when Pass 2 fails — surface extracted facts directly."""
        tensions = extracted_facts.get("potential_tensions", [])
        tension_points = [
            {
                "topic": t if isinstance(t, str) else str(t),
                "bull_view": "",
                "bear_view": "",
                "evidence": [],
                "resolution_catalyst": "",
            }
            for t in tensions[:8]
        ]
        return {
            "bull_case": {"thesis": "", "key_drivers": extracted_facts.get("key_financials", [])[:3], "catalysts": []},
            "bear_case": {"thesis": "", "key_drivers": [], "catalysts": []},
            "tension_points": tension_points,
            "management_questions": [],
            "thesis_summary": f"Partial analysis for {self.ticker} — fact extraction succeeded but debate generation failed.",
            "data_completeness": completeness,
            "data_sources_used": sources,
            "extracted_facts": extracted_facts,
            "pass2_failed": True,
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_agents/test_thesis_agent.py::TestThesisDataGate tests/test_agents/test_thesis_agent.py::TestThesisDataCompleteness tests/test_agents/test_thesis_agent.py::TestThesisTieredExtraction -v`
Expected: All 11 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/agents/thesis_agent.py tests/test_agents/test_thesis_agent.py
git commit -m "feat(thesis): add ThesisAgent skeleton with data gate, completeness scoring, and tiered extraction"
```

---

### Task 3: LLM Guardrails — validate_thesis_output()

**Files:**
- Modify: `src/llm_guardrails.py`
- Modify: `tests/test_agents/test_thesis_agent.py`

- [ ] **Step 1: Write guardrail tests**

Append to `tests/test_agents/test_thesis_agent.py`:

```python
from src.llm_guardrails import validate_thesis_output


def _make_extracted_facts():
    """Build mock Pass 1 extracted facts."""
    return {
        "company_context": "Apple is a $3T technology company.",
        "key_financials": [
            "Revenue $383B, growth 8%",
            "Gross margin 46%",
            "P/E 32.5",
            "Debt/Equity 1.73",
        ],
        "recent_developments": [
            "Apple AI push accelerates with new features",
            "iPhone sales slow in China",
        ],
        "management_signals": [
            "Confident tone on earnings call",
            "Guidance raised to $93-95B",
        ],
        "macro_technical_context": [
            "RSI 58 — neutral territory",
            "Fed funds at 4.5%",
        ],
        "potential_tensions": [
            "Revenue sustainability vs growth deceleration",
            "AI investment payoff timeline",
        ],
    }


def _make_valid_thesis():
    """Build a valid thesis output dict."""
    return {
        "bull_case": {
            "thesis": "Strong fundamentals and AI investment position Apple for growth.",
            "key_drivers": ["Revenue growth at 8%", "AI product expansion"],
            "catalysts": ["Q2 earnings", "WWDC product announcements"],
        },
        "bear_case": {
            "thesis": "Slowing China sales and high valuation limit upside.",
            "key_drivers": ["China market share loss", "P/E of 32.5 is stretched"],
            "catalysts": ["Next China sales report", "Fed rate decision"],
        },
        "tension_points": [
            {
                "topic": "Revenue Sustainability",
                "bull_view": "Revenue growth of 8% shows durable demand.",
                "bear_view": "Growth is decelerating and China sales are declining.",
                "evidence": ["Revenue $383B, growth 8%", "iPhone sales slow in China"],
                "resolution_catalyst": "Next quarter China revenue breakdown.",
            },
            {
                "topic": "AI Investment Payoff",
                "bull_view": "AI features will drive upgrade cycles and services revenue.",
                "bear_view": "AI spend has uncertain ROI and competes with entrenched players.",
                "evidence": ["Apple AI push accelerates with new features", "Guidance raised to $93-95B"],
                "resolution_catalyst": "WWDC developer adoption metrics.",
            },
        ],
        "management_questions": [
            {"role": "CEO", "question": "What is the AI monetization timeline?", "context": "AI investment is a key tension."},
            {"role": "CFO", "question": "How will China revenue trends impact margins?", "context": "China is the biggest bear concern."},
        ],
        "thesis_summary": "The core debate is whether AI investment can offset China headwinds.",
        "data_completeness": 0.85,
        "data_sources_used": ["fundamentals", "news", "earnings"],
    }


class TestThesisGuardrails:
    """Tests for validate_thesis_output() in llm_guardrails.py."""

    def test_valid_thesis_passes_cleanly(self):
        thesis = _make_valid_thesis()
        facts = _make_extracted_facts()
        validated, warnings = validate_thesis_output(thesis, facts, _make_agent_results())
        assert validated["bull_case"]["thesis"] != ""
        # May have minor warnings but should not error
        assert isinstance(warnings, list)

    def test_fabricated_evidence_flagged(self):
        thesis = _make_valid_thesis()
        thesis["tension_points"][0]["evidence"] = ["Revenue $500B growing 25%"]  # Not in facts
        facts = _make_extracted_facts()
        validated, warnings = validate_thesis_output(thesis, facts, _make_agent_results())
        assert any("evidence" in w.lower() or "ungrounded" in w.lower() for w in warnings)

    def test_generic_catalyst_flagged(self):
        thesis = _make_valid_thesis()
        thesis["tension_points"][0]["resolution_catalyst"] = "Time will tell."
        facts = _make_extracted_facts()
        validated, warnings = validate_thesis_output(thesis, facts, _make_agent_results())
        assert any("catalyst" in w.lower() or "generic" in w.lower() for w in warnings)

    def test_data_completeness_overridden_deterministically(self):
        thesis = _make_valid_thesis()
        thesis["data_completeness"] = 0.99  # LLM claimed 0.99 but real is 0.85
        facts = _make_extracted_facts()
        results = _make_agent_results()
        validated, warnings = validate_thesis_output(thesis, facts, results)
        # Should be overridden to the deterministic value
        assert validated["data_completeness"] != 0.99

    def test_contradiction_with_agent_data_flagged(self):
        thesis = _make_valid_thesis()
        # Bull claims negative revenue growth — contradicts fundamentals (8% growth)
        thesis["bull_case"]["thesis"] = "Revenue is declining rapidly."
        facts = _make_extracted_facts()
        results = _make_agent_results()
        validated, warnings = validate_thesis_output(thesis, facts, results)
        # Should flag the contradiction
        assert any("contradict" in w.lower() or "mismatch" in w.lower() or "revenue" in w.lower() for w in warnings)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_agents/test_thesis_agent.py::TestThesisGuardrails -v`
Expected: FAIL — `ImportError: cannot import name 'validate_thesis_output'`

- [ ] **Step 3: Implement validate_thesis_output()**

Add at the end of `src/llm_guardrails.py`:

```python
# ─── Thesis Output ─────────────────────────────────────────────────────────


_GENERIC_CATALYSTS = {
    "time will tell", "future earnings", "remains to be seen",
    "only time will tell", "we will see", "market will decide",
    "further developments", "more data needed",
}


def validate_thesis_output(
    thesis: Dict[str, Any],
    extracted_facts: Dict[str, Any],
    agent_results: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[str]]:
    """Validate thesis agent output against extracted facts and agent data.

    Three checks:
        1. Evidence grounding — flag evidence not traceable to extracted facts.
        2. Catalyst specificity — flag generic resolution catalysts.
        3. Cross-reference — flag claims that contradict agent data.

    Also overrides data_completeness with deterministic value.

    Returns:
        (validated_thesis, warnings)
    """
    warnings: List[str] = []
    validated = dict(thesis)

    # Build a searchable text corpus from extracted facts
    fact_corpus = _build_fact_corpus(extracted_facts)

    # 1. Evidence grounding check
    for i, tp in enumerate(validated.get("tension_points", [])):
        for evidence_item in tp.get("evidence", []):
            if not _evidence_is_grounded(evidence_item, fact_corpus):
                warnings.append(
                    f"Tension '{tp.get('topic', i)}': ungrounded evidence — "
                    f"'{evidence_item[:80]}' not found in extracted facts"
                )

    # 2. Catalyst specificity
    for i, tp in enumerate(validated.get("tension_points", [])):
        catalyst = (tp.get("resolution_catalyst") or "").strip().lower()
        catalyst_stripped = catalyst.rstrip(".")
        if catalyst_stripped in _GENERIC_CATALYSTS or len(catalyst) < 10:
            warnings.append(
                f"Tension '{tp.get('topic', i)}': generic catalyst — "
                f"'{tp.get('resolution_catalyst', '')}'"
            )

    # 3. Cross-reference against agent data
    _cross_reference_claims(validated, agent_results, warnings)

    # Override data_completeness deterministically
    completeness_weights = {
        "fundamentals": 0.30, "news": 0.15, "earnings": 0.20,
        "leadership": 0.10, "market": 0.10, "technical": 0.05,
        "macro": 0.05, "options": 0.05,
    }
    deterministic_completeness = 0.0
    for agent_name, weight in completeness_weights.items():
        result = agent_results.get(agent_name, {})
        if isinstance(result, dict) and result.get("success") and result.get("data"):
            deterministic_completeness += weight
    validated["data_completeness"] = round(deterministic_completeness, 2)

    return validated, warnings


def _build_fact_corpus(extracted_facts: Dict[str, Any]) -> str:
    """Flatten extracted facts into a single searchable string."""
    parts = []
    for key, value in extracted_facts.items():
        if isinstance(value, str):
            parts.append(value.lower())
        elif isinstance(value, list):
            for item in value:
                parts.append(str(item).lower())
    return " ".join(parts)


def _evidence_is_grounded(evidence: str, fact_corpus: str) -> bool:
    """Check if an evidence string can be traced to the fact corpus.

    Uses keyword overlap: extracts significant words (3+ chars) from the
    evidence and checks if at least 40% appear in the corpus.
    """
    words = re.findall(r"[a-z0-9]+", evidence.lower())
    significant = [w for w in words if len(w) >= 3]
    if not significant:
        return True  # Can't check empty evidence
    matches = sum(1 for w in significant if w in fact_corpus)
    return (matches / len(significant)) >= 0.40


def _cross_reference_claims(
    thesis: Dict[str, Any],
    agent_results: Dict[str, Any],
    warnings: List[str],
) -> None:
    """Check thesis claims against agent data for contradictions."""
    fund_result = agent_results.get("fundamentals", {})
    fund_data = fund_result.get("data") if isinstance(fund_result, dict) else None
    if not fund_data:
        return

    rev_growth = fund_data.get("revenue_growth")
    if rev_growth is not None:
        growth_positive = rev_growth > 0
        # Check bull and bear thesis text for contradictory claims
        bull_thesis = (thesis.get("bull_case") or {}).get("thesis", "").lower()
        bear_thesis = (thesis.get("bear_case") or {}).get("thesis", "").lower()

        decline_phrases = ["revenue is declining", "revenue declining", "falling revenue", "revenue shrink"]
        growth_phrases = ["revenue is growing rapidly", "accelerating revenue", "surging revenue"]

        if growth_positive:
            for phrase in decline_phrases:
                if phrase in bull_thesis or phrase in bear_thesis:
                    warnings.append(
                        f"Contradiction: thesis claims '{phrase}' but fundamentals show "
                        f"revenue growth of {rev_growth * 100:.1f}%"
                    )
        else:
            for phrase in growth_phrases:
                if phrase in bull_thesis or phrase in bear_thesis:
                    warnings.append(
                        f"Contradiction: thesis claims '{phrase}' but fundamentals show "
                        f"revenue decline of {rev_growth * 100:.1f}%"
                    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_agents/test_thesis_agent.py::TestThesisGuardrails -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/llm_guardrails.py tests/test_agents/test_thesis_agent.py
git commit -m "feat(thesis): add validate_thesis_output() guardrails — evidence grounding, catalyst specificity, cross-reference"
```

---

### Task 4: Orchestrator Integration

**Files:**
- Modify: `src/orchestrator.py`
- Modify: `tests/test_orchestrator.py`

- [ ] **Step 1: Write orchestrator integration tests**

Add to `tests/test_orchestrator.py` at the end:

```python
class TestThesisIntegration:
    """Tests for thesis agent integration in synthesis phase."""

    def test_thesis_in_registry(self, test_config):
        """Thesis agent is registered in AGENT_REGISTRY."""
        orch = Orchestrator(config=test_config)
        assert "thesis" in orch.AGENT_REGISTRY

    def test_thesis_not_in_default_agents(self, test_config):
        """Thesis agent is NOT in DEFAULT_AGENTS (wired in synthesis phase)."""
        orch = Orchestrator(config=test_config)
        assert "thesis" not in orch.DEFAULT_AGENTS

    @pytest.mark.asyncio
    async def test_thesis_runs_parallel_with_solution(self, test_config, tmp_path):
        """Thesis agent runs during synthesis phase and result is attached."""
        db_path = str(tmp_path / "test.db")
        db_manager = DatabaseManager(db_path)
        orch = Orchestrator(config=test_config, db_manager=db_manager)

        mock_thesis_data = {
            "bull_case": {"thesis": "Bull.", "key_drivers": [], "catalysts": []},
            "bear_case": {"thesis": "Bear.", "key_drivers": [], "catalysts": []},
            "tension_points": [],
            "management_questions": [],
            "thesis_summary": "Test thesis.",
            "data_completeness": 0.5,
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
                "success": True, "data": mock_thesis_data,
            })

            result = await orch.analyze_ticker("AAPL")

        assert result["success"] is True
        assert "thesis" in result["analysis"]
        assert result["analysis"]["thesis"]["thesis_summary"] == "Test thesis."

    @pytest.mark.asyncio
    async def test_thesis_failure_is_nonblocking(self, test_config, tmp_path):
        """If thesis agent fails, analysis still completes without thesis."""
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
            MockThesis.return_value.execute = AsyncMock(side_effect=Exception("LLM exploded"))

            result = await orch.analyze_ticker("AAPL")

        assert result["success"] is True
        assert result["analysis"].get("thesis") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_orchestrator.py::TestThesisIntegration -v`
Expected: FAIL — `ImportError: cannot import name 'ThesisAgent' from 'src.orchestrator'`

- [ ] **Step 3: Add ThesisAgent import and registry entry to orchestrator**

In `src/orchestrator.py`, add the import after the other agent imports (line ~20):

```python
from .agents.thesis_agent import ThesisAgent
```

Add to `AGENT_REGISTRY` dict (after "earnings" entry):

```python
"thesis": {"class": ThesisAgent, "requires": []},
```

- [ ] **Step 4: Add _run_thesis_agent() method**

Add after the `_run_solution_agent()` method in `src/orchestrator.py`:

```python
    async def _run_thesis_agent(
        self,
        ticker: str,
        agent_results: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Run thesis agent to generate bull/bear debate (non-blocking).

        Args:
            ticker: Stock ticker
            agent_results: Results from all data agents

        Returns:
            Thesis output dict, or None on failure
        """
        try:
            thesis_agent = ThesisAgent(ticker, self.config, agent_results)
            self._inject_shared_resources(thesis_agent)
            timeout = self.config.get("AGENT_TIMEOUT", 30)
            result = await asyncio.wait_for(
                thesis_agent.execute(),
                timeout=timeout,
            )
            if result.get("success"):
                return result.get("data")
            else:
                self.logger.warning(f"Thesis agent failed for {ticker}: {result.get('error')}")
                return None
        except asyncio.TimeoutError:
            self.logger.warning(f"Thesis agent timed out for {ticker}")
            return None
        except Exception as e:
            self.logger.warning(f"Thesis agent error for {ticker}: {e}")
            return None
```

- [ ] **Step 5: Modify synthesis phase to run thesis in parallel**

In `src/orchestrator.py`, in the `analyze_ticker()` method, replace the line:

```python
final_analysis = await self._run_solution_agent(ticker, agent_results)
```

With:

```python
final_analysis, thesis_result = await asyncio.gather(
    self._run_solution_agent(ticker, agent_results),
    self._run_thesis_agent(ticker, agent_results),
)
if thesis_result:
    final_analysis["thesis"] = thesis_result
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_orchestrator.py::TestThesisIntegration -v`
Expected: All 4 tests PASS

- [ ] **Step 7: Run existing orchestrator tests to check for regressions**

Run: `python -m pytest tests/test_orchestrator.py -v`
Expected: All existing tests PASS (thesis is not in DEFAULT_AGENTS, so existing mocks are unaffected)

- [ ] **Step 8: Commit**

```bash
git add src/orchestrator.py tests/test_orchestrator.py
git commit -m "feat(thesis): integrate ThesisAgent into orchestrator synthesis phase (parallel with solution)"
```

---

### Task 5: Full Agent Tests — LLM Mocking & End-to-End

**Files:**
- Modify: `tests/test_agents/test_thesis_agent.py`

- [ ] **Step 1: Write LLM pass tests with mocked responses**

Append to `tests/test_agents/test_thesis_agent.py`:

```python
import json
from unittest.mock import patch, AsyncMock


MOCK_PASS1_RESPONSE = json.dumps({
    "company_context": "Apple is a $3T technology company focused on consumer electronics and services.",
    "key_financials": [
        "Revenue $383B, growth 8%",
        "Gross margin 46%",
        "P/E 32.5",
        "Analyst target mean $210",
    ],
    "recent_developments": [
        "Apple AI push accelerates with new features",
        "iPhone sales slow in China",
    ],
    "management_signals": [
        "Confident tone on earnings call",
        "Guidance raised to $93-95B",
    ],
    "macro_technical_context": [
        "RSI 58 — neutral territory",
        "Fed funds at 4.5%",
    ],
    "potential_tensions": [
        "Revenue sustainability vs China slowdown",
        "AI investment payoff timeline",
        "Valuation premium justification",
    ],
})

MOCK_PASS2_RESPONSE = json.dumps({
    "bull_case": {
        "thesis": "Strong fundamentals and AI investment position Apple for continued growth.",
        "key_drivers": ["Revenue growth at 8%", "AI product expansion", "Services momentum"],
        "catalysts": ["Q2 earnings beat", "WWDC product announcements"],
    },
    "bear_case": {
        "thesis": "China headwinds and stretched valuation limit near-term upside.",
        "key_drivers": ["China market share loss", "P/E of 32.5 is above historical average"],
        "catalysts": ["Next China sales report", "Fed rate decision impact"],
    },
    "tension_points": [
        {
            "topic": "Revenue Sustainability",
            "bull_view": "8% revenue growth with raised guidance shows durable demand across product lines.",
            "bear_view": "Growth is masking China weakness; excluding China, growth picture changes.",
            "evidence": ["Revenue $383B, growth 8%", "iPhone sales slow in China", "Guidance raised to $93-95B"],
            "resolution_catalyst": "Q2 earnings China revenue segment breakdown.",
        },
        {
            "topic": "AI Investment Payoff",
            "bull_view": "Apple AI features will drive upgrade cycles and boost services revenue.",
            "bear_view": "AI spend competes with entrenched players and ROI is uncertain.",
            "evidence": ["Apple AI push accelerates with new features", "Confident tone on earnings call"],
            "resolution_catalyst": "WWDC developer adoption metrics and AI feature usage data.",
        },
        {
            "topic": "Valuation Premium",
            "bull_view": "Premium P/E justified by ecosystem lock-in and services growth.",
            "bear_view": "At 32.5x earnings, any miss gets punished severely.",
            "evidence": ["P/E 32.5", "Analyst target mean $210"],
            "resolution_catalyst": "Next earnings relative to consensus expectations.",
        },
    ],
    "management_questions": [
        {"role": "CEO", "question": "What is the AI feature monetization timeline?", "context": "AI investment is a core bull/bear tension."},
        {"role": "CFO", "question": "Can you break down China revenue trajectory?", "context": "China is the primary bear concern."},
        {"role": "CEO", "question": "How do you view competitive positioning in AI?", "context": "Late mover risk vs ecosystem advantage."},
    ],
    "thesis_summary": "The core debate centers on whether Apple's AI push and services growth can offset China headwinds and justify a premium valuation.",
})


class TestThesisLLMPasses:
    """Tests for two-pass LLM flow with mocked responses."""

    @pytest.mark.asyncio
    async def test_full_two_pass_flow(self):
        agent = ThesisAgent("AAPL", {"llm_config": {"provider": "none"}}, _make_agent_results())
        call_count = 0

        async def mock_call_llm(prompt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return MOCK_PASS1_RESPONSE
            return MOCK_PASS2_RESPONSE

        with patch.object(agent, "_call_llm", side_effect=mock_call_llm):
            with patch("src.llm_guardrails.validate_thesis_output", return_value=({
                **json.loads(MOCK_PASS2_RESPONSE),
                "data_completeness": 1.0,
                "data_sources_used": ["fundamentals", "news", "earnings", "market", "technical", "macro", "options", "leadership"],
            }, [])):
                result = await agent.analyze(agent.agent_results)

        assert call_count == 2
        assert result["bull_case"]["thesis"] != ""
        assert result["bear_case"]["thesis"] != ""
        assert len(result["tension_points"]) == 3
        assert len(result["management_questions"]) == 3
        assert result["data_completeness"] == 1.0

    @pytest.mark.asyncio
    async def test_pass1_failure_returns_empty(self):
        agent = ThesisAgent("AAPL", {"llm_config": {"provider": "none"}}, _make_agent_results())

        async def mock_fail(prompt):
            raise Exception("LLM unavailable")

        with patch.object(agent, "_call_llm", side_effect=mock_fail):
            result = await agent.analyze(agent.agent_results)

        assert result["data_completeness"] == 0.0
        assert "error" in result or "insufficient" in result.get("thesis_summary", "").lower()

    @pytest.mark.asyncio
    async def test_pass2_failure_returns_pass1_fallback(self):
        agent = ThesisAgent("AAPL", {"llm_config": {"provider": "none"}}, _make_agent_results())
        call_count = 0

        async def mock_call_llm(prompt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return MOCK_PASS1_RESPONSE
            raise Exception("Pass 2 failed")

        with patch.object(agent, "_call_llm", side_effect=mock_call_llm):
            result = await agent.analyze(agent.agent_results)

        assert result.get("pass2_failed") is True
        assert result["data_completeness"] > 0
        assert "extracted_facts" in result
        assert len(result["tension_points"]) > 0

    @pytest.mark.asyncio
    async def test_data_gate_failure_skips_llm(self):
        results = _make_agent_results(fundamentals=False)
        agent = ThesisAgent("AAPL", {"llm_config": {"provider": "none"}}, results)

        call_count = 0

        async def mock_call_llm(prompt):
            nonlocal call_count
            call_count += 1
            return "{}"

        with patch.object(agent, "_call_llm", side_effect=mock_call_llm):
            result = await agent.analyze(results)

        assert call_count == 0  # LLM never called
        assert result["data_completeness"] == 0.0


class TestThesisPromptBuilding:
    """Tests for prompt construction."""

    def test_pass1_prompt_contains_ticker(self):
        agent = ThesisAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        rich, metrics = agent._extract_tiered_data()
        prompt = agent._build_pass1_prompt(rich, metrics)
        assert "AAPL" in prompt
        assert "FUNDAMENTALS" in prompt
        assert "TECHNICAL" in prompt or "RSI" in prompt

    def test_pass2_prompt_contains_facts(self):
        agent = ThesisAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        facts = json.loads(MOCK_PASS1_RESPONSE)
        prompt = agent._build_pass2_prompt(facts)
        assert "AAPL" in prompt
        assert "Revenue $383B" in prompt
        assert "bull_case" in prompt  # JSON schema in prompt

    def test_pass1_prompt_includes_guardrail_instructions(self):
        agent = ThesisAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        rich, metrics = agent._extract_tiered_data()
        prompt = agent._build_pass1_prompt(rich, metrics)
        assert "Do NOT infer" in prompt
        assert "contradictory" in prompt.lower() or "contradiction" in prompt.lower()

    def test_pass2_prompt_includes_guardrail_instructions(self):
        agent = ThesisAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        facts = json.loads(MOCK_PASS1_RESPONSE)
        prompt = agent._build_pass2_prompt(facts)
        assert "trace to a fact" in prompt.lower() or "trace" in prompt.lower()
```

- [ ] **Step 2: Run all thesis agent tests**

Run: `python -m pytest tests/test_agents/test_thesis_agent.py -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_agents/test_thesis_agent.py
git commit -m "test(thesis): add LLM mock tests, prompt validation, and end-to-end flow tests"
```

---

### Task 6: Full Test Suite Verification

**Files:** None modified — verification only.

- [ ] **Step 1: Run the full test suite**

Run: `python -m pytest tests/ -v --tb=short`
Expected: All existing tests PASS, no regressions.

- [ ] **Step 2: Run thesis-specific tests with coverage**

Run: `python -m pytest tests/test_agents/test_thesis_agent.py --cov=src.agents.thesis_agent --cov=src.llm_guardrails --cov-report=term-missing -v`
Expected: Good coverage of thesis_agent.py (data gate, extraction, prompts, fallbacks) and the new guardrails function.

- [ ] **Step 3: Commit any test fixes if needed**

Only if the full suite revealed issues. Otherwise skip this step.
