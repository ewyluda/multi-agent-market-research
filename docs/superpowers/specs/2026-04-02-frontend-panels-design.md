# Frontend Panels — Thesis, EarningsReview, Narrative, RiskDiff

**Date:** 2026-04-02
**Status:** Approved
**Context:** CapRelay feature replication — frontend visualization for the 5 new backend agents

---

## Overview

Four new React panel components that visualize output from the CapRelay synthesis agents. Each renders as a child of `AnalysisSection` (the existing wrapper pattern). Layout is hybrid — grid for structured panels (Thesis, EarningsReview, RiskDiff), stacked for narrative content (Narrative). Panels are inserted into `SECTION_ORDER` in Dashboard.jsx to form a "deep research" block after Earnings.

---

## Architecture Decisions

| # | Decision | Choice |
|---|----------|--------|
| 1 | Scope | One spec — all 4 panels together |
| 2 | Layout pattern | Hybrid — grid for structured, stacked for narrative |
| 3 | Panel placement | ThesisPanel mockup Option A (side-by-side bull/bear) |
| 4 | Section ordering | Deep research block: Earnings → EarningsReview → Thesis → Narrative → RiskDiff |
| 5 | Component pattern | Children of AnalysisSection, same as EarningsPanel |

Visual mockups saved in `.superpowers/brainstorm/` for reference.

---

## SECTION_ORDER (Dashboard.jsx)

Updated order with new panels inserted:

```javascript
const SECTION_ORDER = [
  { key: "fundamentals", name: "Fundamentals" },
  { key: "earnings", name: "Earnings", special: "earnings" },         // existing EarningsPanel
  { key: "earnings_review", name: "Earnings Review", special: "earnings_review" },  // NEW
  { key: "thesis", name: "Thesis", special: "thesis" },                             // NEW
  { key: "narrative", name: "Narrative", special: "narrative" },                     // NEW
  { key: "risk_diff", name: "Risk Analysis", special: "risk_diff" },                // NEW
  { key: "technical", name: "Technical" },
  { key: "sentiment", name: "Sentiment" },
  { key: "macro", name: "Macro" },
  { key: "news", name: "News", special: "news" },
  { key: "options", name: "Options", special: "options" },
  { key: "leadership", name: "Leadership", special: "leadership" },
  { key: "council", name: "Council", special: "council" },
];
```

Note: The new synthesis agents (thesis, earnings_review, narrative, risk_diff) store their data on `analysis.thesis`, `analysis.earnings_review`, `analysis.narrative`, `analysis.risk_diff` — NOT in `agent_results`. The `renderSpecialChildren` function and data extraction helpers need to handle this.

---

## Panel 1: ThesisPanel.jsx

**Data source:** `analysis?.thesis || null`

**Layout:** Grid (bull/bear side-by-side + tension points list + management questions)

**Sub-components:**
1. **ThesisSummary** — Summary paragraph with data completeness badge
2. **BullBearCards** — Two equal-width cards with green/red borders, thesis text, key drivers list, catalysts list
3. **TensionPointsList** — Cards for each tension point with bull/bear views side by side, evidence, resolution catalyst
4. **ManagementQuestions** — List with CEO/CFO role badges (blue/purple)

**Conditional rendering:** If `analysis?.thesis` is null or has `error`, show a muted "Thesis analysis not available" message.

**Color scheme:**
- Bull: `#17c964` (green) backgrounds and borders
- Bear: `#f31260` (red) backgrounds and borders
- CEO badge: `#006fee` (blue)
- CFO badge: `#7828c8` (purple)
- Resolution catalyst: muted text with arrow prefix

---

## Panel 2: EarningsReviewPanel.jsx

**Data source:** `analysis?.earnings_review || null`

**Layout:** Grid (beat/miss badges + KPI table + quotes/impact)

**Sub-components:**
1. **ExecutiveSummary** — Glass card with 3-5 sentence summary
2. **BeatMissBadges** — 3 equal cards: EPS verdict, Guidance direction, Management tone. Large verdict text with colored backgrounds
3. **KPITable** — Full-width table with columns: Metric, Value, Prior, YoY, Source. Source badges: "reported" (gray), "call" (blue), "calc" (gray)
4. **BottomRow** — 2-column: Notable Quotes (italic) | Thesis Impact + One-offs (amber warning)

**Conditional rendering:**
- If `partial: true` — show beat/miss badges but muted "No transcript available" for LLM-derived sections
- If null — show "Earnings review not available"

**Color scheme:**
- Beat: `#17c964` (green)
- Miss: `#f31260` (red)
- Inline: `rgba(255,255,255,0.5)` (muted)
- Raised: `#17c964` | Lowered: `#f31260` | Maintained: muted
- Sector template badge: `#006fee` (blue)

---

