# Thesis Agent — Bull/Bear Debate Engine

**Date:** 2026-04-02
**Status:** Approved
**Context:** CapRelay feature replication — first of 5 planned agents

---

## Overview

A two-pass LLM synthesis agent that generates structured bull/bear investment debates from existing agent outputs. Runs in parallel with the solution agent during the synthesis phase, adding zero latency to the pipeline. Produces tension points, management questions, and thesis cases — all purely qualitative with no conviction scoring.

---

## Architecture Decisions

| # | Decision | Choice | Alternatives |
|---|----------|--------|-------------|
| 1 | Pipeline placement | Parallel with solution agent (synthesis phase) | Normal agent with deps; post-processing after solution |
| 2 | Relationship to solution | Independent — standalone output | Feed into solution; hybrid post-hoc stitch |
| 3 | Data context level | Tiered — rich fundamentals/news/earnings, key metrics from technical/macro/options | Full context; curated subset only |
| 4 | Tension point count | Adaptive — LLM decides (3-8) | Fixed count; fixed with ranking |
| 5 | Conviction scoring | Purely qualitative — no scores | Bull/bear balance score; per-tension-point lean |
| 6 | Sparse data handling | Minimum data gate + data completeness score | Graceful degradation only; hard gate only |
| 7 | LLM strategy | Two-pass (extract then debate) | Single-pass; multi-prompt with merge |
| 8 | Earnings data depth | Use EarningsAgent's distilled output | Raw transcript excerpts; distilled + key Q&A; hybrid |
| 9 | Guardrails | Three layers: prompt + post-processing + cross-reference | Prompt-only; post-processing only |

Full rationale for each decision stored in memory: `project_caprelay_thesis_agent_decisions.md`

**Key revisit lever:** If thesis quality feels shallow on management intent or guidance nuance, upgrade earnings data depth (Decision 8) first — add raw Q&A exchanges to Pass 1 input.

---

## Output Schema

```python
class TensionPoint(BaseModel):
    topic: str                    # e.g., "Revenue Sustainability"
    bull_view: str                # Bull argument (2-3 sentences)
    bear_view: str                # Bear counter-argument (2-3 sentences)
    evidence: list[str]           # 2-4 supporting data points from agent data
    resolution_catalyst: str      # What event/data would settle the debate

class ManagementQuestion(BaseModel):
    role: str                     # "CEO" | "CFO"
    question: str                 # The question itself
    context: str                  # Why this question matters for the thesis

class ThesisCase(BaseModel):
    thesis: str                   # 2-3 sentence core thesis
    key_drivers: list[str]        # 3-5 primary drivers
    catalysts: list[str]          # Near-term catalysts

class ThesisOutput(BaseModel):
    bull_case: ThesisCase
    bear_case: ThesisCase
    tension_points: list[TensionPoint]     # Adaptive count (3-8)
    management_questions: list[ManagementQuestion]  # Adaptive count (5-7)
    thesis_summary: str                    # One-paragraph synthesis
    data_completeness: float               # 0.0-1.0
    data_sources_used: list[str]           # Which agents contributed
```

---

## Two-Pass LLM Flow

### Pass 1 — Fact Extraction ("The Analyst")

**Role:** Senior equity research analyst extracting investment-relevant facts.

**Input:** Tiered agent data (~3-5K tokens):

| Tier | Agents | Data Included |
|------|--------|---------------|
| Rich | Fundamentals | company_name, sector, market_cap, revenue, revenue_growth, earnings, margins, PE, debt_to_equity, business_description, analyst_estimates, insider_trading summary |
| Rich | News | Top 5 articles (title + summary), overall news_sentiment |
| Rich | Earnings | highlights, guidance, tone, guidance_direction, management quotes, EPS history |
| Rich | Leadership | overall_score, grade, executive_summary, red_flags |
| Key metrics | Technical | RSI, MACD signal, current price vs 50/200 SMA, support/resistance |
| Key metrics | Macro | fed_funds_rate, CPI_yoy, GDP_growth, unemployment_rate, yield_curve_spread |
| Key metrics | Options | put_call_ratio, IV_percentile, unusual_activity_summary |
| Key metrics | Market | current_price, 52w_high, 52w_low, avg_volume, price_change_1m/3m |

**Output (JSON):**
```json
{
    "company_context": "2-3 sentence business summary",
    "key_financials": ["5-8 most important financial data points"],
    "recent_developments": ["3-5 material recent events/news"],
    "management_signals": ["3-5 signals from earnings/leadership"],
    "macro_technical_context": ["2-4 relevant macro/technical factors"],
    "potential_tensions": ["4-8 areas where reasonable people could disagree"]
}
```

**Prompt guardrails (Layer 1):**
- "Only extract facts that appear in the provided data. Do NOT infer metrics not present."
- "If a data point seems contradictory (e.g., revenue growth positive but guidance lowered), flag the contradiction explicitly rather than resolving it."

### Pass 2 — Debate Generation ("The Debater")

