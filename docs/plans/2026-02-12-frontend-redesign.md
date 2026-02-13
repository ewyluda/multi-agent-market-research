# Frontend Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Overhaul the frontend from horizontal-nav 3-column grid to vertical icon sidebar + tabbed content area + right sidebar, with significant visual polish.

**Architecture:** Replace Dashboard.jsx's horizontal nav with a fixed 64px icon sidebar. Convert the analysis view from a single vertical scroll to a tabbed interface (Overview, Research, Sentiment, News, Options). AgentStatus becomes a compact horizontal bar instead of a full sidebar column. Right sidebar (Recommendation + Macro) stays.

**Tech Stack:** React 19, Tailwind CSS v4, framer-motion, lightweight-charts

**Note:** This is a frontend-only visual overhaul. No backend changes. No frontend test suite exists — verification is `npm run build` + visual inspection. The hooks (`useAnalysis.js`, `useSSE.js`), context (`AnalysisContext.jsx`), and utils (`api.js`) remain unchanged.

---

### Task 1: Update CSS Theme & Add New Animations

**Files:**
- Modify: `frontend/src/index.css`
- Modify: `frontend/tailwind.config.js`

**Step 1: Update index.css with new theme tokens and animations**

Add sidebar-specific CSS variables, tab transition animations, and new utility classes. Key additions:
- `--bg-sidebar: #0a0a0b` (darker than main bg)
- `--bg-sidebar-active: rgba(0, 111, 238, 0.12)` (active nav item)
- `--sidebar-width: 64px` (collapsed sidebar)
- New keyframes: `slideInUp`, `tabFadeIn`, `scaleIn`
- `.sidebar-nav-item` base styles
- `.tab-content` transition styles
- Refine existing glass-card borders from `0.06` to `0.04` opacity

**Step 2: Update tailwind.config.js with new color tokens**

Add:
- `'dark-sidebar': '#0a0a0b'`
- `'dark-sidebar-active': 'rgba(0, 111, 238, 0.12)'`
- `'dark-sidebar-border': 'rgba(255, 255, 255, 0.04)'`

**Step 3: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no errors

**Step 4: Commit**

```
feat(frontend): update theme tokens and animations for redesign
```

---

### Task 2: Create Sidebar Navigation Component

**Files:**
- Create: `frontend/src/components/Sidebar.jsx`

**Step 1: Build the Sidebar component**

A 64px-wide fixed left sidebar with:
- Brand icon at top (PulseIcon in a gradient pill)
- 5 nav items: Analysis (PulseIcon), History (HistoryIcon), Watchlist (ChartBarIcon), Schedules (ClockIcon), Alerts (BellIcon with unacknowledged count badge)
- Each item: icon + tooltip on hover (using CSS `group` and a positioned span)
- Active state: blue pill background + white icon
- Inactive: gray-500 icon, hover transitions to white
- Fixed position, full viewport height
- Background: `var(--bg-sidebar)`, right border: `rgba(255,255,255,0.04)`

Props: `{ activeView, onViewChange, unacknowledgedCount }`

**Step 2: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds (component not yet wired in)

**Step 3: Commit**

```
feat(frontend): create vertical Sidebar navigation component
```

---

### Task 3: Create Analysis Tabs Component

**Files:**
- Create: `frontend/src/components/AnalysisTabs.jsx`

**Step 1: Build the AnalysisTabs component**

A horizontal tab bar for the analysis content area with 5 tabs:
- Overview, Research, Sentiment, News, Options
- Each tab: text label, optional icon, active underline indicator
- Active tab has `border-b-2 border-accent-blue text-white`
- Inactive: `text-gray-500 hover:text-gray-300`
- Smooth underline transition using framer-motion `layoutId`
- Tab bar has bottom border `border-white/5`

Props: `{ activeTab, onTabChange, analysis }` (analysis used to show/hide Options tab if no options data)

**Step 2: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds

**Step 3: Commit**

```
feat(frontend): create AnalysisTabs horizontal tab bar component
```

---

### Task 4: Create Compact Agent Pipeline Bar

**Files:**
- Create: `frontend/src/components/AgentPipelineBar.jsx`

**Step 1: Build the AgentPipelineBar component**

Replaces the full-sidebar AgentStatus with a compact horizontal bar:
- Single row of 8 agent items (market, fundamentals, news, technical, options, macro, sentiment, synthesis)
- Each item: small icon (16px) + 3-letter label below + status indicator
- Status indicators: gray dot (pending), blue pulse (running), green check (success), red x (error)
- Duration appears as tooltip on hover
- Right side: total completion time when done
- Collapsible: after analysis completes, can toggle visibility via a small "Pipeline ▾" button
- Uses same `useAnalysisContext` logic as current AgentStatus for status derivation
- Framer-motion stagger animation on initial appear

