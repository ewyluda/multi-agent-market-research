# Frontend Redesign — Narrative-First Hybrid Layout

**Date:** 2026-03-31
**Status:** Design approved, pending implementation plan
**Approach:** Incremental refactor of existing React + Vite + Tailwind stack (no framework migration)

## Problem Statement

The current frontend fragments the analysis story across 6 tabs, requiring users to click between views to piece together a coherent picture. The recommendation gauge feels dated, information density is poor, and the visual design lacks the polish of a professional research tool. The UI needs to support three usage modes — quick checks, deep dives, and portfolio monitoring — without compromising any of them.

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Mental model | Hybrid: Dashboard strip + Briefing narrative | Supports both quick-check and deep-dive workflows in one view |
| Recommendation display | V2 Split Thesis Card (verdict left, evidence right) | Tells a mini-story: bold verdict + target + agent heatmap on left, thesis narrative + supporting signals on right |
| Analysis body | Single scrollable page with sticky section mini-nav | No tabs fragmenting the narrative; scroll the story top-to-bottom, jump via mini-nav |
| Section design | V1 Headline + Expandable Detail | Compact summary always visible with key metrics; "Show more" for full agent output |
| Sidebar nav | Expanded 220px with labels, sections, and recent analyses | Proper navigation with quick-access recent tickers |
| Price chart | Prominent, below thesis card, with SMA overlays (9, 20, 50, 100, 200) | Chart is essential context; SMA indicators add actionable technical data |
| Meta/debug content | Separate area (footer link to diagnostics) | Keeps the investment narrative clean; meta info accessible but not in the flow |
| Other views | Full rework with consistent design language | History, watchlist, portfolio, schedules, alerts all get the new card/typography system |
| Tech approach | Incremental refactor (same React + Vite + Tailwind stack) | Avoids framework migration risk; fastest path to the UX improvement |

## Layout Architecture

### Analysis View (Primary)

