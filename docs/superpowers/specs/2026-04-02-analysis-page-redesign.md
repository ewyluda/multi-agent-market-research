# Analysis Page Redesign

**Date**: 2026-04-02
**Approach**: Component Restructure (Approach B) — restructure in logical groups, preserving existing sub-components

---

## 1. Spacing & Layout Tokens

Add CSS custom properties to `frontend/src/index.css`:

```css
--space-card-gap: 20px;      /* gap between cards within a section */
--space-section-gap: 32px;    /* gap between major sections */
--space-card-padding: 20px;   /* internal card padding */
--space-metrics-gap: 16px;    /* gap between metric items in grids */
```

All components migrate from hardcoded Tailwind gap classes (`gap-3`, `gap-4`) to these tokens for section/card-level spacing. The `glass-card` base class padding updates to `--space-card-padding`.

---

## 2. Section Navigation (Pill Tabs)

Replace the current horizontal tab row in `SectionNav.jsx` with pill-style tabs:

- **Shape**: `border-radius: 9999px`, padding `px-5 py-2.5`
- **Gap**: `16px` between pills
- **Active**: `--accent-blue` background, white text
- **Inactive**: transparent background, `--text-muted` text, subtle border `rgba(255,255,255,0.06)`
- **Hover**: background `rgba(255,255,255,0.06)`, text `--text-secondary`
- **Transition**: 150ms background + color

New tab list (10 items, down from 13):

1. Company Overview
2. Earnings
3. Earnings Review
4. Thesis
5. Risk Analysis
6. Technicals & Options
7. Sentiment
8. News
9. Leadership
10. Council

Horizontally scrollable on small screens with fade-edge indicators as fallback.

---

## 3. Company Overview (New Composite Section)

New component `CompanyOverview.jsx` — three stacked glass cards, no collapsibles:

### Card 1 — Company Description
- 3-4 line summary: what the company does, where they operate, biggest revenue segments
- Source: fundamentals agent `company_overview` / `description` field
- Clean prose, no metrics

### Card 2 — Narrative
- Existing `NarrativePanel` content rendered directly (CompanyArc, YearSections, NarrativeChapters, CurrentChapter)
- All sub-sections always visible
- Updated spacing tokens

### Card 3 — Fundamentals Metrics
- No text block for metrics (description moved to Card 1)
- Responsive grid of metric cards (2-3 columns on desktop)
- Each metric card: muted label on top, large bold value below, optional delta indicator
- Metrics: P/E Ratio (`toFixed(1)`), Revenue Growth (%), Net Margin (%), Health Score (/100), Market Cap, EPS, Dividend Yield
- Fundamentals agent summary/analysis text below the metric grid as prose with paragraph spacing

Replaces separate Fundamentals and Narrative entries in `SECTION_ORDER`. NarrativePanel imported directly into CompanyOverview.

---

## 4. Earnings Section Readability

Changes to `EarningsPanel.jsx` summary text:

### Hybrid format
- **Opening paragraph**: 2-3 sentences of context (headline takeaway)
- **Bulleted list**: key specifics (beats/misses, notable metrics, management commentary)
- Parsing: split summary at sentence boundaries. First 2-3 sentences → paragraph, remaining → bullets. If agent returns structured data, use directly.

### Spacing
- All sub-cards (HighlightsCard, GuidanceCard, QACard, EPSChart, ToneChart) use `--space-card-gap`
- Internal card padding uses `--space-card-padding`

No collapsibles — full earnings content always visible (already compliant).

---

## 5. Technicals & Options (Combined Section)

New component `TechnicalsOptionsSection.jsx` — two stacked glass cards under one header:

### Card 1 — Technical Indicators
- Metric card grid (same style as Fundamentals Card 3): RSI, MACD interpretation, Signal Strength, Trend Direction, Support/Resistance levels
- Color-coded values where meaningful (RSI overbought/oversold → red/green accents)
- Technical agent summary as prose with paragraph spacing below
- No collapsible

### Card 2 — Options Flow
- Existing `OptionsFlow` component rendered directly
- Updated spacing tokens
- No visual design changes

Dashboard treats `technicals_options` as a single entry. Old separate `technical` and `options` entries removed from `SECTION_ORDER`.

---

## 6. Thesis Section (Empty State + Retry)

Changes to `ThesisPanel.jsx`:

### Empty state (when `analysis.analysis.thesis` is null)
- Glass card with:
  - Muted placeholder icon
  - "Thesis analysis unavailable" in `--text-secondary`
  - "The thesis agent didn't return data for this analysis" in `--text-muted`
  - Retry button: pill-style, `--accent-blue` outline, "Retry Thesis Analysis" label