## Panel 3: NarrativePanel.jsx

**Data source:** `analysis?.narrative || null`

**Layout:** Stacked (company arc → year sections → thematic chapters → current chapter)

**Sub-components:**
1. **CompanyArc** — Gradient glass card (blue-purple) with overarching narrative and metadata badges
2. **YearSections** — Stacked cards with colored left borders (neutral gray, blue, green based on growth). Each card has: headline, 2x2 grid (revenue/margins/strategy/capital), inline quarterly inflection highlight (if any, with impact badge)
3. **NarrativeChapters** — Side-by-side cards for thematic threads, colored by sentiment of the theme
4. **CurrentChapter** — Glass card with "Where We Are Now" label

**Year section left border colors:**
- Negative/flat growth: `rgba(255,255,255,0.15)` (muted)
- Moderate growth: `#006fee` (blue)
- Strong growth: `#17c964` (green)

**Quarterly inflection badges:**
- Positive: green background
- Negative: red background
- Pivotal: blue background

**Conditional rendering:** If null — show "Financial narrative not available"

---

## Panel 4: RiskDiffPanel.jsx

**Data source:** `analysis?.risk_diff || null`

**Layout:** Grid (summary + score → emerging threats → change cards → filing metadata)

**Sub-components:**
1. **SummaryAndScore** — 2-column: summary text (flex:2) | risk score gauge + delta (flex:1)
2. **EmergingThreats** — Red-tinted card with threat tag pills
3. **RiskChangeCards** — Cards for each change with type badge (NEW/ESCALATED/DE-ESCALATED/REMOVED/REWORDED), severity badge, analysis text, prior/current excerpts for escalated risks
4. **FilingMetadata** — Footer with filing type/date badges showing extraction method

**Change type badge colors:**
- NEW: red (`#f31260`)
- ESCALATED: amber (`#f5a524`)
- DE-ESCALATED: green (`#17c964`)
- REMOVED: muted gray
- REWORDED: blue (`#006fee`)

**Severity badge colors:**
- HIGH: red
- MEDIUM: amber
- LOW: gray

**Conditional rendering:**
- `has_diff: false` — show risk inventory table only, muted "Only 1 filing available — no diff"
- null — show "Risk analysis not available"

**Extraction method badges:**
- "pattern" — gray badge
- "llm_fallback" — blue badge

---

## Dashboard.jsx Changes

### Data Extraction for New Panels

The new panels read from `analysis.thesis`, `analysis.earnings_review`, etc. (top-level analysis fields, not `agent_results`). The existing `getAgentStance`, `getAgentSummary`, `getAgentMetrics` helpers need entries for the new keys.

```javascript
// In getAgentStance:
case "thesis": return "neutral";  // Thesis is always neutral (no conviction scoring)
case "earnings_review": return data?.beat_miss?.[0]?.verdict === "beat" ? "bullish" : data?.beat_miss?.[0]?.verdict === "miss" ? "bearish" : "neutral";
case "narrative": return "neutral";
case "risk_diff": return data?.risk_score_delta > 5 ? "bearish" : data?.risk_score_delta < -5 ? "bullish" : "neutral";

// In getAgentSummary:
case "thesis": return data?.thesis_summary;
case "earnings_review": return data?.executive_summary;
case "narrative": return data?.company_arc;
case "risk_diff": return data?.summary;
```

### renderSpecialChildren

```javascript
case "earnings_review": return <EarningsReviewPanel analysis={analysis} />;
case "thesis": return <ThesisPanel analysis={analysis} />;
case "narrative": return <NarrativePanel analysis={analysis} />;
case "risk_diff": return <RiskDiffPanel analysis={analysis} />;
```

### SectionNav Update

Add the 4 new sections to the in-page navigation links.

---

## File Changes

| File | Change | Lines (est.) |
|------|--------|-------------|
| `frontend/src/components/ThesisPanel.jsx` | **New.** Bull/bear cards, tension points, management questions. | ~250 |
| `frontend/src/components/EarningsReviewPanel.jsx` | **New.** Beat/miss badges, KPI table, quotes, thesis impact. | ~300 |
| `frontend/src/components/NarrativePanel.jsx` | **New.** Company arc, year sections, chapters, inflections. | ~280 |
| `frontend/src/components/RiskDiffPanel.jsx` | **New.** Risk score, emerging threats, change cards, filing metadata. | ~300 |
| `frontend/src/components/Dashboard.jsx` | Update SECTION_ORDER, renderSpecialChildren, data extraction helpers. | ~40 |
| `frontend/src/components/SectionNav.jsx` | Add 4 new section links. | ~10 |

### Not in Scope
- Tag screening UI (separate feature)
- Backend changes (all agents already implemented)
- Tests (React component tests not in current test suite pattern)