```
┌─────────────────────────────────────────────────────────────┐
│ SIDEBAR (220px fixed)  │  MAIN CONTENT (flex-1)             │
│                        │                                     │
│ ● Market Research      │  ┌─ Search Bar (sticky) ─────────┐ │
│                        │  │ [ticker input] [Analyze] ●●●●● │ │
│ ANALYSIS               │  └─────────────────────────────────┘ │
│  ▸ Analysis (active)   │                                     │
│  ▸ History             │  ┌─ Thesis Card (V2 Split) ──────┐ │
│                        │  │ AAPL · $187.42    │ Thesis...   │ │
│ PORTFOLIO              │  │ BUY               │ ▲ signal 1  │ │
│  ▸ Watchlist           │  │ Target $195-210   │ ▲ signal 2  │ │
│  ▸ Holdings            │  │ ▓▓▓▓░▓▓ heatmap  │ ● signal 3  │ │
│  ▸ Schedules           │  └─────────────────────────────────┘ │
│  ▸ Alerts              │                                     │
│                        │  ┌─ Chart (candlestick + SMAs) ───┐ │
│ ─────────────          │  │  [1W] [1M] [3M] [6M] [1Y]     │ │
│                        │  │  ████████████████████████████   │ │
│ RECENT                 │  │  SMA9 SMA20 SMA50 SMA100 SMA200│ │
│  AAPL  BUY             │  └─────────────────────────────────┘ │
│  NVDA  BUY             │                                     │
│  TSLA  HOLD            │  ┌─ Section Nav (sticky) ─────────┐ │
│                        │  │ FUN TCH SNT MAC NWS OPT LDR CNC│ │
│                        │  └─────────────────────────────────┘ │
│                        │                                     │
│                        │  ┌─ Fundamentals ─────────────────┐ │
│                        │  │ ● Bullish                      │ │
│                        │  │ Summary text...                │ │
│                        │  │ P/E 28.4x  Rev +12%  Margin... │ │
│                        │  │ Show full analysis ▼           │ │
│                        │  └────────────────────────────────┘ │
│                        │  ┌─ Technical ────────────────────┐ │
│                        │  │ ● Neutral                      │ │
│                        │  │ Summary text...                │ │
│                        │  │ RSI 58  MACD Bullish  ...      │ │
│                        │  │ Show full analysis ▼           │ │
│                        │  └────────────────────────────────┘ │
│                        │                                     │
│                        │  ... Sentiment, Macro, News,        │
│                        │      Options, Leadership, Council   │
│                        │                                     │
│                        │  ┌─ Meta Footer ──────────────────┐ │
│                        │  │ Analyzed Mar 31 · 4.2s · 7/7   │ │
│                        │  │              View Diagnostics → │ │
│                        │  └────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### Component Breakdown

#### 1. Sidebar (`Sidebar.jsx` — rewrite)

- **Width:** 220px fixed, full height
- **Sections:**
  - Logo/brand at top
  - "Analysis" group: Analysis (main), History
  - "Portfolio" group: Watchlist, Holdings, Schedules, Alerts
  - Divider
  - "Recent" section at bottom: last 3-5 analyzed tickers with recommendation badge
- **Behavior:** Active item highlighted with primary color tint. Clicking recent ticker loads that analysis.

#### 2. Search Bar (`SearchBar.jsx` — extract from ContentHeader)

- **Position:** Sticky top, z-40, backdrop-blur
- **Contents:** Ticker input, Analyze button, agent progress dots (right-aligned)
- **Agent dots:** 7 dots showing running/done/failed state during analysis. Compact, not the full pipeline bar.

#### 3. Thesis Card (`ThesisCard.jsx` — new, replaces Recommendation.jsx)

- **Layout:** V2 Split — two-column card
- **Left column (200px):**
  - Ticker + price + daily change
  - Large recommendation text (BUY/HOLD/SELL) colored by sentiment
  - Price target range
  - Agent heatmap (7 colored bars) with labels (MKT, FUN, TCH, NWS, SNT, MAC, OPT)
- **Right column (flex-1):**
  - Thesis narrative (1-3 sentences from solution agent synthesis)
  - 3 supporting signals with directional arrows (pulled from top agent findings)
- **Card styling:** Subtle gradient background tinted to recommendation color. Border tinted to match.
- **Data source:** `analysis.analysis` (solution agent output) + `agent_results` for individual signals

#### 4. Price Chart (`PriceChart.jsx` — enhance existing)

- **Position:** Below thesis card
- **Enhancements:**
  - Add SMA overlays: 9-day (red), 20-day (amber), 50-day (green), 100-day (blue), 200-day (purple)
  - SMA legend below chart with toggleable visibility
  - Time range buttons: 1W, 1M, 3M, 6M, 1Y, ALL
  - Calculate SMAs from price history data already available from market agent
- **Implementation:** lightweight-charts `addLineSeries()` for each SMA period. Compute SMA values client-side from OHLCV data.

#### 5. Section Nav (`SectionNav.jsx` — new)

- **Position:** Sticky below search bar (top offset accounts for search bar height)
- **Contents:** Horizontal pill buttons for each agent section: Fundamentals, Technical, Sentiment, Macro, News, Options, Leadership, Council
- **Behavior:** Click scrolls to that section smoothly. Active state updates on scroll via IntersectionObserver. Highlighted with primary color tint.

#### 6. Analysis Section (`AnalysisSection.jsx` — new shared component)

Each agent's output renders as an instance of this component. Props: `name`, `stance`, `summary`, `metrics`, `fullContent`, `dataSource`, `duration`.

- **Header:** Colored accent bar (3px) + section name + stance badge (Bullish/Neutral/Bearish)
- **Summary:** 2-3 sentence narrative from the agent's analysis
- **Metrics row:** 3-5 key metrics displayed inline (label + value, colored when directional)
- **Expand:** "Show full analysis" link reveals the complete agent output
- **Meta:** Data source + duration (e.g., "FMP · 1.2s") in top-right, muted

**Section order (narrative flow):**
1. Fundamentals — the company's financial health
2. Technical — what the chart says
3. Sentiment — how the market feels
4. Macro — economic backdrop
5. News — recent catalysts
6. Options — smart money positioning
7. Leadership — management quality
8. Council — legendary investor perspectives

#### 7. Meta Footer (`MetaFooter.jsx` — new)

- **Position:** Below all sections
- **Contents:** Analysis timestamp, total duration, agent success count, "View Diagnostics →" link
- **Diagnostics:** Opens as a slide-over panel from the right edge (not a full page view), showing agent timing, data quality checks, guardrail warnings, validation results. Slide-over chosen over modal so the analysis context remains partially visible.

### Secondary Views

All views share the sidebar + search bar chrome. Content area changes per view.

#### History View (`HistoryView.jsx` — rewrite of HistoryDashboard)

- **Filter bar:** Pill buttons for All/Buy/Hold/Sell, total count
- **Table:** Each row shows: ticker (bold), recommendation badge, thesis summary (truncated), relative timestamp
- **Behavior:** Click row loads full analysis in the analysis view
- **Pagination:** Infinite scroll or load-more button
- **Calibration:** Accessible via a "Calibration" tab or toggle within this view (not a separate view)

#### Watchlist View (`WatchlistView.jsx` — rewrite of WatchlistPanel)

- **Watchlist tabs:** Switch between saved watchlists, "+ New" to create
- **Grid layout:** Responsive grid of mini thesis cards (3-4 per row)
- **Mini thesis card:** Ticker, price, daily change, recommendation badge, agent heatmap strip
- **Actions:** Click card → open full analysis. "Re-analyze All" button for batch refresh.

#### Portfolio View (`PortfolioView.jsx` — rewrite of PortfolioPanel)

- **Summary strip:** Total value, day P&L, risk score, sector concentration — all as large-font metrics
- **Holdings table:** Ticker, shares, market value, total return, latest recommendation badge
- **Click ticker** to jump to analysis view for that holding

#### Schedules View (`SchedulesView.jsx` — rewrite of SchedulePanel)

- **Card list:** Each schedule as a card showing name, tickers, frequency, active/paused status dot
- **Create/edit:** Inline form or modal for schedule management

#### Alerts View (`AlertsView.jsx` — rewrite of AlertPanel)

- **Two sections:** Active rules (top), Recent triggers (bottom)
- **Alert cards:** Severity-colored left border (red/amber), rule description, trigger timestamp
- **Create/edit:** Inline form or modal for alert rule management

## Styling System

### Design Tokens (carried over and refined)

```
Backgrounds:
  --bg-primary: #09090b (page)
  --bg-card: rgba(255,255,255,0.02) (cards)
  --bg-card-hover: rgba(255,255,255,0.04)
  --bg-elevated: rgba(255,255,255,0.04)

