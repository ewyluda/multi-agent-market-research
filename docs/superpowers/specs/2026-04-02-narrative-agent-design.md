# Narrative Agent — Multi-Year Financial Story

**Date:** 2026-04-02
**Status:** Approved
**Context:** CapRelay feature replication — third of 5 planned agents

---

## Overview

A two-pass LLM hybrid agent that weaves multi-year financial data and earnings transcripts into a coherent investment narrative. Unlike thesis/earnings_review (pure synthesis agents), the narrative agent also fetches its own historical data via `fetch_data()`. Produces chronological year sections with selective quarterly inflection highlights, thematic narrative chapters that span years, and an overarching company arc. Runs in the synthesis phase parallel with Solution, Thesis, and EarningsReview agents.

---

## Architecture Decisions

| # | Decision | Choice | Alternatives |
|---|----------|--------|-------------|
| 1 | Year span | Configurable via `NARRATIVE_YEARS`, default 3 | Fixed 3; fixed 5 |
| 2 | LLM strategy | Two-pass (extract per-year facts → weave narrative) | Single-pass; year-by-year + synthesize |
| 3 | Data sourcing | Hybrid — fetches own historical data + consumes agent_results | agent_results only; new data provider method |
| 4 | Time resolution | Annual sections + selective quarterly inflection highlights | Annual only; annual + quarterly latest; annual + all quarterly |
| 5 | Output structure | Year sections (chronological) + narrative chapters (thematic) + company_arc | Year sections + arc only; chapters replace arc |
| 6 | Data gate | No hard gate — always produce output, data_completeness for transparency | Require 2+ years; require 2+ years + transcript |

Full rationale in memory: `project_caprelay_narrative_agent_decisions.md`

**Key revisit levers:**
- If quarterly detail for latest year is always wanted, upgrade to annual + quarterly for most recent year (Decision 4 option B)
- If 3 years feels thin for certain companies, bump `NARRATIVE_YEARS` default to 5

---

## Output Schema

```python
class QuarterlyInflection(BaseModel):
    quarter: str              # e.g., "Q2'25"
    headline: str             # One-line summary of why this quarter mattered
    details: str              # 2-3 sentence explanation
    impact: str               # "positive" | "negative" | "pivotal"

class YearSection(BaseModel):
    year: int
    headline: str                           # One-line summary of the year
    revenue_trajectory: str                 # Revenue story for this year
    margin_story: str                       # Margin expansion/compression narrative
    strategic_moves: list[str]              # M&A, divestitures, pivots, reorgs
    management_commentary: str              # Key themes from earnings calls
    capital_allocation: str                 # Buybacks, dividends, capex, debt
    quarterly_inflections: list[QuarterlyInflection]  # 0-2 inflection quarters

class NarrativeChapter(BaseModel):
    title: str                # e.g., "The Services Transition"
    years_covered: str        # e.g., "2024-2026"
    narrative: str            # 3-5 sentence thematic narrative
    evidence: list[str]       # Supporting data points

class NarrativeOutput(BaseModel):
    company_arc: str                        # 3-5 sentence overarching story
    year_sections: list[YearSection]
    narrative_chapters: list[NarrativeChapter]  # 2-4 thematic threads
    key_inflection_points: list[str]        # Top 3-5 moments that changed trajectory
    current_chapter: str                    # Where the company is now in its story
    years_covered: int                      # How many years of data were available
    data_completeness: float                # 0.0-1.0
    data_sources_used: list[str]
```

---

## Two-Pass LLM Flow

### fetch_data() — Hybrid Data Sourcing

Unlike thesis/earnings_review agents, the narrative agent fetches its own historical data:

```python
async def fetch_data(self) -> Dict[str, Any]:
    financials = await self._data_provider.get_financials(self.ticker)
    num_quarters = self.config.get("NARRATIVE_YEARS", 3) * 4
    transcripts = await self._data_provider.get_earnings_transcripts(
        self.ticker, num_quarters=num_quarters
    )
    return {
        "financials": financials,
        "transcripts": transcripts,
        "agent_results": self.agent_results,
    }
```

### Pass 1 — Fact Extraction ("The Researcher")

