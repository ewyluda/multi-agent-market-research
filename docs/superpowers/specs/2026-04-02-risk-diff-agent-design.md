# Risk Diff Agent — Risk Factor Change Detection

**Date:** 2026-04-02
**Status:** Approved
**Context:** CapRelay feature replication — fifth and final planned agent

---

## Overview

A two-pass LLM hybrid agent that fetches SEC filing risk factor sections and compares them across periods to detect new, removed, escalated, and de-escalated risks. Uses FMP for filing metadata discovery and EDGAR for full-text retrieval. HTML parsing uses section-based pattern matching with LLM fallback for messy filings. Produces both a risk inventory (always) and a period-over-period diff (when 2+ filings available). Runs in the synthesis phase parallel with 5 other agents.

---

## Architecture Decisions

| # | Decision | Choice | Alternatives |
|---|----------|--------|-------------|
| 1 | Scope | Single spec — EDGAR integration + agent | Split EDGAR from agent |
| 2 | Filing data source | Hybrid — FMP metadata + EDGAR full text | EDGAR only; FMP only |
| 3 | HTML parsing | Pattern matching + LLM fallback | Regex only (~80%); fully LLM |
| 4 | Filing comparison scope | Two most recent 10-Ks + latest 10-Q (3 max) | Two 10-Ks only; configurable |
| 5 | Diff strategy | Two-pass LLM (extract inventories → diff) | Fully LLM; deterministic + LLM |
| 6 | Data gate | Require 2+ for diff, 1 → inventory only, 0 → empty | Always try with completeness |

Full rationale in memory: `project_caprelay_risk_diff_decisions.md`

---

## EDGAR Integration (data_provider.py)

### New Methods

**`_resolve_cik(ticker) -> Optional[str]`**
- Maps ticker to CIK number via `https://www.sec.gov/files/company_tickers.json`
- Caches result (CIK mapping is stable)
- Already partially implemented in `news_agent.py` — extract to shared utility in data_provider

**`get_sec_filing_metadata(ticker, filing_type="10-K", limit=3) -> list[dict]`**
- Uses FMP `/stable/sec-filings?symbol={ticker}&type={filing_type}&limit={limit}`
- Returns `[{accession_number, filing_date, filing_type, filing_url}]`
- TTL cached

**`get_sec_filing_section(ticker, filing_url, section="1A") -> dict`**
- Fetches filing HTML from the URL (EDGAR hosted)
- Parses Item 1A using two-tier extraction:
  1. **Fast path:** BeautifulSoup + regex for `Item\s*1A[\.\s\-—]*Risk\s*Factors` header, extract until next Item header
  2. **LLM fallback:** If no confident match, strip HTML tags, truncate to 30K chars, send to LLM with "Extract the Risk Factors section"
- Returns `{section_text, extraction_method: "pattern"|"llm_fallback", char_count}`
- Uses `SEC_EDGAR_USER_AGENT` from config for requests
- Requires `beautifulsoup4` dependency

### CIK Resolution

```python
async def _resolve_cik(self, ticker: str) -> Optional[str]:
    """Resolve ticker to SEC CIK number."""
    # Check cache first
    # Fetch https://www.sec.gov/files/company_tickers.json
    # Search for ticker match, return zero-padded CIK
```

---

## Output Schema

```python
class RiskTopic(BaseModel):
    topic: str                # e.g., "Supply Chain Concentration"
    severity: str             # "high" | "medium" | "low"
    summary: str              # 2-3 sentence description
    text_excerpt: str         # Brief excerpt from filing

class RiskChange(BaseModel):
    risk_topic: str
    change_type: str          # "new" | "removed" | "escalated" | "de-escalated" | "reworded"
    severity: str             # "high" | "medium" | "low"
    current_text_excerpt: str
    prior_text_excerpt: str   # Empty string if new risk
    analysis: str             # Why this change matters for investors

class RiskDiffOutput(BaseModel):
    # Diff results (empty if only 1 filing available)
    new_risks: list[RiskChange]
    removed_risks: list[RiskChange]
    changed_risks: list[RiskChange]
    risk_score: float                  # 0-100 composite risk score
    risk_score_delta: float            # Change from prior period (0 if no prior)
    top_emerging_threats: list[str]    # 3-5 most actionable new/escalated risks
    summary: str                       # 2-3 sentence risk landscape summary

    # Risk inventory (always populated from latest filing)
    current_risk_inventory: list[RiskTopic]

    # Metadata
    filings_compared: list[dict]       # {type, date, accession_number} per filing
    has_diff: bool                     # True if 2+ filings compared
    extraction_methods: list[str]      # "pattern" | "llm_fallback" per filing
    data_completeness: float           # 0.0-1.0
    data_sources_used: list[str]
```

---

## Two-Pass LLM Flow

### fetch_data() — Hybrid Data Sourcing

```
1. Get filing metadata from FMP (two most recent 10-Ks + latest 10-Q)
2. For each filing, concurrently:
   a. Fetch HTML from EDGAR
   b. Parse Item 1A (fast path or LLM fallback)
3. Return {filings: [{type, date, accession, risk_text, extraction_method}], agent_results}
```

All filing fetches run concurrently via `asyncio.gather()`. Failures are non-fatal — skipped filings reduce `data_completeness`.

### Pass 1 — Risk Inventory ("The Cataloger")

Runs once per filing that has risk text. **Concurrent** — all Pass 1 calls run in parallel.

**Input:** One risk section (~5-15K chars, truncated to ~10K if needed)