Accents:
  --accent-buy / --accent-bullish: #17c964
  --accent-sell / --accent-bearish: #f31260
  --accent-hold / --accent-neutral: #f5a524
  --accent-primary: #006fee

Text:
  --text-primary: rgba(255,255,255,0.9)
  --text-secondary: rgba(255,255,255,0.65)
  --text-muted: rgba(255,255,255,0.4)
  --text-dim: rgba(255,255,255,0.25)

Borders:
  --border-subtle: rgba(255,255,255,0.05)
  --border-default: rgba(255,255,255,0.08)

Typography:
  --font-sans: system-ui, -apple-system, sans-serif
  --font-mono: 'SF Mono', 'Fira Code', monospace (for numbers, tickers)

Spacing scale:
  4px, 8px, 12px, 16px, 20px, 24px, 32px (consistent across all components)

Border radius:
  --radius-sm: 4px (pills, badges)
  --radius-md: 8px (inner cards, inputs)
  --radius-lg: 10-12px (section cards)
  --radius-xl: 14px (thesis card)
```

### Consistent Patterns

- **Cards:** `bg-card border border-subtle rounded-lg p-5`
- **Badges:** `text-[0.68rem] px-2 py-0.5 rounded-sm font-medium` with sentiment-colored bg/text
- **Metrics:** Label in `text-dim text-[0.7rem]`, value in `text-secondary font-semibold tabular-nums`
- **Section headers:** 3px colored accent bar + name + badge, meta info right-aligned
- **Expand links:** Primary color at 70% opacity, hover to full
- **Agent heatmap:** Flex row of colored 4px-tall rounded bars, labeled beneath

## Data Mapping

### Thesis Card Data Sources

```
Left column:
  ticker          → analysis.ticker
  price           → agent_results.market.data.current_price
  daily_change    → agent_results.market.data.change_percent
  recommendation  → analysis.analysis.recommendation
  target_range    → analysis.analysis.price_target (or scenarios)
  agent_heatmap   → each agent_results[key].data.stance or .signal

Right column:
  thesis_text     → analysis.analysis.executive_summary (or synthesis)
  signals         → top 3 from analysis.analysis.key_factors or agent summaries