**Role:** Senior equity research analyst extracting key events and financial inflections per year.

**Input:** Multi-year income statements + balance sheets + transcript excerpts + latest fundamentals context (~4-6K tokens)

**Output (JSON):**
```json
{
    "per_year": [
        {
            "year": 2024,
            "revenue": "$365B",
            "revenue_growth": "2%",
            "gross_margin": "44%",
            "operating_margin": "30%",
            "key_events": ["iPhone 15 cycle", "Vision Pro launch"],
            "management_themes": ["Services growth emphasis", "India expansion"],
            "capital_moves": ["$90B buyback authorization"],
            "inflection_quarters": [
                {"quarter": "Q3'24", "event": "First China revenue decline in 3 years"}
            ]
        }
    ],
    "cross_year_themes": ["Services transition", "China exposure", "AI investment ramp"]
}
```

**Prompt guardrails:**
- "Only extract facts from the provided data. Do not infer events not mentioned."
- "For inflection_quarters, only flag quarters where something materially changed — not routine quarters."

### Pass 2 — Narrative Synthesis ("The Storyteller")

**Role:** Senior analyst who has covered this company for years, writing the narrative that connects financial results and management commentary.

**Input:** Pass 1 output only (~1-2K tokens)

**Output:** Full `NarrativeOutput` schema.

**Prompt guardrails:**
- "Every claim must trace to the extracted facts. Do not introduce new data."
- "Narrative chapters must span multiple years — single-year themes belong in year sections, not chapters."
- "Quarterly inflections should only include genuinely significant quarters (0-2 per year, not every quarter)."

### Error Handling

- `fetch_data()` fails → return empty result (no historical data available)
- Pass 1 fails → return empty result
- Pass 2 fails → return Pass 1 facts as fallback (year data without narrative polish)

---

## Data Completeness

Scored by coverage depth — no hard gate:

```python
weights:
    financial_coverage: 0.60  # years_available / years_requested
    transcript_coverage: 0.30  # transcripts_available / (years * 4)
    fundamentals_context: 0.10  # latest fundamentals from agent_results
```

Earnings partial credit: if only 1 year of financials available for a 3-year request, financial_coverage = 1/3 = 0.33, contributing 0.33 * 0.60 = 0.20 to the score.

`years_covered` field in output tells consumers exactly how much history was used.

---

## Guardrails

New function `validate_narrative_output()` in `src/llm_guardrails.py`:

- **Year ordering:** Verify year_sections are in chronological order
- **Inflection plausibility:** Flag if any year has more than 3 quarterly inflections (likely over-flagging)
- **Chapter spanning:** Warn if a narrative chapter only covers 1 year (should be a year section theme instead)
- **Data completeness override:** Deterministic recalculation
- Returns `(validated_result, warnings)` per existing pattern

---

## Orchestrator Integration

Expand existing synthesis phase `asyncio.gather()` to 4 agents:

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

New method `_run_narrative_agent()` mirrors the others. Non-blocking failure.

Registration: `AGENT_REGISTRY` entry, NOT in `DEFAULT_AGENTS`.

---

## File Changes

| File | Change | Lines (est.) |
|------|--------|-------------|
| `src/agents/narrative_agent.py` | **New.** Two-pass LLM, hybrid data fetching, per-year extraction, thematic chapters, completeness. | ~300 |
| `src/models.py` | Add `QuarterlyInflection`, `YearSection`, `NarrativeChapter`, `NarrativeOutput` models. | ~40 |
| `src/orchestrator.py` | Import, registry entry, `_run_narrative_agent()`, expand `asyncio.gather()` to 4 agents. | ~35 |
| `src/llm_guardrails.py` | Add `validate_narrative_output()` — year ordering, inflection count, chapter spanning, completeness. | ~50 |
| `tests/test_agents/test_narrative_agent.py` | **New.** Models, data fetching mocks, year extraction, LLM mocking, guardrails, completeness. | ~200 |
| `tests/test_orchestrator.py` | Update synthesis phase tests for 4 parallel agents. | ~15 |

### Not in Scope
- Frontend changes
- Existing agent modifications
- README/CLAUDE.md updates (after implementation)