**Role:** Buy-side portfolio manager constructing a structured investment debate.

**Input:** Pass 1 output only (~800-1200 tokens). Raw agent data is NOT passed.

**Output:** Full `ThesisOutput` schema.

**Prompt guardrails (Layer 1):**
- "Every evidence item must trace to a fact from the extraction. Do not introduce new data points."
- "If bull and bear views on a tension point don't actually conflict, discard that tension point."

### Error Handling

- Pass 1 fails → return fallback result (empty thesis with error note)
- Pass 1 succeeds, Pass 2 fails → attempt single-pass fallback using Pass 1 output directly (degrade gracefully, preserve extracted facts)
- Both succeed → run through guardrails (Layers 2 & 3)

---

## Guardrails (Three Layers)

All follow existing `(validated_result, warnings)` pattern from `llm_guardrails.py`.

### Layer 1: Prompt Instructions
Embedded in both LLM prompts (see above).

### Layer 2: Deterministic Post-Processing
New function `validate_thesis_output()` in `src/llm_guardrails.py`:

- **Evidence grounding:** Every `evidence` string in tension points gets fuzzy-matched against Pass 1's extracted facts. Flag any that appear fabricated.
- **Tension validity:** For each tension point, verify bull_view and bear_view aren't rephrasing the same position. Simple check: if both contain the same directional language, flag it.
- **Catalyst specificity:** Reject resolution_catalysts that are generic ("time will tell", "future earnings"). Require reference to a concrete event or metric.
- **Data completeness accuracy:** Verify claimed `data_completeness` against which agents actually had data (deterministic calculation, overrides LLM-assessed value).

### Layer 3: Cross-Reference Against Agent Data
- If fundamentals reports negative revenue growth but bull case claims "accelerating revenue", flag the contradiction.
- If bear case cites a risk the news agent didn't surface, mark as "LLM-inferred" rather than "data-supported".
- Extract 3-5 checkable numeric claims from thesis, compare against agent data, attach `warnings` list.

---

## Data Gate

Minimum requirements to produce a thesis:
1. **Required:** Fundamentals agent succeeded with data
2. **Required:** At least one of: news, earnings, or market agent succeeded
3. If gate fails → return fallback result with `data_completeness: 0.0`

Completeness score calculation (deterministic):
```
score = sum(weights[agent] for agent in agents_with_data) / sum(weights.values())

weights = {
    "fundamentals": 0.30,
    "news": 0.15,
    "earnings": 0.20,
    "leadership": 0.10,
    "market": 0.10,
    "technical": 0.05,
    "macro": 0.05,
    "options": 0.05,
}
```

---

## Orchestrator Integration

### Synthesis Phase Change

```python
# In analyze_ticker(), replace:
final_analysis = await self._run_solution_agent(ticker, agent_results)

# With:
final_analysis, thesis_result = await asyncio.gather(
    self._run_solution_agent(ticker, agent_results),
    self._run_thesis_agent(ticker, agent_results),
)
if thesis_result:
    final_analysis["thesis"] = thesis_result
```

### New Method: `_run_thesis_agent()`

Mirrors `_run_solution_agent()`:
- Creates `ThesisAgent(ticker, config, agent_results)`
- Injects shared resources
- Wraps in `asyncio.wait_for(timeout=timeout)`
- Returns `result.get("data", {})` on success, `None` on failure
- Failure is **non-blocking** — analysis completes without thesis

### Registration

Added to `AGENT_REGISTRY` for discoverability:
```python
"thesis": {"class": ThesisAgent, "requires": []},
```
NOT added to `DEFAULT_AGENTS` — wired explicitly in synthesis phase.

### SSE Progress

Emits `"generating_thesis"` event at the same time as `"synthesizing"` (both at 80%).

---

## File Changes

| File | Change | Lines (est.) |
|------|--------|-------------|
| `src/agents/thesis_agent.py` | **New.** Two-pass LLM, tiered data extraction, prompt construction, JSON parsing, fallback results. | ~300 |
| `src/models.py` | Add `TensionPoint`, `ManagementQuestion`, `ThesisCase`, `ThesisOutput` Pydantic models. | ~35 |
| `src/orchestrator.py` | Import ThesisAgent. Add `_run_thesis_agent()`. Modify synthesis phase to `asyncio.gather()`. Attach thesis to final analysis. | ~40 |
| `src/llm_guardrails.py` | Add `validate_thesis_output()` with evidence grounding, tension validity, catalyst specificity, completeness, cross-reference checks. | ~80 |
| `tests/test_agents/test_thesis_agent.py` | **New.** Data gate, prompt building, both LLM passes, fallback paths, guardrail validation. | ~150 |
| `tests/test_orchestrator.py` | Update registry count assertions (10 registry entries, 9 default agents unchanged). Add test for thesis running parallel with solution. | ~15 |

### Not in Scope
- Frontend (Thesis tab — separate task)
- Database schema changes (thesis stores in existing `agent_results` as JSON)
- CLAUDE.md / README.md updates (after implementation)