**Output:**
```json
{
    "risks": [
        {"topic": "Supply Chain Concentration", "severity": "high",
         "summary": "Company depends on 3 suppliers for 80% of components.",
         "text_excerpt": "We rely on a limited number of suppliers..."}
    ]
}
```

**Prompt guardrails:**
- "Extract distinct risk topics from this filing's Risk Factors section."
- "Severity should reflect language intensity: 'material adverse effect' = high, 'could impact' = medium, 'may affect' = low."
- "Do not invent risks not present in the text."

### Pass 2 — Risk Diff ("The Comparator")

**Input:** Pass 1 structured inventories for current 10-K vs prior 10-K (~1-2K tokens each). If 10-Q inventory exists, included as supplementary context.

**Output:** Full `RiskDiffOutput` minus metadata fields (those are attached by the agent).

**Prompt guardrails:**
- "Classify each change as: new (not in prior), removed (in prior but not current), escalated (same topic but stronger language/higher severity), de-escalated (weaker language), reworded (same meaning, different words)."
- "risk_score: 0=minimal risk, 100=extreme risk. Base on count and severity of current risks."
- "risk_score_delta: positive means riskier than prior period, negative means safer."

### Error Handling

- All filing fetches fail → empty result (`data_completeness: 0.0`)
- 1 filing parsed → risk inventory only (`has_diff: false`, diff fields empty)
- 2+ filings parsed → full diff
- Pass 1 fails for a filing → skip that filing, reduce completeness
- Pass 2 fails → return Pass 1 inventories as fallback

---

## HTML Parsing Detail

### Fast Path (BeautifulSoup + regex)

```python
def _parse_risk_section(html: str) -> Optional[str]:
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(separator="\n")
    
    # Find Item 1A header
    pattern = r"(?:Item\s*1A[\.\s\-—:]*Risk\s*Factors)"
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return None  # Trigger LLM fallback
    
    start = match.start()
    
    # Find next Item header (Item 1B, Item 2, etc.)
    end_pattern = r"(?:Item\s*(?:1B|2)[\.\s\-—:])"
    end_match = re.search(end_pattern, text[start + 100:], re.IGNORECASE)
    end = (start + 100 + end_match.start()) if end_match else start + 50000
    
    section = text[start:end].strip()
    return section if len(section) > 200 else None  # Too short = bad parse
```

### LLM Fallback

When fast path returns `None`:
```
"The following is a SEC filing document. Extract ONLY the Risk Factors section 
(Item 1A). Return the full text of that section, nothing else. If you cannot 
find a Risk Factors section, return 'NOT_FOUND'."
```

Input: first 30K chars of cleaned text (HTML stripped). Track `extraction_method: "llm_fallback"`.

---

## Data Completeness

```python
weights = {
    "latest_10k": 0.40,     # Got current annual risk section
    "prior_10k": 0.30,      # Got prior annual for comparison
    "latest_10q": 0.15,     # Got quarterly supplement
    "fundamentals": 0.15,   # Context from agent_results
}
```

---

## Guardrails

New function `validate_risk_diff_output()` in `src/llm_guardrails.py`:

- **Risk score bounds:** Clamp `risk_score` to [0, 100], `risk_score_delta` to [-50, +50]
- **Change type validation:** Verify all `change_type` in {"new", "removed", "escalated", "de-escalated", "reworded"}
- **Severity validation:** Verify all severity in {"high", "medium", "low"}
- **Diff consistency:** If `has_diff=False`, warn if diff fields are non-empty
- Returns `(validated_result, warnings)`

---

## Orchestrator Integration

6th agent in `asyncio.gather()`:

```python
final_analysis, thesis_result, earnings_review_result, narrative_result, tag_result, risk_diff_result = await asyncio.gather(
    self._run_solution_agent(ticker, agent_results),
    self._run_thesis_agent(ticker, agent_results),
    self._run_earnings_review_agent(ticker, agent_results),
    self._run_narrative_agent(ticker, agent_results),
    self._run_tag_extractor_agent(ticker, agent_results),
    self._run_risk_diff_agent(ticker, agent_results),
)
```

Result attached as `final_analysis["risk_diff"]`. Non-blocking failure.

Note: The risk_diff agent needs `_data_provider` for EDGAR calls (injected via `_inject_shared_resources()`), same as narrative agent.

---

## File Changes

| File | Change | Lines (est.) |
|------|--------|-------------|
| `src/agents/risk_diff_agent.py` | **New.** Hybrid EDGAR fetching, HTML parsing with LLM fallback, two-pass LLM, risk inventory + diff. | ~400 |
| `src/data_provider.py` | Add `get_sec_filing_metadata()`, `get_sec_filing_section()`, `_resolve_cik()`. | ~120 |
| `src/models.py` | Add `RiskTopic`, `RiskChange`, `RiskDiffOutput` models. | ~35 |
| `src/orchestrator.py` | Import, registry, `_run_risk_diff_agent()`, expand gather to 6. | ~35 |
| `src/llm_guardrails.py` | Add `validate_risk_diff_output()`. | ~50 |
| `requirements.txt` | Add `beautifulsoup4`. | ~1 |
| `tests/test_agents/test_risk_diff_agent.py` | **New.** HTML parsing, filing mocks, risk inventory, diff flow, guardrails. | ~250 |
| `tests/test_orchestrator.py` | Update for 6 parallel agents. | ~15 |

### Not in Scope
- Frontend risk diff visualization
- Filing text caching in SQLite
- README/CLAUDE.md updates (after implementation)