```

### Analysis Section Data Sources

Each section maps to `agent_results[agent_type]`:

| Section | Agent Key | Summary Field | Metrics |
|---------|-----------|---------------|---------|
| Fundamentals | `fundamentals` | `.data.analysis` or `.data.summary` | P/E, rev growth, margin, cash |
| Technical | `technical` | `.data.analysis` or `.data.summary` | RSI, MACD, support, resistance |
| Sentiment | `sentiment` | `.data.analysis` or `.data.summary` | Score, news tone, social, upgrades |
| Macro | `macro` | `.data.analysis` or `.data.summary` | Fed rate, CPI, GDP, 10Y yield |
| News | `news` | `.data.analysis` or `.data.summary` | Article list with sentiment |
| Options | `options` | `.data.analysis` or `.data.summary` | P/C ratio, max pain, IV |
| Leadership | `leadership` | `.data.analysis` | Four capitals scores |
| Council | `council` | separate endpoint: `POST/GET /api/analyze/{ticker}/council` (not in `agent_results`) | Investor perspectives, consensus |

Exact field paths will be confirmed during implementation by reading the actual API response shapes.

## Chart Enhancement — SMA Implementation

### Calculation

SMAs computed client-side from the OHLCV data already fetched by the market agent:

```
SMA(period) = average of closing prices over last `period` days
```

For each data point at index `i` where `i >= period - 1`:
```
sma[i] = sum(close[i-period+1] ... close[i]) / period
```

### Display

- Each SMA rendered as a `LineSeries` via lightweight-charts `addLineSeries()`
- Colors: SMA9 (#ef4444), SMA20 (#f59e0b), SMA50 (#22c55e), SMA100 (#3b82f6), SMA200 (#a855f7)
- Line width: 1px, with slight opacity reduction for longer periods
- Legend below chart with color swatches — clickable to toggle visibility
- Default: SMA50 and SMA200 visible, others hidden (user can toggle)

## Component File Plan

### New Files
- `components/ThesisCard.jsx` — V2 split verdict/evidence card
- `components/SectionNav.jsx` — sticky section jump navigation
- `components/AnalysisSection.jsx` — shared section template for all agents
- `components/SearchBar.jsx` — extracted from ContentHeader
- `components/MetaFooter.jsx` — analysis metadata + diagnostics link
- `components/HistoryView.jsx` — rewritten history browser
- `components/WatchlistView.jsx` — rewritten watchlist with mini thesis cards
- `components/PortfolioView.jsx` — rewritten portfolio with summary strip
- `components/SchedulesView.jsx` — rewritten schedule manager
- `components/AlertsView.jsx` — rewritten alert manager

### Modified Files
- `components/Dashboard.jsx` — new layout orchestration, remove tab system
- `components/Sidebar.jsx` — expand to 220px with labels and recent tickers
- `components/PriceChart.jsx` — add SMA overlays and legend
- `index.css` — refined design tokens, consistent spacing scale, remove unused styles

### Removed Files (functionality absorbed into new components)
- `components/ContentHeader.jsx` → split into SearchBar + ThesisCard
- `components/Recommendation.jsx` → replaced by ThesisCard
- `components/AnalysisTabs.jsx` → replaced by SectionNav
- `components/AgentPipelineBar.jsx` → agent dots moved into SearchBar
- `components/Summary.jsx` → content distributed across AnalysisSection instances
- `components/ScenarioPanel.jsx` → scenarios folded into relevant sections
- `components/MacroSnapshot.jsx` → absorbed into Macro AnalysisSection
- `components/CalibrationCard.jsx` → moved into diagnostics panel / history view
- `components/DiagnosticsPanel.jsx` → becomes a modal/slide-over from MetaFooter

### Unchanged (but restyled)
- `components/CouncilPanel.jsx` — content stays, but rendered within AnalysisSection wrapper
- `components/LeadershipPanel.jsx` — content stays, rendered within AnalysisSection wrapper
- `components/NewsFeed.jsx` — content stays, rendered within News AnalysisSection
- `components/OptionsFlow.jsx` — content stays, rendered within Options AnalysisSection
- `components/Icons.jsx` — unchanged

### Unchanged (infrastructure)
- `context/AnalysisContext.jsx` — no changes needed
- `hooks/useAnalysis.js` — no changes needed
- `hooks/useSSE.js` — no changes needed
- `hooks/useHistory.js` — no changes needed
- `utils/api.js` — no changes needed
- `App.jsx` — no changes needed
- `main.jsx` — no changes needed

## Scope Boundary

**In scope:**
- Complete visual redesign of all views
- New layout system (sidebar + scrollable narrative)
- New ThesisCard replacing recommendation gauge
- SMA overlays on price chart
- Sticky section navigation
- Expandable analysis sections
- Consistent design token system
- Responsive behavior (min-width ~1024px; no mobile target for now)

**Out of scope:**
- TypeScript migration (can do incrementally later)
- New API endpoints (frontend-only changes)
- Component library migration (keep custom Tailwind components)
- Mobile/responsive design below 1024px
- New features (no new data or functionality, just better presentation)
- Test suite (can add after redesign stabilizes)

## Mockups

Visual mockups from the brainstorming session are preserved in:
`.superpowers/brainstorm/35523-1775003251/content/`

Key files:
- `full-layout.html` — complete analysis view layout (approved)
- `thesis-card-hybrid.html` — thesis card variations (V2 selected)
- `section-design.html` — analysis section variations (V1 selected)
- `other-views.html` — history, watchlist, portfolio, schedules, alerts (approved)
- `recommendation-concepts.html` — initial recommendation explorations
- `mental-model.html` — layout mental model options (Hybrid selected)
