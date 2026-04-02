# Earnings Review Agent — Structured Earnings Digest

**Date:** 2026-04-02
**Status:** Approved
**Context:** CapRelay feature replication — second of 5 planned agents

---

## Overview

A single-pass LLM synthesis agent that produces structured earnings call digests with deterministic beat/miss computation, sector-specific KPI extraction, guidance delta tracking, and thesis impact assessment. Runs in the synthesis phase parallel with Solution and Thesis agents. Consumes EarningsAgent output + fundamentals + market data.

---

## Architecture Decisions

| # | Decision | Choice | Alternatives |
|---|----------|--------|-------------|
| 1 | Relationship to EarningsAgent | Separate synthesis agent | Extend existing; replace existing |
| 2 | Sector KPI extraction | Hybrid — hardcoded templates + LLM extras | Templates only; fully LLM-inferred |
| 3 | LLM strategy | Single-pass | Two-pass |
| 4 | Data context | Earnings + Fundamentals + Market | Earnings+Fund only; add News |
| 5 | Beat/miss structure | EPS + Revenue + Guidance delta | EPS+Rev only; full multi-metric |
| 6 | Beat/miss computation | Deterministic for EPS/rev, LLM for guidance | All LLM; all deterministic |
| 7 | Missing data handling | Return partial with deterministic fields | Hard gate (return empty) |

Full rationale in memory: `project_caprelay_earnings_review_decisions.md`

---

## Output Schema

```python
class BeatMiss(BaseModel):
    metric: str               # "EPS" | "Revenue"
    actual: Optional[float]
    estimate: Optional[float]
    surprise_pct: Optional[float]
    verdict: str              # "beat" | "miss" | "inline"

class GuidanceDelta(BaseModel):
    metric: str               # "Revenue" | "EPS" | "Gross Margin" | etc.
    prior_value: Optional[str]
    new_value: Optional[str]
    direction: str            # "raised" | "lowered" | "maintained" | "introduced" | "withdrawn"

class KPIRow(BaseModel):
    metric: str               # e.g., "ARR", "Net Revenue Retention"
    value: Optional[str]      # Current value (string to handle %, $, etc.)
    prior_value: Optional[str]
    yoy_change: Optional[str]
    source: str               # "reported" | "call_disclosed" | "calculated"

class EarningsReviewOutput(BaseModel):
    executive_summary: str
    beat_miss: list[BeatMiss]
    guidance_deltas: list[GuidanceDelta]
    kpi_table: list[KPIRow]
    management_tone: str
    notable_quotes: list[str]
    thesis_impact: str
    one_offs: list[str]
    sector_template: str
    data_completeness: float  # ge=0.0, le=1.0
    data_sources_used: list[str]
```

---

## Deterministic vs LLM Split

### Deterministic (computed from structured data)

**beat_miss** — Computed from EarningsAgent's `eps_history`:
```python
def _compute_beat_miss(self, earnings_data, fundamentals_data) -> list[dict]:
    results = []
    eps_history = earnings_data.get("eps_history", [])
    if eps_history:
        latest = eps_history[0]
        actual, estimate = latest.get("actual"), latest.get("estimate")
        if actual is not None and estimate is not None:
            surprise = latest.get("surprise_pct", 0)
            verdict = "beat" if surprise > 1.0 else "miss" if surprise < -1.0 else "inline"
            results.append({
                "metric": "EPS",
                "actual": actual,
                "estimate": estimate,
                "surprise_pct": round(surprise, 2),
                "verdict": verdict,
            })
    # Revenue beat/miss from fundamentals if available
    # (analyst_estimates may have revenue consensus)
    return results
```

**data_completeness** — Weighted score:
```python
weights = {
    "earnings": 0.50,   # Primary input (0.15 if EPS only, 0.50 if transcript+EPS)
    "fundamentals": 0.30,  # Sector + context
    "market": 0.20,     # Price context
}
```
Earnings gets partial credit (0.15 of 0.50) if only EPS history is available without transcript data.

