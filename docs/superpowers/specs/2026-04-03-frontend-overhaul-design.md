# Frontend Overhaul Design Spec

**Date:** 2026-04-03
**Status:** Approved
**Scope:** Complete frontend rebuild — new component library, routing, layout, color palette, and information architecture.

---

## Goals

1. Replace the current custom-built UI with shadcn/ui components on a proper design system
2. Introduce React Router for URL-based navigation (replacing viewMode state switching)
3. Reorganize the analysis view from a long scroll into KPI summary + tabbed sections
4. Apply a warm dark fintech terminal aesthetic inspired by the Buildly dashboard reference
5. Preserve the existing data layer (AnalysisContext, useAnalysis, useSSE, api.js)

## Non-Goals

- Backend changes — API endpoints, agent logic, and data models are untouched
- Adding new features — this is a visual/structural overhaul of existing functionality
- Mobile-first responsive design — desktop-first dashboard, basic tablet support

---

## Stack Changes

| Layer | Current | New |
|-------|---------|-----|
| Components | Custom divs + inline styles | shadcn/ui (Card, Table, Tabs, Dialog, Badge, Tooltip, Select, DropdownMenu) |
| Routing | `viewMode` state in Dashboard.jsx | React Router v6 (`Routes`, `Route`, `useNavigate`) |
| Styling | Tailwind + glass-card CSS classes | Tailwind + shadcn CSS variables + design tokens |
| Typography | Default + JetBrains Mono | Inter (UI) + Fira Code (data/numbers) |
| Charts | Lightweight Charts v5 | Lightweight Charts v5 (unchanged) |
| Animation | Framer Motion v12 | Framer Motion v12 (unchanged) |
| HTTP | Axios + useSSE | Axios + useSSE (unchanged) |

### New Dependencies

- `@radix-ui/*` — headless primitives (via shadcn)
- `react-router-dom` — client-side routing
- `class-variance-authority` — component variants (shadcn dependency)
- `clsx` + `tailwind-merge` — className composition (shadcn dependency)
- `lucide-react` — SVG icon library (replaces custom inline SVGs)

### Removed

- All custom glass-card CSS classes
- Custom modal/dialog implementations
- Custom tab/section-nav implementations
- Custom badge/tooltip implementations
- `SectionNav.jsx` (replaced by shadcn Tabs)

---

## Layout Structure

```
┌──────────────────────────────────────────────────────────────┐
│  [Logo]        [ Search ticker...              ]   [🔔] [⚙] │  ← Header (h-14, fixed top)
├──────────┬───────────────────────────────────────────────────┤
│          │                                                   │
│  RESEARCH│  Main content area                                │
│  Analysis│  (scrolls independently)                          │
│  Macro   │                                                   │
│          │                                                   │
│  TOOLS   │                                                   │
│  Watchlst│                                                   │
│  Holdings│                                                   │
│  Schedule│                                                   │
│  Alerts  │                                                   │
│          │                                                   │
│  HISTORY │                                                   │
│  History │                                                   │
│  Inflctns│                                                   │
│          │                                                   │
│  ──────  │                                                   │
│  Recent: │                                                   │
│  AAPL 🟢 │                                                   │
│  TSLA 🔴 │                                                   │
│  MSFT 🟢 │                                                   │
├──────────┴───────────────────────────────────────────────────┤
```

### Header

