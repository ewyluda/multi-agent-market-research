# Frontend Redesign Design

## Overview

Full visual and structural overhaul of the trading analyst frontend. Moves from horizontal top nav + 3-column grid to a vertical icon sidebar + tabbed content area + right sidebar layout inspired by fiscal.ai, while keeping the dark trading terminal aesthetic.

## Navigation: Vertical Icon Sidebar

Fixed-width left sidebar (~64px) replaces horizontal nav tabs:
- Icon rail with tooltip labels: Analysis, History, Watchlist, Schedules, Alerts
- Brand mark at top (logo icon only)
- Active state: accent-blue background pill
- Subtle border-right, elevated background (#0a0a0b)
- Ticker search moves to main content header

## Main Content Header

Compact header strip above content:
- Left: ticker symbol (large, bold) + price + change % + source badges
- Right: "Run Analysis" button + notification bell
- Thin progress bar during analysis
- Agent pipeline becomes compact horizontal status strip (8 icons in a row with check/spinner/pending)

## Analysis View: Tabbed Content

Horizontal tabs within center content area:

### Tab: Overview (default)
- Price chart (full width, ~400px height)
- 4 technical indicator cards (RSI, MACD, Bollinger, Signal)
- Verdict banner + At-a-Glance metrics

### Tab: Research
- Chain-of-thought analysis sections (expandable)
- Price targets range bar + entry/target/stop cards
- Risks & Opportunities side by side

### Tab: Sentiment
- Sentiment arc gauge + reasoning + key themes + factor breakdown
- Social Buzz (Twitter) panel

### Tab: News
- Full news feed with refined article cards

### Tab: Options
- Options flow data (P/C ratios, unusual activity, high IV)

## Right Sidebar (~280px)
- Recommendation gauge (refined SVG + animations)
- Agent consensus signals
- Macro snapshot (compact indicators)

## Welcome Screen
- Large centered ticker search input (hero element)
- Subtle grid/gradient background pattern
- Quick-start tickers as larger pill buttons
- Feature cards with refined visual treatment
- Staggered reveal animations

## Visual Refinements
- Typography: Inter (body) + JetBrains Mono (numbers) — unchanged
- Palette: Refined zinc/black base + blue/green/red accents with more depth layers
- Cards: More depth variation, distinct background levels
- Borders: Subtler base (rgba 0.04), brighter hover
- Animations: Smoother tab transitions, spring physics on gauges
- Data density: More visible without scrolling on Overview tab

## Agent Pipeline (During Analysis)
- Horizontal compact bar between header and content
- 8 agent icons in row with labels, status indicators
- Collapses after analysis completes, expandable via button
- Duration on hover, total time at end

## Files Affected
- `Dashboard.jsx` — major restructure (sidebar nav, tabbed layout, header)
- `AgentStatus.jsx` — rewrite as horizontal compact bar
- `PriceChart.jsx` — visual refinements
- `Summary.jsx` — split into Overview tab and Research tab content
- `SentimentReport.jsx` — move to Sentiment tab
- `NewsFeed.jsx` — move to News tab
- `OptionsFlow.jsx` — move to Options tab
- `SocialBuzz.jsx` — move to Sentiment tab
- `Recommendation.jsx` — visual refinements
- `MacroSnapshot.jsx` — visual refinements
- `index.css` — updated theme variables, new animations
- `index.html` — no font changes needed
- `tailwind.config.js` — potential new color tokens
