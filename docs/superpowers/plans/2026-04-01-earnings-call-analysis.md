# Earnings Call Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dedicated Earnings Call Analysis section with a new `EarningsAgent` that performs deep LLM-powered transcript analysis, rendered in a rich `EarningsPanel.jsx` component.

**Architecture:** New `EarningsAgent` inherits `BaseAgent`, fetches 4 quarters of transcripts via existing `data_provider.get_earnings_transcripts()`, runs a focused LLM prompt to extract highlights/guidance/Q&A/tone, and returns structured JSON. Frontend renders via a new `EarningsPanel.jsx` wired into the existing `SECTION_ORDER` → `AnalysisSection` pattern.

**Tech Stack:** Python/asyncio (backend agent), Anthropic/OpenAI SDK (LLM), React/Tailwind CSS v4/Framer Motion (frontend panel)

**Spec:** `docs/superpowers/specs/2026-04-01-earnings-call-analysis-design.md`

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `src/agents/earnings_agent.py` | Fetch transcripts + earnings history, LLM analysis, structured output |
| Create | `tests/test_earnings_agent.py` | Unit tests for earnings agent |
| Create | `frontend/src/components/EarningsPanel.jsx` | Rich earnings call visualization component |
| Modify | `src/orchestrator.py:38-49` | Register earnings agent in `AGENT_REGISTRY` and `DEFAULT_AGENTS` |
| Modify | `src/config.py:36-38` | Add `EARNINGS_AGENT_ENABLED` and `EARNINGS_TRANSCRIPT_QUARTERS` |
| Modify | `frontend/src/components/Dashboard.jsx:53-80,157-166,258-271` | Add earnings stance, section order entry, and render case |

---

### Task 1: Add Config Toggles

**Files:**
- Modify: `src/config.py:38` (after `OPTIONS_AGENT_ENABLED`)
- Modify: `tests/conftest.py:113` (add to `test_config`)

- [ ] **Step 1: Add config vars to `src/config.py`**

In `src/config.py`, add these two lines immediately after the `OPTIONS_AGENT_ENABLED` line (line 38):

```python
EARNINGS_AGENT_ENABLED = os.getenv("EARNINGS_AGENT_ENABLED", "true").lower() == "true"
EARNINGS_TRANSCRIPT_QUARTERS = int(os.getenv("EARNINGS_TRANSCRIPT_QUARTERS", "4"))
```

- [ ] **Step 2: Add to test config fixture in `tests/conftest.py`**

In `tests/conftest.py`, add inside the `test_config` dict (after the `OPTIONS_AGENT_ENABLED` line at ~line 113):

```python
"EARNINGS_AGENT_ENABLED": True,
"EARNINGS_TRANSCRIPT_QUARTERS": 4,
```

- [ ] **Step 3: Commit**

```bash
git add src/config.py tests/conftest.py
git commit -m "feat(config): add EARNINGS_AGENT_ENABLED and EARNINGS_TRANSCRIPT_QUARTERS toggles"
```

---

### Task 2: Create EarningsAgent — Skeleton + fetch_data

**Files:**
- Create: `src/agents/earnings_agent.py`
- Create: `tests/test_earnings_agent.py`

- [ ] **Step 1: Write the failing test for fetch_data**

Create `tests/test_earnings_agent.py`:

```python
"""Tests for the EarningsAgent."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.agents.earnings_agent import EarningsAgent


# ─── Fixtures ────────────────────────────────────────────────────────────────


SAMPLE_TRANSCRIPT = {
    "quarter": 1,
    "year": 2026,
    "date": "2026-01-30",
    "content": (
        "Good afternoon. Welcome to the Q1 2026 earnings call. "
        "Revenue came in at $124.3 billion, exceeding our guidance of $117 to $121 billion. "
        "EPS of $2.40 versus consensus of $2.35. Gross margin expanded 80 basis points year over year. "
        "We are raising our full-year revenue guidance to $125 billion to $130 billion. "
        "EPS guidance is now $2.42 to $2.50, up from $2.28 to $2.35. "
        "Capital expenditure expected at $13 billion, up from prior $11 billion. "
        "We announced a $110 billion share buyback authorization. "
        "China revenue declined 2% quarter over quarter. "
        "\n\nQuestion-and-Answer Session\n\n"
        "Erik Woodring, Morgan Stanley: How is Apple Intelligence adoption tracking? "
        "Tim Cook: We are seeing 60% plus adoption on supported devices with incredible engagement. "
        "Michael Ng, Goldman Sachs: Can you quantify the China competitive impact? "
        "Luca Maestri: Competitive dynamics exist but our installed base loyalty and Services attach rate are durable. "
        "Toni Sacconaghi, Bernstein: What drives margin expansion? "
        "Luca Maestri: Services mix shift and favorable component pricing. We guide similar or better margins next quarter."
    ),
    "symbol": "AAPL",
    "data_source": "fmp",
}

SAMPLE_EARNINGS_HISTORY = {
    "eps_history": [
        {"date": "2026-01-30", "reported_eps": 2.40, "estimated_eps": 2.35},
        {"date": "2025-10-31", "reported_eps": 2.18, "estimated_eps": 2.10},
        {"date": "2025-07-31", "reported_eps": 1.95, "estimated_eps": 2.00},
        {"date": "2025-04-30", "reported_eps": 1.82, "estimated_eps": 1.78},
    ],
    "latest_eps": {"reported_eps": 2.40, "estimated_eps": 2.35},
    "data_source": "fmp",
}


@pytest.fixture
def agent(test_config):
    agent = EarningsAgent("AAPL", test_config)
    agent._data_provider = AsyncMock()
    return agent


# ─── Tests ───────────────────────────────────────────────────────────────────


class TestEarningsAgentFetchData:

    @pytest.mark.asyncio
    async def test_fetch_data_returns_transcripts_and_earnings(self, agent):
        agent._data_provider.get_earnings_transcripts = AsyncMock(
            return_value=[SAMPLE_TRANSCRIPT]
        )
        agent._data_provider.get_earnings = AsyncMock(
            return_value=SAMPLE_EARNINGS_HISTORY
        )

        raw = await agent.fetch_data()

        assert "transcripts" in raw
        assert "earnings_history" in raw
        assert len(raw["transcripts"]) == 1
        assert raw["transcripts"][0]["quarter"] == 1
        agent._data_provider.get_earnings_transcripts.assert_awaited_once_with(
            "AAPL", num_quarters=4
        )

    @pytest.mark.asyncio
    async def test_fetch_data_empty_transcripts(self, agent):
        agent._data_provider.get_earnings_transcripts = AsyncMock(return_value=[])
        agent._data_provider.get_earnings = AsyncMock(return_value=SAMPLE_EARNINGS_HISTORY)

        raw = await agent.fetch_data()

        assert raw["transcripts"] == []

    def test_agent_type(self, agent):
        assert agent.get_agent_type() == "earnings"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_earnings_agent.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.agents.earnings_agent'`