Props: none (reads from context)

**Step 2: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds

**Step 3: Commit**

```
feat(frontend): create compact horizontal AgentPipelineBar
```

---

### Task 5: Create ContentHeader Component

**Files:**
- Create: `frontend/src/components/ContentHeader.jsx`

**Step 1: Build the ContentHeader component**

The header strip above the tabbed content area:
- Left side: ticker symbol (text-2xl bold) + current price (text-3xl mono) + change % badge (green/red) + data source badges (AV/YF)
- Right side: ticker search input + "Run Analysis" button + notification bell button
- Below (conditional): thin progress bar during analysis (same gradient as current)
- Below progress: AgentPipelineBar (only visible during/after analysis)
- Search input: dark inset bg, mono font, uppercase, 5-char max
- Run Analysis button: gradient blue, disabled state, loading spinner

Props: `{ tickerInput, setTickerInput, onAnalyze, loading, onAlertClick, unacknowledgedCount, analysis }`

**Step 2: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds

**Step 3: Commit**

```
feat(frontend): create ContentHeader with search, progress, and pipeline
```

---

### Task 6: Rewrite Dashboard.jsx — Layout Structure

**Files:**
- Modify: `frontend/src/components/Dashboard.jsx`

**Step 1: Rewrite Dashboard with new layout**

Major restructure:
- Root layout: `flex` with Sidebar on left (64px fixed) + main content area (flex-1)
- Main content area: ContentHeader at top + view-specific content below
- Analysis view: AnalysisTabs + tab content panels + right sidebar (280px)
- Tab content rendered conditionally based on `activeTab` state
- New state: `activeTab` (overview/research/sentiment/news/options)
- View modes stay the same (ANALYSIS, HISTORY, WATCHLIST, SCHEDULES, ALERTS)
- Welcome screen: rendered when no analysis and not loading, in analysis view
- Remove all old header JSX, old nav tab JSX, old 3-column grid

