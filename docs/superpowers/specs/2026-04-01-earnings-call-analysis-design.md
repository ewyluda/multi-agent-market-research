# Earnings Call Analysis — Design Spec

## Overview

Add a dedicated Earnings Call Analysis section to the analysis view that provides deep, structured analysis of earnings call transcripts and Q&A sessions. A new `EarningsAgent` fetches up to 4 quarters of transcripts via FMP and uses LLM analysis to extract highlights, guidance breakdowns, Q&A summaries, and management tone — rendered in a rich `EarningsPanel.jsx` component.

## Architecture

### Approach: Dedicated Agent + New Section

A new `EarningsAgent` runs in parallel with all existing agents during the standard analysis pipeline. No new API endpoints, no modifications to the fundamentals agent, no new data provider methods.

```
Orchestrator → EarningsAgent.fetch_data() [parallel with other agents]
  → data_provider.get_earnings_transcripts(ticker, 4)
  → data_provider.get_earnings()
→ EarningsAgent.analyze(raw_data) [LLM call]
→ agent_results["earnings"] stored in DB
→ Frontend reads from analysis.agent_results.earnings
→ EarningsPanel.jsx renders structured data
```

### Why a separate agent (not extending fundamentals)

- Fundamentals agent is already ~1050 lines with a long LLM prompt — adding more degrades quality
- Dedicated agent gets a focused prompt optimized for transcript analysis
- Runs fully in parallel — no latency impact on the pipeline
- Can independently control transcript depth (4 quarters vs fundamentals' 2)

## Backend

### `src/agents/earnings_agent.py`

Inherits `BaseAgent`. No dependencies on other agents.

#### `fetch_data()`

Fetches concurrently via `asyncio.gather`:
- `self._data_provider.get_earnings_transcripts(ticker, num_quarters=4)` — up to 4 quarters of full transcripts
- `self._data_provider.get_earnings()` — EPS history (last 8 quarters of actual vs. estimate)

Returns combined dict with `transcripts` list and `earnings_history`.

#### `analyze(raw_data)`

Sends transcript content to LLM with a structured prompt. The prompt instructs the LLM to extract:

1. **Key highlights** — 4-6 items, each tagged with a category:
   - `BEAT` — metric that exceeded expectations
   - `MISS` — metric that missed expectations
   - `NEW` — new strategic announcement or initiative
   - `WATCH` — risk factor or concern raised

2. **Guidance breakdown** — for each guided metric (revenue, EPS, gross margin, capex, and any others mentioned):
   - Prior quarter guidance range
   - Current quarter guidance range
   - Direction: `raised` / `lowered` / `maintained` / `introduced` / `withdrawn`

3. **Q&A session highlights** — top 3-5 most material analyst exchanges:
   - Analyst name and firm
   - Topic tag (e.g., "AI Strategy", "China Risk", "Margins", "Capital Allocation")
   - Question summary (1 sentence)
   - Answer summary (2-3 sentences capturing management's response and any evasions/deflections)

4. **Management tone analysis** — five dimensions, each scored 0-100:
   - **Confidence** — how assured is management about execution and outlook?
   - **Specificity** — are answers detailed with numbers, or vague platitudes?
   - **Defensiveness** — how much deflection or pushback on tough questions?
   - **Forward-looking** — how much emphasis on future plans vs. backward-looking results?
   - **Hedging language** — frequency of qualifiers ("may", "could", "subject to", "uncertain")

5. **Overall stance** — `bullish` / `bearish` / `neutral` based on the totality of the call

6. **Full narrative analysis** — 2-3 paragraph written analysis for the AnalysisSection text content

The LLM response is parsed via structured output (JSON mode). If the most recent quarter's transcript is unavailable, the agent falls back to whatever quarters are available and notes the gap.

#### Output structure

```python
{
    "call_metadata": {
        "quarter": 1,
        "year": 2026,
        "date": "2026-01-30",
        "symbol": "AAPL"
    },
    "tone": "confident",              # overall management tone label
    "guidance_direction": "raised",    # raised/lowered/maintained/mixed
    "highlights": [
        {"tag": "BEAT", "text": "Revenue of $124.3B exceeded consensus..."},
        {"tag": "NEW", "text": "Announced $110B share buyback..."},
        {"tag": "WATCH", "text": "China revenue declined 2% QoQ..."}
    ],
    "guidance": [
        {
            "metric": "Revenue",
            "prior": "$117-121B",
            "current": "$125-130B",
            "direction": "raised"
        },
        {
            "metric": "EPS",
            "prior": "$2.28-2.35",
            "current": "$2.42-2.50",
            "direction": "raised"
        }
    ],
    "qa_highlights": [
        {
            "analyst": "Erik Woodring",
            "firm": "Morgan Stanley",
            "topic": "AI Strategy",
            "question": "How is Apple Intelligence adoption tracking?",
            "answer": "Management highlighted 60%+ adoption rate..."
        }
    ],
    "tone_analysis": {
        "confidence": 85,
        "specificity": 62,
        "defensiveness": 20,
        "forward_looking": 78,
        "hedging": 45
    },
    "eps_history": [  # built from get_earnings() data, not LLM output
        {"quarter": "Q1'26", "actual": 2.40, "estimate": 2.35, "surprise_pct": 2.1}
    ],
    "available_quarters": [
        {"quarter": 1, "year": 2026, "date": "2026-01-30"},
        {"quarter": 4, "year": 2025, "date": "2025-10-31"}
    ],
    "analysis": "Full LLM narrative for AnalysisSection...",
    "stance": "bullish",
    "data_source": "fmp"
}
```

### Orchestrator registration

In `src/orchestrator.py`:
- Add `"earnings": EarningsAgent` to `AGENT_REGISTRY`
- Add `"earnings"` to `DEFAULT_AGENTS`
- No dependency declarations — runs fully parallel in the gather phase

### Config

- `EARNINGS_AGENT_ENABLED` (default `true`) — opt-out toggle, consistent with `MACRO_AGENT_ENABLED` / `OPTIONS_AGENT_ENABLED` pattern
- `EARNINGS_TRANSCRIPT_QUARTERS` (default `4`) — number of quarters to fetch
- No new API keys required — uses existing `FMP_API_KEY`

## Frontend

### `EarningsPanel.jsx`

A special child component rendered inside `AnalysisSection` when the earnings section is expanded. Receives `analysis` prop, reads from `analysis.agent_results.earnings`.

#### Layout (top to bottom)

1. **Header row** (flex, 3 items):
   - Call metadata card: quarter label, date (glass card with blue accent)
   - Tone badge: overall management tone (color-coded: green=confident, amber=cautious, red=defensive)
   - Guidance direction badge: raised/lowered/maintained (color-coded)

2. **Key Highlights + Guidance Breakdown** (2-column grid):
   - Left: Tagged highlight items with colored category badges (BEAT=green, MISS=red, NEW=blue, WATCH=amber)
   - Right: Guidance comparison table — metric, prior range, current range, direction arrow with color

3. **Q&A Session Highlights** (full-width card):
   - Each exchange has a purple left-border accent
   - Shows: analyst name + firm, topic tag badge, question (italic), synthesized answer
   - 3-5 exchanges displayed

4. **Charts row** (2-column grid):
   - Left: **EPS Actual vs. Estimate** — horizontal paired bars for last 4 quarters, color-coded beat (green) / miss (red), with surprise % shown
   - Right: **Management Tone Analysis** — 5 horizontal progress bars (confidence, specificity, defensiveness, forward-looking, hedging) with color-coded labels

5. **Quarter indicator** (centered row of pills):
   - Shows available quarters as pill badges (up to 4)
   - Latest quarter highlighted with blue accent; others shown as muted pills
   - v1: display-only indicators (no interactive switching); interactive quarter toggle is a follow-up enhancement

#### Styling

- Uses existing `glass-card` / `glass-card-elevated` CSS classes
- Color palette matches existing theme: primary `#006fee`, success `#17c964`, danger `#f31260`, warning `#f5a524`, purple `#7828c8`
- Tables use `font-variant-numeric: tabular-nums` and JetBrains Mono for numeric values
- All charts are HTML/CSS (like `InflectionHeatmap.jsx`), not lightweight-charts
- Framer Motion `fadeUp` animation on section expand, consistent with other panels

### Dashboard integration

In `Dashboard.jsx`:
- Add to `SECTION_ORDER`: `{ key: 'earnings', name: 'Earnings', special: 'earnings' }` — positioned after `fundamentals`
- Add case to `renderSpecialChildren`: `case 'earnings': return <EarningsPanel analysis={analysis} />`
- Add stance logic in `getAgentStance` for `case 'earnings'`: read `stance` field from agent data

### SectionNav

`SectionNav.jsx` auto-generates from `SECTION_ORDER` — no changes needed.

## Scope boundaries

### In scope
- New `EarningsAgent` with LLM-powered transcript analysis
- `EarningsPanel.jsx` with all 5 layout sections described above
- Orchestrator registration and config toggles
- Dashboard integration (SECTION_ORDER, renderSpecialChildren, getAgentStance)

### Out of scope
- Interactive multi-quarter toggle (v1 shows latest quarter only with static quarter indicators)
- New data provider methods (reuses existing `get_earnings_transcripts` and `get_earnings`)
- Modifications to fundamentals agent (it keeps its existing transcript metrics extraction)
- New API endpoints (earnings data flows through standard analysis pipeline)
- Perception ledger KPI extraction for earnings (can be added later)
- Tests for the new agent (will be added in the implementation plan)

## Error handling

- If FMP transcript fetch returns empty (no API key, 402 paid plan, no transcripts available): agent returns `success=False` with appropriate message; section shows "Earnings call transcripts unavailable" placeholder
- If LLM parsing fails: fall back to displaying raw transcript metrics from the regex-based `_extract_transcript_metrics()` in fundamentals agent data, if available
- If fewer than 4 quarters available: render what's available, adjust quarter selector accordingly