**sector_template** — Lookup from fundamentals sector field with default fallback.

### LLM (single-pass)

All remaining fields extracted by a single LLM call:
- `executive_summary` — 3-5 sentence key takeaways
- `guidance_deltas` — forward guidance changes with direction
- `kpi_table` — sector template metrics + call-only disclosures
- `management_tone` — overall tone with market context
- `notable_quotes` — 2-3 most important management quotes (short)
- `thesis_impact` — how this quarter affects the investment thesis
- `one_offs` — non-recurring items that distort results

---

## Sector KPI Templates

```python
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
```

Sector matching: exact match on `fundamentals_data.get("sector")`, fallback to `DEFAULT_KPI_TEMPLATE`. The LLM prompt includes: "Prioritize extracting these metrics, but also include any additional KPIs disclosed on the call that are not in the template."

---

## Data Input (LLM Prompt)

~2-3K tokens from three agents:

| Source | Data Included |
|--------|---------------|
| Earnings | highlights (with tags), guidance (metric/prior/current/direction), Q&A highlights (top 3-5), tone_analysis (5 dimensions), EPS history (last 4 quarters) |
| Fundamentals | company_name, sector, revenue, revenue_growth, gross_margin, business_description |
| Market | current_price, 52w high/low, price_change_1m |

---

## Partial Result (No Transcript)

When EarningsAgent has EPS history but no transcript:

```python
{
    "executive_summary": "No earnings transcript available for detailed review.",
    "beat_miss": [computed deterministically],
    "guidance_deltas": [],
    "kpi_table": [],
    "management_tone": "unknown",
    "notable_quotes": [],
    "thesis_impact": "",
    "one_offs": [],
    "sector_template": "Technology",  # still determined from fundamentals
    "data_completeness": 0.15,  # only partial earnings data
    "data_sources_used": ["earnings"],
    "partial": True,
}
```

When no earnings data at all: return fully empty result with `data_completeness: 0.0`.

---

## Guardrails

New function `validate_earnings_review_output()` in `src/llm_guardrails.py`:

- **Beat/miss sanity:** Verify deterministic beat/miss values are internally consistent (actual, estimate, surprise_pct agree on verdict)
- **KPI value validation:** Flag KPI values that look unreasonable (gross margin > 100%, negative counts, etc.)
- **Guidance consistency:** If guidance_deltas say "raised" but EarningsAgent tone is "defensive", add warning
- **Data completeness override:** Replace LLM-claimed value with deterministic calculation
- Returns `(validated_result, warnings)` per existing pattern

---

## Orchestrator Integration

Expand existing synthesis phase `asyncio.gather()`:

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

New method `_run_earnings_review_agent()` mirrors `_run_thesis_agent()`. Non-blocking failure.

Registration: `AGENT_REGISTRY` entry, NOT in `DEFAULT_AGENTS`.

---

## File Changes

| File | Change | Lines (est.) |
|------|--------|-------------|
| `src/agents/earnings_review_agent.py` | **New.** Single-pass LLM, deterministic beat/miss, sector templates, partial results. | ~250 |
| `src/models.py` | Add `BeatMiss`, `GuidanceDelta`, `KPIRow`, `EarningsReviewOutput` models. | ~40 |
| `src/orchestrator.py` | Import, registry entry, `_run_earnings_review_agent()`, expand `asyncio.gather()` to 3 agents. | ~35 |
| `src/llm_guardrails.py` | Add `validate_earnings_review_output()`. | ~60 |
| `tests/test_agents/test_earnings_review_agent.py` | **New.** Models, deterministic beat/miss, KPI templates, LLM mocking, guardrails, partial results. | ~200 |
| `tests/test_orchestrator.py` | Update synthesis phase tests for 3 parallel agents. | ~15 |

### Not in Scope
- Frontend changes (EarningsPanel modifications — separate task)
- Existing EarningsAgent modifications
- README/CLAUDE.md updates (after implementation)