Tab content mapping:
- **Overview**: PriceChart + (Summary's VerdictBanner + AtAGlance)
- **Research**: Summary's chain-of-thought sections + price targets + risks/opportunities
- **Sentiment**: SentimentReport + SocialBuzz
- **News**: NewsFeed
- **Options**: OptionsFlow

Right sidebar (always visible in analysis view): Recommendation + MacroSnapshot

**Step 2: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds

**Step 3: Commit**

```
feat(frontend): rewrite Dashboard with sidebar nav and tabbed layout
```

---

### Task 7: Refactor Summary.jsx — Split Overview vs Research

**Files:**
- Modify: `frontend/src/components/Summary.jsx`

**Step 1: Export sub-components for tab-based rendering**

Currently Summary renders everything (verdict + at-a-glance + chain-of-thought + price targets + risks/opps) as one block. Refactor to export individual pieces:

- Export `VerdictBanner` (already defined, just export it)
- Export `AtAGlance` (already defined, just export it)
- Create `ResearchContent` — wraps chain-of-thought sections + price targets + risks/opps + PDF export button
- Keep `Summary` as default export for backward compat but it now renders nothing (or a simple wrapper)
- `OverviewMetrics` — new component: VerdictBanner + AtAGlance together for the Overview tab

All internal sub-components (AnalysisSection, PriceTargetsRangeBar, parseReasoning, SECTION_META) stay in the same file.

**Step 2: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds

**Step 3: Commit**

```
refactor(frontend): export Summary sub-components for tabbed layout
```

---

### Task 8: Polish PriceChart.jsx

**Files:**
- Modify: `frontend/src/components/PriceChart.jsx`

**Step 1: Visual refinements to PriceChart**

- Increase chart height from 360 to 400px
- Remove the header section (ticker name, price, change %) — that's now in ContentHeader
- Keep: chart container + 4 technical indicator cards below
- Refine indicator card borders: add subtle `border border-white/[0.04]`
- Add hover states to indicator cards: `hover:border-white/[0.08]` transition
- Clean up the "Chart data unavailable" empty state with a more refined icon

**Step 2: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds

**Step 3: Commit**

```
style(frontend): polish PriceChart visuals and increase chart height
```

---

### Task 9: Polish Recommendation.jsx

**Files:**
- Modify: `frontend/src/components/Recommendation.jsx`

**Step 1: Refine Recommendation gauge and card**

- Remove the `border-t-2` colored top border (feels heavy) — replace with a subtle colored left glow line
- Refine gauge SVG: slightly larger arc radius, smoother gradients
- Add subtle animated glow ring around the center needle dot
- Improve the confidence bar: make it 2px tall, add a faint glow matching the recommendation color
- Agent consensus section: tighten spacing, make the rows slightly more compact

**Step 2: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds

**Step 3: Commit**

```
style(frontend): polish Recommendation gauge and card design
```

---

### Task 10: Polish SentimentReport.jsx

**Files:**
- Modify: `frontend/src/components/SentimentReport.jsx`

**Step 1: Visual refinements**

- Factor breakdown: default to expanded (remove collapsed state, it's now on its own tab with room)
- Tighten the arc gauge: use a bit more whitespace around it
- Factor bars: add subtle rounded ends, slightly taller (2px instead of 1.5px)
- Key themes tags: add subtle hover state

**Step 2: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds

**Step 3: Commit**

```
style(frontend): polish SentimentReport factor bars and gauge
```

---

### Task 11: Polish NewsFeed.jsx, OptionsFlow.jsx, SocialBuzz.jsx

**Files:**
- Modify: `frontend/src/components/NewsFeed.jsx`
- Modify: `frontend/src/components/OptionsFlow.jsx`
- Modify: `frontend/src/components/SocialBuzz.jsx`

**Step 1: NewsFeed refinements**

- Remove max-height scroll constraint (full tab height now)
- Refine article cards: add subtle hover elevation effect
- Source badge: slightly larger, rounded-full instead of rounded

**Step 2: OptionsFlow refinements**

- Remove outer `glass-card-elevated` wrapper (now in a tab, not a standalone card)
- Add subtle divider lines between sections

**Step 3: SocialBuzz refinements**

- Top tweets default expanded (on its own tab now)
- Remove outer card wrapper for tab context

**Step 4: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds

**Step 5: Commit**

```
style(frontend): polish NewsFeed, OptionsFlow, and SocialBuzz for tabbed layout
```

---

### Task 12: Redesign Welcome Screen

**Files:**
- Modify: `frontend/src/components/Dashboard.jsx` (welcome section within the analysis view)

**Step 1: Redesign the welcome/landing screen**

New welcome screen in the analysis view (when no analysis loaded):
- Full content area (no right sidebar)
- Centered layout with generous vertical spacing
- Large hero search input: 480px wide, taller (py-4), with a subtle blue glow on focus
- Brand text: "AI Trading Analyst" as text-5xl bold with gradient text effect
- Subtitle: "Multi-agent research platform" in gray-400
- Quick-start tickers: larger pill buttons (px-5 py-2), arranged in a centered row
- Feature cards: 3 cards in a row, each with icon + title + description
- Subtle background: CSS grid pattern or dot matrix using `radial-gradient` in a pseudo-element
- Staggered framer-motion entrance: container → title → search → tickers → cards

**Step 2: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds

**Step 3: Commit**

```
feat(frontend): redesign welcome screen with hero search and grid background
```

---

### Task 13: Polish MacroSnapshot.jsx

**Files:**
- Modify: `frontend/src/components/MacroSnapshot.jsx`

**Step 1: Visual refinements**

- Refine yield curve visualization: taller bars, subtle gradient fills
- Tighten spacing between indicator rows
- Add subtle divider between indicator groups

**Step 2: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds

**Step 3: Commit**

```
style(frontend): polish MacroSnapshot yield curve and spacing
```

---

### Task 14: Final Integration Test & Visual QA

**Files:**
- All modified files

**Step 1: Full build verification**

Run: `cd frontend && npm run build`
Expected: Build succeeds with zero errors and zero warnings

**Step 2: Run backend test suite to confirm no regression**

Run: `cd /Users/ericwyluda/Development/projects/multi-agent-market-research && python -m pytest tests/ -v`
Expected: All 157 tests pass (frontend changes should not affect backend)

**Step 3: Commit any final adjustments**

```
chore(frontend): final QA pass and cleanup
```

---

## Task Dependency Graph

```
Task 1 (CSS/Theme)
  └─→ Task 2 (Sidebar) ─────────────┐
  └─→ Task 3 (AnalysisTabs) ────────┤
  └─→ Task 4 (AgentPipelineBar) ────┤
  └─→ Task 5 (ContentHeader) ───────┤
                                     ├─→ Task 6 (Dashboard rewrite)
  Task 7 (Summary refactor) ────────┤
                                     ├─→ Task 8-13 (Polish, parallel)
                                     └─→ Task 12 (Welcome screen)
                                          └─→ Task 14 (Final QA)
```

Tasks 2-5 + 7 can be built in parallel (independent new components). Task 6 wires them together. Tasks 8-13 are polish passes that can run in parallel after Task 6. Task 14 is final.