- Fixed top, full viewport width, 56px tall
- Background: `--header-bg` (#0d0d0d) with bottom border
- Left: App logo/name
- Center: Ticker search input (max-width ~480px). Shows agent progress dots during analysis.
- Right: Notification bell (alert count badge), settings gear icon

### Sidebar

- Fixed left, 220px wide, below header (top: 56px)
- Background: `--sidebar-bg` (#0d0d0d) with right border
- Three nav groups with section labels: RESEARCH, TOOLS, HISTORY
- Each nav item: icon (Lucide) + text label, 44px tall touch target
- Active state: amber accent left bar indicator + tinted background
- Bottom section: "Recent Analyses" — last 5 tickers with recommendation color dot
- Clicking a recent ticker navigates to `/analysis/:ticker` and loads cached or re-runs

### Main Content

- Fills remaining viewport (left: 220px, top: 56px)
- Independent scroll
- Content padding: 24px
- Max content width: none (fills available space for data density)

---

## Color Palette — Warm Dark

### Core Tokens

| Token | Value | Usage |
|-------|-------|-------|
| `--background` | `#0a0a0a` | Page background |
| `--card` | `#141414` | Card surfaces |
| `--card-foreground` | `rgba(255,255,255,0.92)` | Text on cards |
| `--card-hover` | `#1a1a1a` | Card hover state |
| `--popover` | `#181818` | Dropdowns, tooltips |
| `--popover-foreground` | `rgba(255,255,255,0.92)` | Text in popovers |
| `--primary` | `#e8860c` | Primary accent (warm amber) |
| `--primary-foreground` | `#000000` | Text on primary |
| `--secondary` | `#1f1f1f` | Secondary surfaces |
| `--secondary-foreground` | `rgba(255,255,255,0.8)` | Text on secondary |
| `--muted` | `#1a1a1a` | Muted backgrounds |
| `--muted-foreground` | `rgba(255,255,255,0.4)` | Muted text |
| `--accent` | `#e8860c` | Accent (same as primary) |
| `--accent-foreground` | `#000000` | Text on accent |
| `--destructive` | `#f31260` | Destructive actions / bearish |
| `--border` | `rgba(255,255,255,0.06)` | Default borders |
| `--input` | `rgba(255,255,255,0.08)` | Input borders |
| `--ring` | `#e8860c` | Focus rings |
| `--radius` | `8px` | Default border radius |

### Semantic Tokens

| Token | Value | Usage |
|-------|-------|-------|
| `--success` | `#17c964` | Bullish / positive / buy |
| `--danger` | `#f31260` | Bearish / negative / sell |
| `--warning` | `#f5a524` | Neutral / hold / caution |
| `--info` | `#338ef7` | Informational highlights |

### Sidebar & Header

| Token | Value |
|-------|-------|
| `--sidebar-bg` | `#0d0d0d` |
| `--header-bg` | `#0d0d0d` |
| `--sidebar-active-bg` | `rgba(232,134,12,0.08)` |
| `--sidebar-active-border` | `rgba(232,134,12,0.4)` |

### Chart Colors

| Token | Value | Usage |
|-------|-------|-------|
| `--chart-1` | `#e8860c` | Primary series |
| `--chart-2` | `#338ef7` | Secondary series |
| `--chart-3` | `#17c964` | Tertiary series |
| `--chart-4` | `#f5a524` | Quaternary series |
| `--chart-5` | `#a855f7` | Quinary series |
| `--sma-9` | `#ef4444` | SMA 9 |
| `--sma-20` | `#f59e0b` | SMA 20 |
| `--sma-50` | `#22c55e` | SMA 50 |
| `--sma-100` | `#3b82f6` | SMA 100 |
| `--sma-200` | `#a855f7` | SMA 200 |

---

## Typography

### Font Stack

- **UI text**: Inter (headings, labels, body text, navigation)
- **Data values**: Fira Code (prices, percentages, scores, numeric metrics)

### Type Scale

| Role | Size | Weight | Font |
|------|------|--------|------|
| Page heading | 24px | 600 | Inter |
| Section heading | 18px | 600 | Inter |
| Card title | 16px | 500 | Inter |
| Body | 14px | 400 | Inter |
| Label / caption | 12px | 500 | Inter |
| KPI value | 28px | 600 | Fira Code |
| Data value | 14px | 400 | Fira Code |
| Small data | 12px | 400 | Fira Code |

### Loading

```css
@import url('https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;600&family=Inter:wght@300;400;500;600;700&display=swap');
```

---

## Routing

### Route Map

| Path | Component | Description |
|------|-----------|-------------|
| `/` | `AnalysisView` | Default — shows welcome/empty state or last analysis |
| `/analysis/:ticker` | `AnalysisView` | Stock analysis with KPI row + tabs |
| `/macro` | `MacroPage` | Macroeconomic environment |
| `/watchlist` | `WatchlistView` | Saved watchlists |
| `/portfolio` | `PortfolioView` | Portfolio holdings |
| `/schedules` | `SchedulesView` | Recurring analysis schedules |
| `/alerts` | `AlertsView` | Alert rules & notifications |
| `/history` | `HistoryView` | Past analysis history |
| `/inflections` | `InflectionView` | Inflection tracking |

### Behavior

- Sidebar nav items are `NavLink` components with active class styling
- Analyzing a ticker navigates to `/analysis/:ticker`
- Recent analyses in sidebar link to `/analysis/:ticker`
- Browser back/forward works naturally
- Deep linking supported — sharing `/analysis/AAPL` loads that analysis

---

## Analysis View — KPI Row + Tabs

### KPI Summary Row

Five stat cards displayed in a horizontal row at the top of the analysis view. Each card uses the shadcn `Card` component.

| Card | Icon | Value Source | Trend |
|------|------|-------------|-------|
| Price | DollarSign | `analysis.analysis.market.current_price` | % change, green/red arrow |
| Rating | Target | `analysis.recommendation` | Color-coded badge (BUY/SELL/HOLD) |
| Confidence | Gauge | `analysis.confidence_score` | vs. previous, % delta |
| Sentiment | TrendingUp | `analysis.analysis.sentiment.overall_score` | Labeled (Bullish/Bearish/Neutral) |
| P/E Ratio | BarChart3 | `analysis.analysis.fundamentals.pe_ratio` | vs. previous |

**Card layout:**
```
┌─────────────────────────┐
│  [icon]          ↗ +2.3%│  ← trend indicator (top-right)
│                         │
│  Price                  │  ← label (text-muted, 12px Inter)
│  $182.40                │  ← value (28px Fira Code, text-primary)
│  Prev: $178.30          │  ← comparison (12px, text-muted)
└─────────────────────────┘
```

- Icon: 20px Lucide icon in a 36px rounded container with `--primary` tinted background (rgba)
- Trend arrow: green up-arrow for positive, red down-arrow for negative
- Background: `--card`
- Border: `--border`, subtle

### Tab Bar

Rendered using shadcn `Tabs` component directly below the KPI row.

**Tabs:**

| Tab | Label | Sections Included |
|-----|-------|-------------------|
| `overview` | Overview | CompanyOverview, key fundamentals table, EarningsPanel, PriceChart |
| `thesis` | Thesis & Risk | ThesisPanel, NarrativePanel, RiskDiffPanel, EarningsReviewPanel |
| `technicals` | Technicals | TechnicalsOptionsSection (technical indicators, options flow, detailed chart) |
| `sentiment` | Sentiment | SentimentPanel (5-factor breakdown), NewsFeed, MacroIndicators (inline summary) |
| `council` | Council | CouncilPanel, council synthesis |

- Default active tab: `overview`
- Tab indicator: amber underline (2px, `--primary`)
- Tab text: `--muted-foreground` default, `--card-foreground` when active
- Tab content animates in with a subtle fade (Framer Motion, 150ms)

### Empty / Welcome State

When no analysis has been run:
- Large centered message: "Enter a ticker above to start analysis"
- Subtle icon or illustration
- Optional: show recent analyses as clickable cards

### Loading State

During analysis:
- KPI row shows skeleton placeholders (shimmer animation)
- Tab content shows skeleton cards
- Search bar in header shows progress indicator (agent stage + progress %)

---

## Component Architecture

### New Components

| Component | Purpose |
|-----------|---------|
| `AppLayout.jsx` | Root layout — header + sidebar + `<Outlet />` |
| `Header.jsx` | Global header with search, notifications, settings |
| `Sidebar.jsx` | Navigation sidebar (rebuilt with shadcn + NavLink) |
| `KpiRow.jsx` | Five stat cards for analysis summary |
| `KpiCard.jsx` | Individual stat card |
| `AnalysisView.jsx` | KPI row + tabbed analysis content |
| `AnalysisTabs.jsx` | Tab container managing the 5 tabs |
| `OverviewTab.jsx` | Overview tab content |
| `ThesisRiskTab.jsx` | Thesis & Risk tab content |
| `TechnicalsTab.jsx` | Technicals tab content |
| `SentimentTab.jsx` | Sentiment tab content |
| `CouncilTab.jsx` | Council tab content |

### Migrated Components (restyle, keep logic)

| Component | Changes |
|-----------|---------|
| `CompanyOverview.jsx` | Restyle with shadcn Card, Inter/Fira Code typography |
| `ThesisPanel.jsx` | Restyle cards, keep bull/bear debate structure |
| `NarrativePanel.jsx` | Restyle with new card treatment |
| `RiskDiffPanel.jsx` | Restyle, use shadcn Table for risk items |
| `EarningsReviewPanel.jsx` | Restyle with new badges and cards |
| `EarningsPanel.jsx` | Restyle dates display |
| `PriceChart.jsx` | Keep Lightweight Charts, update container styling and chart theme colors |
| `TechnicalsOptionsSection.jsx` | Restyle indicators and options flow |
| `NewsFeed.jsx` | Restyle article cards |
| `OptionsFlow.jsx` | Restyle with shadcn Card/Badge |
| `LeadershipPanel.jsx` | Restyle executive cards |
| `CouncilPanel.jsx` | Restyle persona cards |
| `MacroPage.jsx` | Restyle with new card system |
| `HistoryView.jsx` | Use shadcn Table |
| `WatchlistView.jsx` | Use shadcn Card + Table |
| `PortfolioView.jsx` | Use shadcn Table + Card |
| `SchedulesView.jsx` | Use shadcn Table + Dialog |
| `AlertsView.jsx` | Use shadcn Table + Badge |
| `InflectionView.jsx` | Restyle heatmap and feed |
| `InflectionChart.jsx` | Update chart theme colors |
| `InflectionHeatmap.jsx` | Restyle with new color tokens |
| `MetaFooter.jsx` | Restyle metadata display |

### Removed Components

| Component | Reason |
|-----------|--------|
| `SectionNav.jsx` | Replaced by shadcn Tabs in AnalysisTabs |
| `SearchBar.jsx` | Merged into Header.jsx |
| `ThesisCard.jsx` | Functionality absorbed into KpiRow + AnalysisView |
| `AnalysisSection.jsx` | Replaced by direct Card usage in each tab |

### Utility Setup (shadcn standard)

```
frontend/src/
├── lib/
│   └── utils.js          # cn() helper (clsx + tailwind-merge)
├── components/
│   └── ui/               # shadcn primitives (card, tabs, table, badge, etc.)
```

---

## Data Layer Changes

### AnalysisContext

No structural changes. The context continues to provide:
- `currentTicker`, `analysis`, `loading`, `error`, `progress`, `stage`

### useAnalysis Hook

Minor change: after `onResult`, call `navigate(`/analysis/${ticker}`)` to update the URL.

### api.js

No changes.

### useSSE Hook

No changes.

---

## Card Design Language

All cards follow a consistent treatment:

```css
/* Base card */
background: var(--card);          /* #141414 */
border: 1px solid var(--border);  /* rgba(255,255,255,0.06) */
border-radius: var(--radius);     /* 8px */
padding: 20px;

/* Hover (interactive cards only) */
background: var(--card-hover);    /* #1a1a1a */
border-color: var(--input);       /* rgba(255,255,255,0.08) */
transition: background 200ms, border-color 200ms;
```

No glass morphism, no backdrop-filter blur. Clean, solid dark cards with subtle borders — matching the Buildly aesthetic.

---

## Animations

Keep Framer Motion for:
- Tab content transitions (fade, 150ms)
- KPI card entrance (stagger, 50ms per card, fade + translateY)
- Page view transitions (fade, 200ms)
- Loading skeleton shimmer (CSS keyframe, keep existing)

Remove:
- Glass morphism blur transitions
- Scale-on-hover for sidebar items (keep subtle opacity change instead)
- Excessive slide animations

---

## Shadows

Minimal shadow usage — the dark background provides natural contrast:

| Level | Shadow | Usage |
|-------|--------|-------|
| None | `none` | Most cards (border provides edge) |
| Subtle | `0 1px 2px rgba(0,0,0,0.3)` | Elevated cards (popovers, dropdowns) |
| Elevated | `0 4px 12px rgba(0,0,0,0.5)` | Modals, dialogs |

---

## File Structure (Final)

```
frontend/src/
├── main.jsx                    # React entry, BrowserRouter wrap
├── App.jsx                     # Routes definition
├── index.css                   # Design tokens, global styles
├── lib/
│   └── utils.js                # cn() helper
├── components/
│   ├── ui/                     # shadcn primitives
│   │   ├── card.jsx
│   │   ├── tabs.jsx
│   │   ├── table.jsx
│   │   ├── badge.jsx
│   │   ├── button.jsx
│   │   ├── dialog.jsx
│   │   ├── dropdown-menu.jsx
│   │   ├── input.jsx
│   │   ├── select.jsx
│   │   ├── tooltip.jsx
│   │   └── skeleton.jsx
│   ├── layout/
│   │   ├── AppLayout.jsx       # Header + Sidebar + Outlet
│   │   ├── Header.jsx          # Global header with search
│   │   └── Sidebar.jsx         # Navigation sidebar
│   ├── analysis/
│   │   ├── AnalysisView.jsx    # KPI row + tabs container
│   │   ├── AnalysisTabs.jsx    # Tab definitions + content routing
│   │   ├── KpiRow.jsx          # Five stat cards
│   │   ├── KpiCard.jsx         # Individual stat card
│   │   ├── OverviewTab.jsx
│   │   ├── ThesisRiskTab.jsx
│   │   ├── TechnicalsTab.jsx
│   │   ├── SentimentTab.jsx
│   │   └── CouncilTab.jsx
│   ├── panels/                 # Migrated content panels
│   │   ├── CompanyOverview.jsx
│   │   ├── ThesisPanel.jsx
│   │   ├── NarrativePanel.jsx
│   │   ├── RiskDiffPanel.jsx
│   │   ├── EarningsReviewPanel.jsx
│   │   ├── EarningsPanel.jsx
│   │   ├── PriceChart.jsx
│   │   ├── TechnicalsOptionsSection.jsx
│   │   ├── SentimentPanel.jsx  # Extracted from inline rendering
│   │   ├── NewsFeed.jsx
│   │   ├── OptionsFlow.jsx
│   │   ├── LeadershipPanel.jsx
│   │   ├── CouncilPanel.jsx
│   │   └── MetaFooter.jsx
│   └── views/                  # Full-page views
│       ├── MacroPage.jsx
│       ├── HistoryView.jsx
│       ├── WatchlistView.jsx
│       ├── PortfolioView.jsx
│       ├── SchedulesView.jsx
│       ├── AlertsView.jsx
│       ├── InflectionView.jsx
│       ├── InflectionChart.jsx
│       ├── InflectionHeatmap.jsx
│       └── InflectionFeed.jsx
├── context/
│   └── AnalysisContext.jsx     # Unchanged
├── hooks/
│   ├── useAnalysis.js          # Minor: add navigate() after result
│   ├── useSSE.js               # Unchanged
│   └── useHistory.js           # Unchanged
├── utils/
│   └── api.js                  # Unchanged
└── assets/
```

---

## Migration Strategy

1. **Foundation first**: Install dependencies, set up shadcn, create design tokens, build AppLayout/Header/Sidebar
2. **Routing**: Replace viewMode with React Router, wire all routes
3. **Analysis view**: Build KpiRow + AnalysisTabs, migrate panels into tabs
4. **Panel migration**: Restyle each panel one at a time with new design tokens
5. **Secondary views**: Restyle Watchlist, Portfolio, History, etc.
6. **Polish**: Animations, loading states, empty states, edge cases

Each step should produce a working app — no big-bang rewrite.