### Retry mechanism
- Button calls `POST /api/analyze/{ticker}?agents=thesis`
- Loading spinner on button while in progress
- On success: ThesisPanel re-renders with returned data
- On failure: brief error message below button

### When data exists
- No layout changes — existing bull/bear cards, tension points, management questions stay
- Updated spacing tokens only

---

## 7. Investor Council (Always-Visible Scenarios)

Changes to `CouncilPanel.jsx`:

### Remove scenario toggle
- Delete the expand/collapse button and `AnimatePresence` wrapper
- ScenarioPill components render inline at bottom of each InvestorCard, always visible
- Keep staggered entrance animation on page load
- Add "If-Then Scenarios" muted sub-header within card to visually separate from key observations

### Spacing
- InvestorCard padding: `--space-card-padding`
- Gap between investor cards: `--space-card-gap` (20px)
- Scenario pill internal gap: `gap-3` (up from `gap-2`)

No other changes — avatar, stance badge, thesis health, disagreement banner all stay.

---

## 8. Macro Standalone Page

### Removed from analysis page
- Delete macro entry from `SECTION_ORDER`

### New route: `/macro`
- Left sidebar under "Research" group divider
- Sidebar restructure:
  - **Research**: Analysis, Macro
  - **Tools**: Watchlist, Portfolio, Schedules, Alerts
  - **History**: History, Inflections

### Page content
- Same macro data as before: Fed Funds Rate, CPI, GDP Growth, macro agent summary
- Glass-card styling, metric card grid, spacing tokens
- Fetches via existing `GET /api/macro-events` endpoint (not tied to specific ticker)
- Header: "Macro Environment" with last-updated timestamp
- Simple single-column layout (future-proof for sector rotation/money flow additions)

---

## 9. PriceChart Moving Averages & Timeframe

Changes to `PriceChart.jsx`:

### Default visibility
- Update `SMA_CONFIG`: set `defaultVisible: true` for all five periods (9, 20, 50, 100, 200)
- Toggle buttons remain functional — user can turn off individual SMAs
- Colors unchanged (red/amber/green/blue/purple)

### Default timeframe
- Chart initializes with 1 year of daily candlestick data
- Ensure price history request covers at least 365 days
- If timeframe selector exists, default to "1Y"

---

## 10. Global Cleanup

### Remove all collapsible sections
- `AnalysisSection.jsx`: delete "Show full analysis" toggle and truncation logic
- All content renders fully by default
- Component still works as wrapper (accent bar, title, stance badge, metrics, body) for sections that use it (Sentiment, News)

### Final section order on analysis page

1. Search bar + Price chart (all SMAs on, 1Y daily)
2. Recommendation card
3. **Company Overview** (Description → Narrative → Fundamentals)
4. **Earnings**
5. **Earnings Review**
6. **Thesis** (empty state + retry)
7. **Risk Analysis**
8. **Technicals & Options** (combined)
9. **Sentiment**
10. **News**
11. **Leadership**
12. **Council** (scenarios always visible)

Macro removed — lives at `/macro`.

---

## Files Affected

| File | Change |
|------|--------|
| `frontend/src/index.css` | Add spacing tokens, update glass-card padding |
| `frontend/src/components/SectionNav.jsx` | Pill-style tabs, new tab list |
| `frontend/src/components/CompanyOverview.jsx` | **New** — composite section |
| `frontend/src/components/TechnicalsOptionsSection.jsx` | **New** — combined wrapper |
| `frontend/src/components/Dashboard.jsx` | New SECTION_ORDER, render new components, remove macro |
| `frontend/src/components/AnalysisSection.jsx` | Remove collapsible toggle, update spacing |
| `frontend/src/components/EarningsPanel.jsx` | Hybrid summary format, spacing |
| `frontend/src/components/ThesisPanel.jsx` | Empty state + retry button |
| `frontend/src/components/CouncilPanel.jsx` | Remove scenario toggle, always visible |
| `frontend/src/components/PriceChart.jsx` | All SMAs default visible, 1Y timeframe |
| `frontend/src/components/NarrativePanel.jsx` | Spacing token updates |
| `frontend/src/components/OptionsFlow.jsx` | Spacing token updates |
| `frontend/src/components/MacroPage.jsx` | **New** — standalone macro page |
| `frontend/src/components/Sidebar.jsx` (or equivalent) | Research/Tools/History grouping |
| `frontend/src/App.jsx` | Add `/macro` route |