- [ ] **Step 3: Write minimal EarningsAgent with fetch_data**

Create `src/agents/earnings_agent.py`:

```python
"""Earnings call analysis agent — deep transcript analysis via LLM."""

import asyncio
import json
import re
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

import anthropic
from openai import OpenAI

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class EarningsAgent(BaseAgent):
    """Agent for deep earnings call transcript analysis.

    Fetches up to 4 quarters of earnings transcripts and EPS history,
    then uses LLM to extract highlights, guidance, Q&A summaries,
    and management tone analysis.
    """

    async def fetch_data(self) -> Dict[str, Any]:
        """Fetch earnings transcripts and EPS history.

        Returns:
            Dict with 'transcripts' list and 'earnings_history' dict.
        """
        num_quarters = self.config.get("EARNINGS_TRANSCRIPT_QUARTERS", 4)
        dp = getattr(self, "_data_provider", None)
        if not dp:
            return {"transcripts": [], "earnings_history": {}}

        transcripts_task = dp.get_earnings_transcripts(self.ticker, num_quarters=num_quarters)
        earnings_task = dp.get_earnings(self.ticker)

        transcripts_result, earnings_result = await asyncio.gather(
            transcripts_task, earnings_task, return_exceptions=True
        )

        transcripts = transcripts_result if isinstance(transcripts_result, list) else []
        earnings_history = earnings_result if isinstance(earnings_result, dict) else {}

        self.logger.info(
            f"Fetched {len(transcripts)} transcripts and earnings history for {self.ticker}"
        )

        return {
            "transcripts": transcripts,
            "earnings_history": earnings_history,
        }

    async def analyze(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze earnings transcripts via LLM.

        Args:
            raw_data: Output from fetch_data().

        Returns:
            Structured earnings analysis dict.
        """
        # Placeholder — implemented in Task 3
        raise NotImplementedError("analyze() not yet implemented")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_earnings_agent.py -v`
Expected: 3 passed (the two fetch_data tests and test_agent_type)

- [ ] **Step 5: Commit**

```bash
git add src/agents/earnings_agent.py tests/test_earnings_agent.py
git commit -m "feat(earnings): add EarningsAgent skeleton with fetch_data"
```

---

### Task 3: EarningsAgent — analyze() with LLM

**Files:**
- Modify: `src/agents/earnings_agent.py` (replace `analyze()` placeholder)
- Modify: `tests/test_earnings_agent.py` (add analyze tests)

- [ ] **Step 1: Write the failing test for analyze**

Append to `tests/test_earnings_agent.py`:

```python
class TestEarningsAgentAnalyze:

    MOCK_LLM_RESPONSE = json.dumps({
        "highlights": [
            {"tag": "BEAT", "text": "Revenue of $124.3B exceeded consensus"},
            {"tag": "NEW", "text": "Announced $110B share buyback"},
            {"tag": "WATCH", "text": "China revenue declined 2% QoQ"},
        ],
        "guidance": [
            {"metric": "Revenue", "prior": "$117-121B", "current": "$125-130B", "direction": "raised"},
            {"metric": "EPS", "prior": "$2.28-2.35", "current": "$2.42-2.50", "direction": "raised"},
        ],
        "qa_highlights": [
            {
                "analyst": "Erik Woodring",
                "firm": "Morgan Stanley",
                "topic": "AI Strategy",
                "question": "How is Apple Intelligence adoption tracking?",
                "answer": "Management highlighted 60%+ adoption rate on supported devices.",
            },
        ],
        "tone_analysis": {
            "confidence": 85,
            "specificity": 62,
            "defensiveness": 20,
            "forward_looking": 78,
            "hedging": 45,
        },
        "tone": "confident",
        "guidance_direction": "raised",
        "stance": "bullish",
        "analysis": "Strong quarter with beats across revenue and EPS.",
    })

    @pytest.mark.asyncio
    async def test_analyze_returns_structured_output(self, agent):
        raw_data = {
            "transcripts": [SAMPLE_TRANSCRIPT],
            "earnings_history": SAMPLE_EARNINGS_HISTORY,
        }

        with patch.object(
            agent, "_call_llm", new_callable=AsyncMock,
            return_value=self.MOCK_LLM_RESPONSE,
        ):
            result = await agent.analyze(raw_data)

        assert result["tone"] == "confident"
        assert result["guidance_direction"] == "raised"
        assert result["stance"] == "bullish"
        assert len(result["highlights"]) == 3
        assert result["highlights"][0]["tag"] == "BEAT"
        assert len(result["guidance"]) == 2
        assert len(result["qa_highlights"]) == 1
        assert result["tone_analysis"]["confidence"] == 85
        assert "analysis" in result
        assert result["data_source"] == "fmp"

    @pytest.mark.asyncio
    async def test_analyze_builds_eps_history(self, agent):
        raw_data = {
            "transcripts": [SAMPLE_TRANSCRIPT],
            "earnings_history": SAMPLE_EARNINGS_HISTORY,
        }

        with patch.object(
            agent, "_call_llm", new_callable=AsyncMock,
            return_value=self.MOCK_LLM_RESPONSE,
        ):
            result = await agent.analyze(raw_data)

        assert "eps_history" in result
        assert len(result["eps_history"]) == 4
        assert result["eps_history"][0]["actual"] == 2.40
        assert result["eps_history"][0]["estimate"] == 2.35
        assert abs(result["eps_history"][0]["surprise_pct"] - 2.13) < 0.1

    @pytest.mark.asyncio
    async def test_analyze_empty_transcripts(self, agent):
        raw_data = {"transcripts": [], "earnings_history": {}}

        result = await agent.analyze(raw_data)

        assert result["stance"] == "neutral"
        assert "no earnings call transcripts" in result["analysis"].lower()

    @pytest.mark.asyncio
    async def test_analyze_llm_failure_fallback(self, agent):
        raw_data = {
            "transcripts": [SAMPLE_TRANSCRIPT],
            "earnings_history": SAMPLE_EARNINGS_HISTORY,
        }

        with patch.object(
            agent, "_call_llm", new_callable=AsyncMock,
            side_effect=Exception("LLM timeout"),
        ):
            result = await agent.analyze(raw_data)

        # Should return a fallback result, not raise
        assert result["stance"] == "neutral"
        assert "data_source" in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_earnings_agent.py::TestEarningsAgentAnalyze -v`
Expected: FAIL — `NotImplementedError` or `AttributeError: '_call_llm'`

- [ ] **Step 3: Implement analyze() and LLM helpers**

Replace the `analyze()` placeholder and add helpers in `src/agents/earnings_agent.py`. Replace everything from `async def analyze` onward with:

```python
    async def analyze(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze earnings transcripts via LLM.

        Args:
            raw_data: Output from fetch_data().

        Returns:
            Structured earnings analysis dict.
        """
        transcripts = raw_data.get("transcripts", [])
        earnings_history = raw_data.get("earnings_history", {})

        # Build EPS history from earnings data
        eps_history = self._build_eps_history(earnings_history)

        # Build available quarters list
        available_quarters = [
            {"quarter": t["quarter"], "year": t["year"], "date": t.get("date", "")}
            for t in transcripts
        ]

        if not transcripts:
            return self._empty_result(eps_history, available_quarters)

        latest = transcripts[0]
        call_metadata = {
            "quarter": latest.get("quarter"),
            "year": latest.get("year"),
            "date": latest.get("date", ""),
            "symbol": self.ticker,
        }

        # Build LLM prompt and call
        prompt = self._build_prompt(transcripts)

        try:
            llm_response = await self._call_llm(prompt)
            parsed = self._parse_llm_response(llm_response)
        except Exception as e:
            self.logger.warning(f"LLM analysis failed for {self.ticker}: {e}")
            return self._fallback_result(call_metadata, eps_history, available_quarters)

        return {
            "call_metadata": call_metadata,
            "tone": parsed.get("tone", "neutral"),
            "guidance_direction": parsed.get("guidance_direction", "maintained"),
            "highlights": parsed.get("highlights", []),
            "guidance": parsed.get("guidance", []),
            "qa_highlights": parsed.get("qa_highlights", []),
            "tone_analysis": parsed.get("tone_analysis", {
                "confidence": 50, "specificity": 50,
                "defensiveness": 50, "forward_looking": 50, "hedging": 50,
            }),
            "eps_history": eps_history,
            "available_quarters": available_quarters,
            "analysis": parsed.get("analysis", ""),
            "stance": parsed.get("stance", "neutral"),
            "data_source": latest.get("data_source", "fmp"),
        }

    # ─── EPS History Builder ─────────────────────────────────────────────────

    def _build_eps_history(self, earnings_history: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Build formatted EPS history from raw earnings data.

        Args:
            earnings_history: Raw earnings dict from data_provider.get_earnings().

        Returns:
            List of dicts with quarter label, actual, estimate, and surprise %.
        """
        eps_list = earnings_history.get("eps_history", [])
        result = []
        for entry in eps_list[:8]:
            actual = entry.get("reported_eps") or entry.get("actual_eps")
            estimate = entry.get("estimated_eps") or entry.get("consensus_eps")
            if actual is None or estimate is None:
                continue
            actual = float(actual)
            estimate = float(estimate)
            surprise_pct = ((actual - estimate) / abs(estimate) * 100) if estimate != 0 else 0.0

            # Build quarter label from date
            date_str = entry.get("date", "")
            label = self._date_to_quarter_label(date_str)

            result.append({
                "quarter": label,
                "actual": actual,
                "estimate": estimate,
                "surprise_pct": round(surprise_pct, 2),
            })
        return result

    @staticmethod
    def _date_to_quarter_label(date_str: str) -> str:
        """Convert date string to quarter label like 'Q1\\'26'."""
        if not date_str:
            return "?"
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return "?"
        q = (dt.month - 1) // 3 + 1
        return f"Q{q}'{dt.strftime('%y')}"

    # ─── LLM Prompt ──────────────────────────────────────────────────────────

    def _build_prompt(self, transcripts: List[Dict[str, Any]]) -> str:
        """Build the LLM prompt from transcript content.

        Args:
            transcripts: List of transcript dicts (most recent first).

        Returns:
            Prompt string for LLM.
        """
        latest = transcripts[0]
        q, y = latest.get("quarter", "?"), latest.get("year", "?")

        # Include prior quarter transcript content for guidance comparison
        prior_content = ""
        if len(transcripts) > 1:
            prior = transcripts[1]
            prior_content = (
                f"\n\n--- PRIOR QUARTER TRANSCRIPT (Q{prior.get('quarter')}/{prior.get('year')}) ---\n"
                f"{prior.get('content', '')[:8000]}"
            )

        return f"""Analyze this earnings call transcript for {self.ticker} (Q{q}/{y}).
Return a JSON object with EXACTLY these keys — no markdown, no explanation, just raw JSON:

{{
  "highlights": [
    {{"tag": "BEAT|MISS|NEW|WATCH", "text": "one-sentence highlight"}}
  ],
  "guidance": [
    {{"metric": "Revenue|EPS|Gross Margin|CapEx|...", "prior": "$X-YB", "current": "$X-YB", "direction": "raised|lowered|maintained|introduced|withdrawn"}}
  ],
  "qa_highlights": [
    {{"analyst": "Name", "firm": "Firm", "topic": "2-3 word tag", "question": "one sentence", "answer": "2-3 sentences"}}
  ],
  "tone_analysis": {{
    "confidence": 0-100,
    "specificity": 0-100,
    "defensiveness": 0-100,
    "forward_looking": 0-100,
    "hedging": 0-100
  }},
  "tone": "confident|cautious|defensive|evasive|optimistic",
  "guidance_direction": "raised|lowered|maintained|mixed",
  "stance": "bullish|bearish|neutral",
  "analysis": "2-3 paragraph investment-focused narrative"
}}

Rules:
- highlights: 4-6 items. Tag each: BEAT (exceeded expectations), MISS (missed), NEW (strategic announcement), WATCH (risk/concern).
- guidance: Compare current quarter guidance vs prior quarter. If prior quarter transcript is provided, use it for "prior" values. If no prior data, use "N/A" for prior.
- qa_highlights: Top 3-5 most material Q&A exchanges. Include analyst name and firm if mentioned.
- tone_analysis: Score each dimension 0-100 based on management language and behavior in Q&A.
- stance: Overall investment signal from the call.
- analysis: Write as an equity research analyst. Focus on what matters for the investment thesis.

--- CURRENT QUARTER TRANSCRIPT (Q{q}/{y}) ---
{latest.get('content', '')}
{prior_content}
"""

    # ─── LLM Call ─────────────────────────────────────────────────────────────

    async def _call_llm(self, prompt: str) -> str:
        """Call the configured LLM provider.

        Args:
            prompt: Full prompt string.

        Returns:
            Raw LLM response text.
        """
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
                temperature=0.3,
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
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}],
            )

        response = await asyncio.to_thread(_call)
        return response.choices[0].message.content.strip()

    # ─── Response Parsing ─────────────────────────────────────────────────────

    def _parse_llm_response(self, raw: str) -> Dict[str, Any]:
        """Parse LLM JSON response, stripping markdown fences if present.

        Args:
            raw: Raw LLM response string.

        Returns:
            Parsed dict.
        """
        text = raw.strip()
        # Strip markdown code fences
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*\n?", "", text)
            text = re.sub(r"\n?```\s*$", "", text)
        return json.loads(text)

    # ─── Fallback / Empty Results ─────────────────────────────────────────────

    def _empty_result(
        self,
        eps_history: List[Dict[str, Any]],
        available_quarters: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Return result when no transcripts are available."""
        return {
            "call_metadata": {"quarter": None, "year": None, "date": "", "symbol": self.ticker},
            "tone": "neutral",
            "guidance_direction": "maintained",
            "highlights": [],
            "guidance": [],
            "qa_highlights": [],
            "tone_analysis": {
                "confidence": 50, "specificity": 50,
                "defensiveness": 50, "forward_looking": 50, "hedging": 50,
            },
            "eps_history": eps_history,
            "available_quarters": available_quarters,
            "analysis": "No earnings call transcripts available for analysis.",
            "stance": "neutral",
            "data_source": "none",
        }

    def _fallback_result(
        self,
        call_metadata: Dict[str, Any],
        eps_history: List[Dict[str, Any]],
        available_quarters: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Return result when LLM call fails."""
        return {
            "call_metadata": call_metadata,
            "tone": "neutral",
            "guidance_direction": "maintained",
            "highlights": [],
            "guidance": [],
            "qa_highlights": [],
            "tone_analysis": {
                "confidence": 50, "specificity": 50,
                "defensiveness": 50, "forward_looking": 50, "hedging": 50,
            },
            "eps_history": eps_history,
            "available_quarters": available_quarters,
            "analysis": "Earnings call analysis unavailable — LLM processing failed.",
            "stance": "neutral",
            "data_source": call_metadata.get("symbol", "fmp"),
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_earnings_agent.py -v`
Expected: All 7 tests pass

- [ ] **Step 5: Commit**

```bash
git add src/agents/earnings_agent.py tests/test_earnings_agent.py
git commit -m "feat(earnings): implement analyze() with LLM prompt and structured output"
```

---

### Task 4: Register EarningsAgent in Orchestrator

**Files:**
- Modify: `src/orchestrator.py:19-49` (import + registry + defaults)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_earnings_agent.py`:

```python
class TestEarningsAgentRegistration:

    def test_earnings_in_agent_registry(self):
        from src.orchestrator import Orchestrator
        assert "earnings" in Orchestrator.AGENT_REGISTRY
        assert Orchestrator.AGENT_REGISTRY["earnings"]["requires"] == []

    def test_earnings_in_default_agents(self):
        from src.orchestrator import Orchestrator
        assert "earnings" in Orchestrator.DEFAULT_AGENTS

    def test_earnings_disabled_via_config(self):
        from src.orchestrator import Orchestrator
        orch = Orchestrator(config={
            "EARNINGS_AGENT_ENABLED": False,
            "MACRO_AGENT_ENABLED": True,
            "OPTIONS_AGENT_ENABLED": True,
            "DATABASE_PATH": ":memory:",
        })
        agents = orch._resolve_agents()
        assert "earnings" not in agents

    def test_earnings_enabled_via_config(self):
        from src.orchestrator import Orchestrator
        orch = Orchestrator(config={
            "EARNINGS_AGENT_ENABLED": True,
            "MACRO_AGENT_ENABLED": True,
            "OPTIONS_AGENT_ENABLED": True,
            "DATABASE_PATH": ":memory:",
        })
        agents = orch._resolve_agents()
        assert "earnings" in agents
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_earnings_agent.py::TestEarningsAgentRegistration -v`
Expected: FAIL — `"earnings" not in AGENT_REGISTRY`

- [ ] **Step 3: Register in orchestrator**

In `src/orchestrator.py`, add the import at line 20 (after the `OptionsAgent` import):

```python
from .agents.earnings_agent import EarningsAgent
```

Add to `AGENT_REGISTRY` dict (after the `"leadership"` entry, before `"sentiment"`):

```python
"earnings": {"class": EarningsAgent, "requires": []},
```

Add `"earnings"` to `DEFAULT_AGENTS` list (before `"sentiment"`):

```python
DEFAULT_AGENTS = ["news", "market", "fundamentals", "technical", "macro", "options", "leadership", "earnings", "sentiment"]
```

In `_resolve_agents()`, add the earnings disable check alongside macro/options (after line 158):

```python
if not self.config.get("EARNINGS_AGENT_ENABLED", True):
    agents = [a for a in agents if a != "earnings"]
```

In `_run_agents()`, add `"earnings"` to the `progress_map` dict (line 471):

```python
progress_map = {"news": 20, "fundamentals": 40, "market": 50, "macro": 55, "options": 57, "earnings": 58, "leadership": 59, "technical": 60}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_earnings_agent.py -v`
Expected: All 11 tests pass

- [ ] **Step 5: Commit**

```bash
git add src/orchestrator.py tests/test_earnings_agent.py
git commit -m "feat(earnings): register EarningsAgent in orchestrator"
```

---

### Task 5: Create EarningsPanel.jsx Frontend Component

**Files:**
- Create: `frontend/src/components/EarningsPanel.jsx`

- [ ] **Step 1: Create the component**

Create `frontend/src/components/EarningsPanel.jsx`:

```jsx
/**
 * EarningsPanel - Earnings call transcript analysis visualization
 * Shows highlights, guidance breakdown, Q&A summaries, EPS chart, and tone analysis
 */

import React from 'react';
import { motion as Motion } from 'framer-motion';

const fadeUp = {
  hidden: { opacity: 0, y: 12 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.22, 1, 0.36, 1] } },
};

// ─── Helpers ─────────────────────────────────────────────────────────────────

const getEarningsData = (analysis) =>
  analysis?.agent_results?.earnings?.data || null;

const TAG_COLORS = {
  BEAT: { text: 'text-success-400', bg: 'bg-success/10' },
  MISS: { text: 'text-danger-400', bg: 'bg-danger/10' },
  NEW: { text: 'text-accent-blue', bg: 'bg-accent-blue/10' },
  WATCH: { text: 'text-warning-400', bg: 'bg-warning/10' },
};

const DIRECTION_COLORS = {
  raised: 'text-success-400',
  lowered: 'text-danger-400',
  maintained: 'text-gray-400',
  introduced: 'text-accent-blue',
  withdrawn: 'text-danger-400',
};

const DIRECTION_ARROWS = {
  raised: '▲',
  lowered: '▼',
  maintained: '—',
  introduced: '●',
  withdrawn: '✕',
};

const TONE_COLORS = {
  confident: { text: 'text-success-400', bg: 'bg-success/10', border: 'border-success/25' },
  optimistic: { text: 'text-success-400', bg: 'bg-success/10', border: 'border-success/25' },
  cautious: { text: 'text-warning-400', bg: 'bg-warning/10', border: 'border-warning/25' },
  defensive: { text: 'text-danger-400', bg: 'bg-danger/10', border: 'border-danger/25' },
  evasive: { text: 'text-danger-400', bg: 'bg-danger/10', border: 'border-danger/25' },
  neutral: { text: 'text-gray-400', bg: 'bg-gray-400/10', border: 'border-gray-400/25' },
};

const GUIDANCE_DIR_STYLES = {
  raised: { text: 'text-success-400', bg: 'bg-success/10', border: 'border-success/25' },
  lowered: { text: 'text-danger-400', bg: 'bg-danger/10', border: 'border-danger/25' },
  maintained: { text: 'text-gray-400', bg: 'bg-gray-400/10', border: 'border-gray-400/25' },
  mixed: { text: 'text-warning-400', bg: 'bg-warning/10', border: 'border-warning/25' },
};

const TOPIC_COLORS = [
  'bg-accent-blue/10 text-accent-blue border-accent-blue/25',
  'bg-success/10 text-success-400 border-success/25',
  'bg-danger/10 text-danger-400 border-danger/25',
  'bg-warning/10 text-warning-400 border-warning/25',
  'bg-purple-500/10 text-purple-400 border-purple-500/25',
];

const getToneBarColor = (key, value) => {
  if (key === 'defensiveness' || key === 'hedging') {
    // Lower is better for these
    if (value <= 30) return 'bg-success-400';
    if (value <= 60) return 'bg-warning-400';
    return 'bg-danger-400';
  }
  // Higher is better
  if (value >= 70) return 'bg-success-400';
  if (value >= 40) return 'bg-accent-blue';
  return 'bg-warning-400';
};

const getToneLabel = (key, value) => {
  if (key === 'defensiveness' || key === 'hedging') {
    if (value <= 25) return 'Low';
    if (value <= 50) return 'Moderate';
    if (value <= 75) return 'High';
    return 'Very High';
  }
  if (value >= 75) return 'Strong';
  if (value >= 50) return 'Medium';
  if (value >= 25) return 'Low';
  return 'Weak';
};

const formatDate = (dateStr) => {
  if (!dateStr) return '';
  try {
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'long', day: 'numeric', year: 'numeric',
    });
  } catch {
    return dateStr;
  }
};

// ─── Sub-components ──────────────────────────────────────────────────────────

const HeaderRow = ({ data }) => {
  const meta = data.call_metadata || {};
  const tone = data.tone || 'neutral';
  const guidanceDir = data.guidance_direction || 'maintained';
  const toneStyle = TONE_COLORS[tone] || TONE_COLORS.neutral;
  const gdStyle = GUIDANCE_DIR_STYLES[guidanceDir] || GUIDANCE_DIR_STYLES.maintained;

  return (
    <div className="flex gap-3 mb-4">
      <div className="glass-card flex-1 px-4 py-3" style={{ borderLeft: '3px solid var(--accent-blue)' }}>
        <div className="text-[11px] uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Latest Call</div>
        <div className="text-base font-semibold mt-1" style={{ color: 'var(--text-primary)' }}>
          Q{meta.quarter} {meta.year} Earnings Call
        </div>
        <div className="text-xs mt-0.5" style={{ color: 'var(--text-secondary)' }}>{formatDate(meta.date)}</div>
      </div>
      <div className={`glass-card px-4 py-3 text-center min-w-[100px] ${toneStyle.bg} border ${toneStyle.border}`}>
        <div className="text-[11px] uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Tone</div>
        <div className={`text-lg font-bold mt-1 capitalize ${toneStyle.text}`}>{tone}</div>
      </div>
      <div className={`glass-card px-4 py-3 text-center min-w-[100px] ${gdStyle.bg} border ${gdStyle.border}`}>
        <div className="text-[11px] uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Guidance</div>
        <div className={`text-lg font-bold mt-1 capitalize ${gdStyle.text}`}>{guidanceDir}</div>
      </div>
    </div>
  );
};

const HighlightsCard = ({ highlights }) => {
  if (!highlights?.length) return null;
  return (
    <div className="glass-card p-4">
      <div className="text-sm font-semibold mb-3 flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
        <span style={{ color: 'var(--accent-blue)' }}>✦</span> Key Highlights
      </div>
      <div className="flex flex-col gap-2.5">
        {highlights.map((h, i) => {
          const tagStyle = TAG_COLORS[h.tag] || TAG_COLORS.WATCH;
          return (
            <div key={i} className="flex gap-2 items-start">
              <span className={`${tagStyle.bg} ${tagStyle.text} text-[10px] px-1.5 py-0.5 rounded font-medium whitespace-nowrap mt-0.5`}>
                {h.tag}
              </span>
              <span className="text-[13px] leading-relaxed" style={{ color: 'var(--text-secondary)' }}>{h.text}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
};

const GuidanceCard = ({ guidance }) => {
  if (!guidance?.length) return null;
  return (
    <div className="glass-card p-4">
      <div className="text-sm font-semibold mb-3 flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
        <span style={{ color: 'var(--accent-amber)' }}>⬥</span> Guidance Breakdown
      </div>
      <table className="w-full">
        <thead>
          <tr className="border-b border-white/[0.08]">
            <th className="text-left text-[11px] font-medium pb-1.5 pr-2" style={{ color: 'var(--text-muted)' }}>Metric</th>
            <th className="text-right text-[11px] font-medium pb-1.5 px-2" style={{ color: 'var(--text-muted)' }}>Prior</th>
            <th className="text-right text-[11px] font-medium pb-1.5 px-2" style={{ color: 'var(--text-muted)' }}>Current</th>
            <th className="text-right text-[11px] font-medium pb-1.5 pl-2" style={{ color: 'var(--text-muted)' }}>Change</th>
          </tr>
        </thead>
        <tbody>
          {guidance.map((g, i) => {
            const dirColor = DIRECTION_COLORS[g.direction] || 'text-gray-400';
            const arrow = DIRECTION_ARROWS[g.direction] || '—';
            return (
              <tr key={i} className={i < guidance.length - 1 ? 'border-b border-white/[0.04]' : ''}>
                <td className="text-[13px] py-2 pr-2" style={{ color: 'var(--text-secondary)' }}>{g.metric}</td>
                <td className="text-right text-[13px] py-2 px-2 font-mono" style={{ color: 'var(--text-muted)' }}>{g.prior}</td>
                <td className="text-right text-[13px] py-2 px-2 font-mono" style={{ color: 'var(--text-primary)' }}>{g.current}</td>
                <td className={`text-right text-[13px] py-2 pl-2 font-mono capitalize ${dirColor}`}>{arrow} {g.direction}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};

const QACard = ({ qaHighlights }) => {
  if (!qaHighlights?.length) return null;
  return (
    <div className="glass-card p-4">
      <div className="text-sm font-semibold mb-3 flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
        <span className="text-purple-400">◈</span> Q&A Session Highlights
      </div>
      <div className="flex flex-col gap-3">
        {qaHighlights.map((qa, i) => {
          const topicClass = TOPIC_COLORS[i % TOPIC_COLORS.length];
          return (
            <div key={i} className="border-l-2 border-purple-500/40 pl-3">
              <div className="flex justify-between items-center mb-1">
                <span className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
                  {qa.firm} — {qa.analyst}
                </span>
                <span className={`text-[10px] px-1.5 py-0.5 rounded border ${topicClass}`}>
                  {qa.topic}
                </span>
              </div>
              <div className="text-xs italic mb-1" style={{ color: 'var(--text-muted)' }}>
                Q: {qa.question}
              </div>
              <div className="text-[13px] leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                {qa.answer}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

const EPSChart = ({ epsHistory }) => {
  if (!epsHistory?.length) return null;
  const maxVal = Math.max(...epsHistory.map((e) => Math.max(e.actual, e.estimate)));

  return (
    <div className="glass-card p-4">
      <div className="text-sm font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>
        EPS: Actual vs. Estimate
      </div>
      <div className="flex flex-col gap-1.5">
        {epsHistory.map((e, i) => {
          const beat = e.actual >= e.estimate;
          const actualPct = maxVal > 0 ? (e.actual / maxVal) * 100 : 0;
          const estPct = maxVal > 0 ? (e.estimate / maxVal) * 100 : 0;
          return (
            <div key={i} className="flex items-center gap-2">
              <div className="text-[11px] w-[50px] font-mono" style={{ color: 'var(--text-muted)' }}>{e.quarter}</div>
              <div className="flex-1 flex gap-0.5 items-center">
                <div
                  className="h-5 rounded-sm flex items-center justify-end pr-1.5"
                  style={{
                    width: `${actualPct}%`,
                    background: beat
                      ? 'linear-gradient(90deg, rgba(23,201,100,0.3), rgba(23,201,100,0.5))'
                      : 'linear-gradient(90deg, rgba(243,18,96,0.3), rgba(243,18,96,0.5))',
                  }}
                >
                  <span className={`text-[11px] font-mono ${beat ? 'text-success-400' : 'text-danger-400'}`}>
                    ${e.actual.toFixed(2)}
                  </span>
                </div>
                <div
                  className="h-5 rounded-sm flex items-center justify-end pr-1.5"
                  style={{ width: `${estPct}%`, background: 'rgba(255,255,255,0.08)' }}
                >
                  <span className="text-[11px] font-mono" style={{ color: 'var(--text-muted)' }}>
                    ${e.estimate.toFixed(2)}
                  </span>
                </div>
              </div>
              <div className={`text-[11px] w-[45px] text-right font-mono ${beat ? 'text-success-400' : 'text-danger-400'}`}>
                {e.surprise_pct >= 0 ? '+' : ''}{e.surprise_pct.toFixed(1)}%
              </div>
            </div>
          );
        })}
      </div>
      <div className="flex gap-3 mt-2 pt-2 border-t border-white/[0.06]">
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded-sm" style={{ background: 'rgba(23,201,100,0.4)' }} />
          <span className="text-[10px]" style={{ color: 'var(--text-muted)' }}>Actual</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded-sm" style={{ background: 'rgba(255,255,255,0.1)' }} />
          <span className="text-[10px]" style={{ color: 'var(--text-muted)' }}>Estimate</span>
        </div>
      </div>
    </div>
  );
};

const ToneChart = ({ toneAnalysis }) => {
  if (!toneAnalysis) return null;
  const dimensions = [
    { key: 'confidence', label: 'Confidence' },
    { key: 'specificity', label: 'Specificity' },
    { key: 'defensiveness', label: 'Defensiveness' },
    { key: 'forward_looking', label: 'Forward-Looking' },
    { key: 'hedging', label: 'Hedging Language' },
  ];

  return (
    <div className="glass-card p-4">
      <div className="text-sm font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>
        Management Tone Analysis
      </div>
      <div className="flex flex-col gap-2">
        {dimensions.map(({ key, label }) => {
          const value = toneAnalysis[key] ?? 50;
          const barColor = getToneBarColor(key, value);
          const valueLabel = getToneLabel(key, value);
          return (
            <div key={key}>
              <div className="flex justify-between mb-1">
                <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>{label}</span>
                <span className={`text-xs font-mono ${barColor.replace('bg-', 'text-')}`}>{valueLabel}</span>
              </div>
              <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.06)' }}>
                <div
                  className={`h-full rounded-full ${barColor}`}
                  style={{ width: `${value}%`, opacity: 0.8 }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

const QuarterIndicator = ({ availableQuarters }) => {
  if (!availableQuarters?.length) return null;
  return (
    <div className="flex gap-2 justify-center mt-4">
      {availableQuarters.map((q, i) => (
        <div
          key={i}
          className={`text-xs px-3 py-1 rounded-md border ${
            i === 0
              ? 'bg-accent-blue/15 border-accent-blue/30 text-accent-blue'
              : 'bg-white/[0.04] border-white/[0.08]'
          }`}
          style={i !== 0 ? { color: 'var(--text-muted)' } : {}}
        >
          Q{q.quarter} {q.year}
        </div>
      ))}
    </div>
  );
};

// ─── Main Component ──────────────────────────────────────────────────────────

const EarningsPanel = ({ analysis }) => {
  const data = getEarningsData(analysis);

  if (!data) {
    return (
      <div className="text-sm py-4 text-center" style={{ color: 'var(--text-muted)' }}>
        Earnings call data unavailable
      </div>
    );
  }

  return (
    <Motion.div variants={fadeUp} initial="hidden" animate="visible" className="flex flex-col gap-4">
      <HeaderRow data={data} />

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <HighlightsCard highlights={data.highlights} />
        <GuidanceCard guidance={data.guidance} />
      </div>

      <QACard qaHighlights={data.qa_highlights} />

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <EPSChart epsHistory={data.eps_history} />
        <ToneChart toneAnalysis={data.tone_analysis} />
      </div>

      <QuarterIndicator availableQuarters={data.available_quarters} />
    </Motion.div>
  );
};

export default EarningsPanel;
```

- [ ] **Step 2: Verify the file was created and lint passes**

Run: `cd frontend && npx eslint src/components/EarningsPanel.jsx --no-error-on-unmatched-pattern 2>/dev/null; echo "done"`

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/EarningsPanel.jsx
git commit -m "feat(frontend): add EarningsPanel component for earnings call visualization"
```

---

### Task 6: Wire EarningsPanel into Dashboard

**Files:**
- Modify: `frontend/src/components/Dashboard.jsx`

- [ ] **Step 1: Add import**

In `frontend/src/components/Dashboard.jsx`, add import after the `OptionsFlow` import (line 21):

```jsx
import EarningsPanel from './EarningsPanel';
```

- [ ] **Step 2: Add earnings to SECTION_ORDER**

In the `SECTION_ORDER` array (line 157), add the earnings entry after `fundamentals`:

```jsx
const SECTION_ORDER = [
  { key: 'fundamentals', name: 'Fundamentals', special: false },
  { key: 'earnings', name: 'Earnings', special: 'earnings' },
  { key: 'technical', name: 'Technical', special: false },
  { key: 'sentiment', name: 'Sentiment', special: false },
  { key: 'macro', name: 'Macro', special: false },
  { key: 'news', name: 'News', special: 'news' },
  { key: 'options', name: 'Options', special: 'options' },
  { key: 'leadership', name: 'Leadership', special: 'leadership' },
  { key: 'council', name: 'Council', special: 'council' },
];
```

- [ ] **Step 3: Add stance logic in getAgentStance**

In the `getAgentStance` function (around line 53), add a case for earnings:

```jsx
case 'earnings': {
  const stance = d.stance || '';
  if (/bull/i.test(stance)) return 'bullish';
  if (/bear/i.test(stance)) return 'bearish';
  return 'neutral';
}
```

- [ ] **Step 4: Add render case in renderSpecialChildren**

In the `renderSpecialChildren` function (around line 258), add:

```jsx
case 'earnings':
  return <EarningsPanel analysis={analysis} />;
```

- [ ] **Step 5: Verify frontend builds**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no errors

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/Dashboard.jsx
git commit -m "feat(frontend): wire EarningsPanel into Dashboard section order"
```

---

### Task 7: Manual Smoke Test

**Files:** None (verification only)

- [ ] **Step 1: Run backend tests**

Run: `python -m pytest tests/test_earnings_agent.py -v`
Expected: All tests pass

- [ ] **Step 2: Start backend and verify agent appears**

Run: `source venv/bin/activate && python run.py`
Check logs for: `EarningsAgent` appearing in the agent list

- [ ] **Step 3: Start frontend and verify section renders**

Run: `cd frontend && npm run dev`
Navigate to `http://localhost:5173`, run an analysis for any ticker. Verify:
- "Earnings" section appears in the section nav after Fundamentals
- Section expands to show the EarningsPanel content (or "unavailable" if no FMP key)

- [ ] **Step 4: Run full test suite**

Run: `python -m pytest tests/ -v -x --timeout=60`
Expected: No regressions — all existing tests still pass
