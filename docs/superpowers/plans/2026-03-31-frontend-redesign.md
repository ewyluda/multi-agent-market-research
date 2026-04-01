# Frontend Redesign — Narrative-First Hybrid Layout

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the tab-fragmented analysis UI with a scrollable narrative layout featuring a V2 split thesis card, SMA-enhanced chart, expandable analysis sections, and consistent restyling of all views.

**Architecture:** Incremental refactor of existing React + Vite + Tailwind v4 stack. No framework migration. New components replace old ones; infrastructure (context, hooks, API layer) stays unchanged. Dashboard becomes the layout orchestrator for a sidebar + scrollable main content pattern.

**Tech Stack:** React 19, Vite 7, Tailwind CSS v4 (PostCSS, @theme directives), framer-motion 12, lightweight-charts 5, axios

**Spec:** `docs/superpowers/specs/2026-03-31-frontend-redesign.md`

**Mockups:** `.superpowers/brainstorm/35523-1775003251/content/full-layout.html` (approved layout)

---

## File Map

### New Files (10)
| File | Responsibility |
|------|---------------|
| `frontend/src/components/SearchBar.jsx` | Sticky top bar: ticker input, analyze button, agent progress dots |
| `frontend/src/components/ThesisCard.jsx` | V2 split card: verdict/target/heatmap left, thesis/signals right |
| `frontend/src/components/AnalysisSection.jsx` | Shared template for each agent's expandable section |
| `frontend/src/components/SectionNav.jsx` | Sticky pill nav for scrolling between agent sections |
| `frontend/src/components/MetaFooter.jsx` | Analysis timestamp, duration, agent count, diagnostics slide-over |
| `frontend/src/components/HistoryView.jsx` | Rewritten history browser with filter pills and thesis summaries |
| `frontend/src/components/WatchlistView.jsx` | Rewritten watchlist with mini thesis card grid |
| `frontend/src/components/PortfolioView.jsx` | Rewritten portfolio with summary strip + holdings table |
| `frontend/src/components/SchedulesView.jsx` | Rewritten schedule manager with card layout |
| `frontend/src/components/AlertsView.jsx` | Rewritten alerts with rules + triggers layout |

### Modified Files (4)
| File | Changes |
|------|---------|
| `frontend/src/components/Dashboard.jsx` | Complete layout rewrite: sidebar + scrollable narrative, remove tab system |
| `frontend/src/components/Sidebar.jsx` | Expand to 220px with labels, section groups, recent tickers |
| `frontend/src/components/PriceChart.jsx` | Add SMA overlays (9/20/50/100/200), legend with toggles |
| `frontend/src/index.css` | Refined design tokens, new CSS variables, cleanup |

### Removed Files (9)
| File | Absorbed By |
|------|------------|
| `ContentHeader.jsx` | SearchBar + ThesisCard |
| `Recommendation.jsx` | ThesisCard |
| `AnalysisTabs.jsx` | SectionNav |
| `AgentPipelineBar.jsx` | SearchBar (agent dots) |
| `Summary.jsx` | AnalysisSection instances |
| `ScenarioPanel.jsx` | Relevant AnalysisSection |
| `MacroSnapshot.jsx` | Macro AnalysisSection |
| `CalibrationCard.jsx` | HistoryView + MetaFooter diagnostics |
| `DiagnosticsPanel.jsx` | MetaFooter slide-over |

### Unchanged Files
- `context/AnalysisContext.jsx`, `hooks/useAnalysis.js`, `hooks/useSSE.js`, `hooks/useHistory.js`, `utils/api.js`, `App.jsx`, `main.jsx`, `Icons.jsx`
- `CouncilPanel.jsx`, `LeadershipPanel.jsx`, `NewsFeed.jsx`, `OptionsFlow.jsx` — content unchanged, wrapped in AnalysisSection

---

## Task 1: Design Tokens & CSS Foundation

**Files:**
- Modify: `frontend/src/index.css`

This task updates the CSS design tokens to match the spec's refined system. All subsequent components use these tokens.

- [ ] **Step 1: Read current index.css**

Read `frontend/src/index.css` to understand existing @theme block and :root variables.

- [ ] **Step 2: Update @theme block and :root variables**

Add these new CSS custom properties to the `:root` block in `index.css` (keep all existing properties, add/override these):

```css
:root {
  /* Existing properties stay... */

  /* Layout */
  --sidebar-width: 220px;

  /* Refined backgrounds (override existing) */
  --bg-primary: #09090b;
  --bg-card: rgba(255, 255, 255, 0.02);
  --bg-card-hover: rgba(255, 255, 255, 0.04);

  /* Refined text */
  --text-primary: rgba(255, 255, 255, 0.9);
  --text-secondary: rgba(255, 255, 255, 0.65);
  --text-muted: rgba(255, 255, 255, 0.4);
  --text-dim: rgba(255, 255, 255, 0.25);

  /* Borders */
  --border-subtle: rgba(255, 255, 255, 0.05);
  --border-default: rgba(255, 255, 255, 0.08);

  /* Sentiment colors */
  --accent-buy: #17c964;
  --accent-sell: #f31260;
  --accent-hold: #f5a524;

  /* SMA colors */
  --sma-9: #ef4444;
  --sma-20: #f59e0b;
  --sma-50: #22c55e;
  --sma-100: #3b82f6;
  --sma-200: #a855f7;

  /* Radius scale */
  --radius-sm: 4px;
  --radius-md: 8px;
  --radius-lg: 10px;
  --radius-xl: 14px;
}
```

- [ ] **Step 3: Add new utility classes**

Append to `index.css` after existing utility classes:

```css
/* Stance badge colors */
.badge-bullish { background: rgba(23, 201, 100, 0.12); color: #17c964; }
.badge-bearish { background: rgba(243, 18, 96, 0.12); color: #f31260; }
.badge-neutral { background: rgba(245, 165, 36, 0.12); color: #f5a524; }

/* Section accent bar */
.accent-bar {
  width: 3px;
  height: 20px;
  border-radius: 2px;
  flex-shrink: 0;
}

/* Slide-over panel */
.slide-over-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 50;
}

.slide-over-panel {
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  width: 480px;
  max-width: 90vw;
  background: #09090b;
  border-left: 1px solid rgba(255, 255, 255, 0.06);
  z-index: 51;
  overflow-y: auto;
  padding: 24px;
}

/* Heatmap bar */
.heatmap-bar {
  flex: 1;
  height: 4px;
  border-radius: 2px;
}
```

- [ ] **Step 4: Update --sidebar-width references**

Change `--sidebar-width: 64px` to `--sidebar-width: 220px` in the `:root` block (if it exists separately from what we added in step 2). Search for any hardcoded `64px` sidebar references in the CSS file and update to `var(--sidebar-width)`.

- [ ] **Step 5: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no CSS errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/index.css
git commit -m "style: update design tokens for frontend redesign"
```

---

## Task 2: Sidebar Rewrite

**Files:**
- Modify: `frontend/src/components/Sidebar.jsx`

Expand from 64px icon-only to 220px with labels, section groups, and recent tickers.

- [ ] **Step 1: Read current Sidebar.jsx**

Read `frontend/src/components/Sidebar.jsx` to understand current structure and props.

- [ ] **Step 2: Rewrite Sidebar component**

Replace the entire contents of `frontend/src/components/Sidebar.jsx`:

```jsx
import { motion } from 'framer-motion';
import { PulseIcon, HistoryIcon, ChartBarIcon, BuildingIcon, ClockIcon, BellIcon } from './Icons';

const NAV_SECTIONS = [
  {
    label: 'Analysis',
    items: [
      { key: 'analysis', label: 'Analysis', Icon: PulseIcon },
      { key: 'history', label: 'History', Icon: HistoryIcon },
    ],
  },
  {
    label: 'Portfolio',
    items: [
      { key: 'watchlist', label: 'Watchlist', Icon: ChartBarIcon },
      { key: 'portfolio', label: 'Holdings', Icon: BuildingIcon },
      { key: 'schedules', label: 'Schedules', Icon: ClockIcon },
      { key: 'alerts', label: 'Alerts', Icon: BellIcon },
    ],
  },
];

const STANCE_COLORS = {
  BUY: 'text-[#17c964]',
  SELL: 'text-[#f31260]',
  HOLD: 'text-[#f5a524]',
};

export default function Sidebar({ activeView, onViewChange, unacknowledgedCount = 0, recentAnalyses = [] }) {
  return (
    <aside className="fixed left-0 top-0 bottom-0 z-50 flex flex-col border-r"
      style={{
        width: 'var(--sidebar-width, 220px)',
        background: 'rgba(255,255,255,0.02)',
        borderColor: 'rgba(255,255,255,0.06)',
      }}
    >
      {/* Logo */}
      <div className="flex items-center gap-2 px-5 pt-4 pb-6">
        <div className="w-2 h-2 rounded-full bg-[#006fee]" />
        <span className="text-[0.95rem] font-bold text-white/90 tracking-tight">Market Research</span>
      </div>

      {/* Nav sections */}
      {NAV_SECTIONS.map((section) => (
        <div key={section.label} className="px-3 mb-5">
          <div className="px-2 pb-2 text-[0.6rem] uppercase tracking-[0.12em] font-semibold text-white/25">
            {section.label}
          </div>
          {section.items.map((item) => {
            const isActive = activeView === item.key;
            return (
              <button
                key={item.key}
                onClick={() => onViewChange(item.key)}
                className={`flex items-center gap-2.5 w-full px-3 py-2 rounded-lg text-[0.82rem] transition-colors relative ${
                  isActive
                    ? 'bg-[rgba(0,111,238,0.1)] text-[#006fee] font-medium'
                    : 'text-white/50 hover:bg-white/[0.04] hover:text-white/70'
                }`}
              >
                <item.Icon className="w-[18px] h-[18px]" style={{ opacity: isActive ? 1 : 0.5 }} />
                {item.label}
                {item.key === 'alerts' && unacknowledgedCount > 0 && (
                  <span className="ml-auto text-[0.6rem] font-semibold bg-[#f31260] text-white px-1.5 py-0.5 rounded-full min-w-[18px] text-center">
                    {unacknowledgedCount}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      ))}

      {/* Divider */}
      <div className="mx-5 h-px bg-white/5" />

      {/* Recent analyses */}
      <div className="px-3 mt-auto pb-4">
        <div className="px-2 pb-2 text-[0.6rem] uppercase tracking-[0.12em] font-semibold text-white/25">
          Recent
        </div>
        {recentAnalyses.slice(0, 5).map((item) => (
          <button
            key={item.ticker}
            onClick={() => {
              onViewChange('analysis');
              item.onSelect?.();
            }}
            className="flex items-center justify-between w-full px-3 py-1.5 rounded-md text-white/40 hover:bg-white/[0.03] hover:text-white/60 transition-colors"
          >
            <span className="text-[0.75rem] font-semibold tabular-nums">{item.ticker}</span>
            <span className={`text-[0.65rem] font-medium ${STANCE_COLORS[item.recommendation] || 'text-white/40'}`}>
              {item.recommendation}
            </span>
          </button>
        ))}
        {recentAnalyses.length === 0 && (
          <div className="px-3 py-2 text-[0.7rem] text-white/20">No recent analyses</div>
        )}
      </div>
    </aside>
  );
}
```

- [ ] **Step 3: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds. (Dashboard will need updating to pass new props — that's Task 9.)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/Sidebar.jsx
git commit -m "feat: rewrite sidebar with 220px labeled nav and recent tickers"
```

---

## Task 3: SearchBar Component

**Files:**
- Create: `frontend/src/components/SearchBar.jsx`

Extract the search/analyze UI from ContentHeader into a standalone sticky bar with compact agent progress dots.

- [ ] **Step 1: Read ContentHeader.jsx for reference**

Read `frontend/src/components/ContentHeader.jsx` to understand the search form logic and stage text mapping.

- [ ] **Step 2: Create SearchBar.jsx**

Create `frontend/src/components/SearchBar.jsx`:

```jsx
import { useState } from 'react';
import { SearchIcon } from './Icons';

const STAGE_TEXT = {
  starting: 'Initializing...',
  gathering_data: 'Gathering data...',
  running_market: 'Market data...',
  running_fundamentals: 'Fundamentals...',
  running_news: 'Fetching news...',
  running_technical: 'Technical analysis...',
  running_options: 'Options flow...',
  running_macro: 'Macro environment...',
  analyzing_sentiment: 'Sentiment...',
  synthesizing: 'Synthesizing...',
  saving: 'Saving...',
  complete: 'Complete',
  error: 'Failed',
};

const AGENT_KEYS = ['market', 'fundamentals', 'technical', 'news', 'sentiment', 'macro', 'options'];

function AgentDots({ analysis, loading, stage }) {
  if (!loading && !analysis) return null;

  return (
    <div className="flex items-center gap-1.5 ml-auto">
      {loading && stage && stage !== 'complete' && (
        <span className="text-[0.7rem] text-white/30 mr-2">{STAGE_TEXT[stage] || stage}</span>
      )}
      {AGENT_KEYS.map((key) => {
        const result = analysis?.agent_results?.[key];
        let color = 'bg-white/10'; // pending
        if (result?.success) color = 'bg-[#17c964]'; // done
        else if (result?.success === false) color = 'bg-[#f31260]'; // failed
        else if (loading) color = 'bg-[#006fee] animate-pulse'; // running
        return <div key={key} className={`w-[7px] h-[7px] rounded-full ${color}`} title={key} />;
      })}
    </div>
  );
}

export default function SearchBar({ tickerInput, setTickerInput, onAnalyze, loading, analysis, stage }) {
  const handleSubmit = (e) => {
    e.preventDefault();
    if (tickerInput.trim() && !loading) {
      onAnalyze(e);
    }
  };

  return (
    <div
      className="sticky top-0 z-40 flex items-center gap-3 px-6 py-3"
      style={{
        background: 'rgba(9,9,11,0.85)',
        backdropFilter: 'blur(12px)',
        borderBottom: '1px solid rgba(255,255,255,0.05)',
      }}
    >
      <form onSubmit={handleSubmit} className="flex items-center gap-2">
        <div className="relative">
          <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/25" />
          <input
            type="text"
            value={tickerInput}
            onChange={(e) => setTickerInput(e.target.value.toUpperCase())}
            placeholder="Enter ticker..."
            maxLength={5}
            disabled={loading}
            className="pl-9 pr-3 py-2 rounded-lg text-[0.85rem] text-white/80 placeholder:text-white/25 outline-none w-[200px]"
            style={{
              background: 'rgba(255,255,255,0.04)',
              border: '1px solid rgba(255,255,255,0.08)',
            }}
          />
        </div>
        <button
          type="submit"
          disabled={loading || !tickerInput.trim()}
          className="px-4 py-2 rounded-lg border-none text-[0.82rem] font-semibold text-white cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
          style={{ background: '#006fee' }}
        >
          {loading ? 'Analyzing...' : 'Analyze'}
        </button>
      </form>
      <AgentDots analysis={analysis} loading={loading} stage={stage} />
    </div>
  );
}
```

- [ ] **Step 3: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/SearchBar.jsx
git commit -m "feat: add SearchBar component with agent progress dots"
```

---

## Task 4: ThesisCard Component

**Files:**
- Create: `frontend/src/components/ThesisCard.jsx`

The V2 split thesis card — verdict/target/heatmap on the left, narrative/signals on the right.

- [ ] **Step 1: Read Recommendation.jsx for data extraction patterns**

Read `frontend/src/components/Recommendation.jsx` to understand how recommendation, score, confidence, and agent signals are extracted from the analysis object.

- [ ] **Step 2: Create ThesisCard.jsx**

Create `frontend/src/components/ThesisCard.jsx`:

```jsx
const AGENT_HEATMAP = [
  { key: 'market', label: 'MKT' },
  { key: 'fundamentals', label: 'FUN' },
  { key: 'technical', label: 'TCH' },
  { key: 'news', label: 'NWS' },
  { key: 'sentiment', label: 'SNT' },
  { key: 'macro', label: 'MAC' },
  { key: 'options', label: 'OPT' },
];

const REC_COLORS = {
  BUY: { text: '#17c964', gradFrom: 'rgba(23,201,100,0.06)', gradTo: 'rgba(23,201,100,0.01)', border: 'rgba(23,201,100,0.12)' },
  SELL: { text: '#f31260', gradFrom: 'rgba(243,18,96,0.06)', gradTo: 'rgba(243,18,96,0.01)', border: 'rgba(243,18,96,0.12)' },
  HOLD: { text: '#f5a524', gradFrom: 'rgba(245,165,36,0.06)', gradTo: 'rgba(245,165,36,0.01)', border: 'rgba(245,165,36,0.12)' },
};

const SIGNAL_COLORS = { bullish: '#17c964', bearish: '#f31260', neutral: '#f5a524' };

function getAgentStance(agentKey, agentResult) {
  if (!agentResult?.success || !agentResult?.data) return 'neutral';
  const d = agentResult.data;

  switch (agentKey) {
    case 'fundamentals': return (d.health_score > 60) ? 'bullish' : (d.health_score < 40) ? 'bearish' : 'neutral';
    case 'technical': return d.signals?.overall || 'neutral';
    case 'sentiment': return (d.overall_sentiment > 0.3) ? 'bullish' : (d.overall_sentiment < -0.3) ? 'bearish' : 'neutral';
    case 'market': {
      const trend = (d.trend || '').toLowerCase();
      return trend.includes('up') || trend.includes('bull') ? 'bullish' : trend.includes('down') || trend.includes('bear') ? 'bearish' : 'neutral';
    }
    case 'macro': return d.risk_environment === 'dovish' ? 'bullish' : d.risk_environment === 'hawkish' ? 'bearish' : 'neutral';
    case 'options': return d.overall_signal || 'neutral';
    case 'news': {
      const articles = d.articles || [];
      if (!articles.length) return 'neutral';
      const avg = articles.reduce((sum, a) => sum + (a.overall_sentiment_score ?? a.sentiment_score ?? 0), 0) / articles.length;
      return avg > 0.15 ? 'bullish' : avg < -0.15 ? 'bearish' : 'neutral';
    }
    default: return 'neutral';
  }
}

function getStanceColor(stance) {
  return SIGNAL_COLORS[stance] || SIGNAL_COLORS.neutral;
}

export default function ThesisCard({ analysis }) {
  if (!analysis) return null;

  const payload = analysis.analysis || analysis;
  const signal = payload.signal_contract_v2 || {};
  const agentResults = analysis.agent_results || payload.agent_results || {};
  const marketData = agentResults.market?.data || {};

  const recommendation = (signal.recommendation || payload.recommendation || 'HOLD').toUpperCase();
  const colors = REC_COLORS[recommendation] || REC_COLORS.HOLD;
  const ticker = analysis.ticker || '';
  const price = marketData.current_price;
  const changePct = marketData.price_change_1m?.change_pct;
  const isPositive = changePct > 0;

  // Price targets from scenarios or signal contract
  const scenarios = payload.scenarios || signal.scenarios || {};
  const targetLow = scenarios.base?.price_target || signal.price_target_low;
  const targetHigh = scenarios.bull?.price_target || signal.price_target_high;
  const targetRange = targetLow && targetHigh ? `$${Math.round(targetLow)} – $${Math.round(targetHigh)}` : null;

  // Thesis text
  const thesis = payload.executive_summary || payload.synthesis || payload.summary || '';

  // Top signals (from key_factors or key_findings)
  const signals = payload.key_factors || payload.key_findings || [];
  const topSignals = (Array.isArray(signals) ? signals : []).slice(0, 3);

  return (
    <div
      className="mx-6 mt-5 rounded-[14px] flex gap-7"
      style={{
        padding: '24px',
        background: `linear-gradient(135deg, ${colors.gradFrom}, ${colors.gradTo})`,
        border: `1px solid ${colors.border}`,
      }}
    >
      {/* Left: Verdict */}
      <div className="flex-shrink-0 w-[200px] pr-7" style={{ borderRight: '1px solid rgba(255,255,255,0.06)' }}>
        <div className="text-[0.65rem] uppercase tracking-[0.1em] text-white/35 mb-2">
          {ticker} · {price ? `$${price.toFixed(2)}` : '—'}{' '}
          {changePct != null && (
            <span style={{ color: isPositive ? '#17c964' : '#f31260' }}>
              {isPositive ? '+' : ''}{changePct.toFixed(1)}%
            </span>
          )}
        </div>
        <div className="text-[2.4rem] font-extrabold leading-none mb-1.5" style={{ color: colors.text }}>
          {recommendation}
        </div>
        {targetRange && <div className="text-[0.85rem] text-white/45 mb-3.5">{targetRange}</div>}

        {/* Agent heatmap */}
        <div className="flex gap-[3px] mb-1">
          {AGENT_HEATMAP.map(({ key }) => (
            <div key={key} className="heatmap-bar" style={{ background: getStanceColor(getAgentStance(key, agentResults[key])) }} />
          ))}
        </div>
        <div className="flex justify-between text-[0.55rem] text-white/20">
          {AGENT_HEATMAP.map(({ key, label }) => <span key={key}>{label}</span>)}
        </div>
      </div>

      {/* Right: Thesis + Signals */}
      <div className="flex-1">
        <div className="text-[1.05rem] font-medium text-white/85 leading-relaxed mb-4">
          {thesis || 'Analysis synthesis pending...'}
        </div>
        <div className="flex flex-col gap-1.5 text-[0.8rem] text-white/50">
          {topSignals.map((sig, i) => {
            const text = typeof sig === 'string' ? sig : sig.description || sig.text || sig.factor || '';
            const direction = typeof sig === 'object' ? (sig.direction || sig.impact || '') : '';
            const isUp = direction.toLowerCase?.().includes('positive') || direction.toLowerCase?.().includes('bullish');
            const isDown = direction.toLowerCase?.().includes('negative') || direction.toLowerCase?.().includes('bearish');
            return (
              <div key={i}>
                <span style={{ color: isUp ? '#17c964' : isDown ? '#f31260' : '#f5a524' }}>
                  {isUp ? '▲' : isDown ? '▼' : '●'}
                </span>{' '}
                {text}
              </div>
            );
          })}
          {topSignals.length === 0 && thesis && (
            <div className="text-white/30 text-[0.75rem]">Supporting signals will appear here</div>
          )}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ThesisCard.jsx
git commit -m "feat: add ThesisCard with V2 split verdict/evidence layout"
```

---

## Task 5: AnalysisSection Component

**Files:**
- Create: `frontend/src/components/AnalysisSection.jsx`

Shared template for each agent's expandable section in the narrative flow.

- [ ] **Step 1: Create AnalysisSection.jsx**

Create `frontend/src/components/AnalysisSection.jsx`:

```jsx
import { useState, forwardRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

const STANCE_CONFIG = {
  bullish: { label: 'Bullish', className: 'badge-bullish' },
  bearish: { label: 'Bearish', className: 'badge-bearish' },
  neutral: { label: 'Neutral', className: 'badge-neutral' },
};

function MetricItem({ label, value, color }) {
  return (
    <div className="text-[0.75rem]">
      <span className="text-white/30">{label}</span>
      <span className="font-semibold tabular-nums ml-1.5" style={{ color: color || 'rgba(255,255,255,0.7)' }}>
        {value}
      </span>
    </div>
  );
}

const AnalysisSection = forwardRef(function AnalysisSection(
  { id, name, stance, stanceColor, summary, metrics, fullContent, dataSource, duration, children },
  ref
) {
  const [expanded, setExpanded] = useState(false);
  const config = STANCE_CONFIG[stance] || STANCE_CONFIG.neutral;

  return (
    <div
      ref={ref}
      id={id}
      className="rounded-[10px] p-5"
      style={{
        background: 'rgba(255,255,255,0.02)',
        border: '1px solid rgba(255,255,255,0.06)',
      }}
    >
      {/* Header */}
      <div className="flex justify-between items-start mb-3">
        <div className="flex items-center gap-2.5">
          <div className="accent-bar" style={{ background: stanceColor || '#f5a524' }} />
          <span className="text-[0.95rem] font-semibold text-white/90">{name}</span>
          <span className={`text-[0.68rem] px-2 py-0.5 rounded font-medium ${config.className}`}>
            {config.label}
          </span>
        </div>
        <span className="text-[0.68rem] text-white/20">
          {dataSource}{duration != null ? ` · ${duration.toFixed(1)}s` : ''}
        </span>
      </div>

      {/* Summary */}
      {summary && (
        <div className="text-[0.88rem] text-white/65 leading-relaxed mb-3">{summary}</div>
      )}

      {/* Metrics row */}
      {metrics && metrics.length > 0 && (
        <div className="flex gap-6 mb-2.5">
          {metrics.map((m, i) => (
            <MetricItem key={i} label={m.label} value={m.value} color={m.color} />
          ))}
        </div>
      )}

      {/* Expand toggle */}
      {(fullContent || children) && (
        <>
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-[0.75rem] font-medium cursor-pointer border-none bg-transparent"
            style={{ color: 'rgba(0,111,238,0.7)' }}
            onMouseEnter={(e) => (e.target.style.color = '#006fee')}
            onMouseLeave={(e) => (e.target.style.color = 'rgba(0,111,238,0.7)')}
          >
            {expanded ? 'Hide details ▲' : 'Show full analysis ▼'}
          </button>
          <AnimatePresence>
            {expanded && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.2 }}
                className="overflow-hidden"
              >
                <div className="mt-3 pt-3" style={{ borderTop: '1px solid rgba(255,255,255,0.05)' }}>
                  {children || (
                    <div className="text-[0.82rem] text-white/55 leading-relaxed whitespace-pre-wrap">
                      {typeof fullContent === 'string' ? fullContent : JSON.stringify(fullContent, null, 2)}
                    </div>
                  )}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </>
      )}
    </div>
  );
});

export default AnalysisSection;
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/AnalysisSection.jsx
git commit -m "feat: add AnalysisSection shared template with expandable detail"
```

---

## Task 6: SectionNav Component

**Files:**
- Create: `frontend/src/components/SectionNav.jsx`

Sticky pill navigation that highlights the active section on scroll and scrolls to sections on click.

- [ ] **Step 1: Create SectionNav.jsx**

Create `frontend/src/components/SectionNav.jsx`:

```jsx
import { useState, useEffect, useCallback } from 'react';

const SECTIONS = [
  { id: 'section-fundamentals', label: 'Fundamentals' },
  { id: 'section-technical', label: 'Technical' },
  { id: 'section-sentiment', label: 'Sentiment' },
  { id: 'section-macro', label: 'Macro' },
  { id: 'section-news', label: 'News' },
  { id: 'section-options', label: 'Options' },
  { id: 'section-leadership', label: 'Leadership' },
  { id: 'section-council', label: 'Council' },
];

export default function SectionNav({ searchBarHeight = 49 }) {
  const [activeId, setActiveId] = useState(SECTIONS[0].id);

  // IntersectionObserver to track which section is in view
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setActiveId(entry.target.id);
          }
        }
      },
      { rootMargin: '-120px 0px -60% 0px', threshold: 0 }
    );

    SECTIONS.forEach(({ id }) => {
      const el = document.getElementById(id);
      if (el) observer.observe(el);
    });

    return () => observer.disconnect();
  }, []);

  const handleClick = useCallback((sectionId) => {
    const el = document.getElementById(sectionId);
    if (el) {
      const offset = searchBarHeight + 48; // search bar + nav height
      const top = el.getBoundingClientRect().top + window.scrollY - offset;
      window.scrollTo({ top, behavior: 'smooth' });
    }
  }, [searchBarHeight]);

  return (
    <div
      className="sticky z-[35] flex gap-1 px-6 py-2"
      style={{
        top: `${searchBarHeight}px`,
        background: 'rgba(9,9,11,0.9)',
        backdropFilter: 'blur(8px)',
        borderBottom: '1px solid rgba(255,255,255,0.04)',
      }}
    >
      {SECTIONS.map(({ id, label }) => {
        const isActive = activeId === id;
        return (
          <button
            key={id}
            onClick={() => handleClick(id)}
            className={`px-3.5 py-1.5 rounded-md text-[0.75rem] font-medium transition-colors border-none cursor-pointer ${
              isActive
                ? 'text-[#006fee] bg-[rgba(0,111,238,0.08)]'
                : 'text-white/35 bg-transparent hover:text-white/55 hover:bg-white/[0.03]'
            }`}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/SectionNav.jsx
git commit -m "feat: add SectionNav sticky pill navigation with scroll tracking"
```

---

## Task 7: PriceChart SMA Enhancement

**Files:**
- Modify: `frontend/src/components/PriceChart.jsx`

Add SMA overlays (9, 20, 50, 100, 200 day) with a toggleable legend below the chart.

- [ ] **Step 1: Read current PriceChart.jsx**

Read `frontend/src/components/PriceChart.jsx` to understand the existing lightweight-charts setup, specifically the `useEffect` that creates the chart instance and how candle data is formatted.

- [ ] **Step 2: Add SMA calculation utility**

Add the following at the top of `PriceChart.jsx`, after the existing imports:

```javascript
const SMA_CONFIG = [
  { period: 9, color: '#ef4444', label: 'SMA 9', defaultVisible: false },
  { period: 20, color: '#f59e0b', label: 'SMA 20', defaultVisible: false },
  { period: 50, color: '#22c55e', label: 'SMA 50', defaultVisible: true },
  { period: 100, color: '#3b82f6', label: 'SMA 100', defaultVisible: false },
  { period: 200, color: '#a855f7', label: 'SMA 200', defaultVisible: true },
];

function calculateSMA(data, period) {
  const result = [];
  for (let i = period - 1; i < data.length; i++) {
    let sum = 0;
    for (let j = i - period + 1; j <= i; j++) {
      sum += data[j].close;
    }
    result.push({ time: data[i].time, value: sum / period });
  }
  return result;
}
```

- [ ] **Step 3: Add SMA visibility state**

Add this state hook inside the PriceChart component, near the top with other state:

```javascript
const [smaVisibility, setSmaVisibility] = useState(() =>
  Object.fromEntries(SMA_CONFIG.map((s) => [s.period, s.defaultVisible]))
);
const smaSeriesRef = useRef({});
```

- [ ] **Step 4: Add SMA series to chart creation useEffect**

Inside the `useEffect` that creates the chart and adds the candlestick series, after the candle series `setData()` call, add the SMA lines:

```javascript
// Add SMA line series
const sortedCandles = /* the sorted candle data already in scope */;
SMA_CONFIG.forEach(({ period, color }) => {
  const lineSeries = chart.addLineSeries({
    color,
    lineWidth: 1,
    priceLineVisible: false,
    lastValueVisible: false,
    crosshairMarkerVisible: false,
    visible: smaVisibility[period],
  });
  const smaData = calculateSMA(sortedCandles, period);
  if (smaData.length > 0) {
    lineSeries.setData(smaData);
  }
  smaSeriesRef.current[period] = lineSeries;
});
```

**Important:** The `sortedCandles` array must have `{ time, open, high, low, close }` format — use the same variable that feeds the candlestick series. The `time` field must be in the same format (YYYY-MM-DD string or UTC timestamp).

- [ ] **Step 5: Add toggle handler**

Add this function inside the component:

```javascript
const toggleSMA = useCallback((period) => {
  setSmaVisibility((prev) => {
    const next = { ...prev, [period]: !prev[period] };
    const series = smaSeriesRef.current[period];
    if (series) {
      series.applyOptions({ visible: next[period] });
    }
    return next;
  });
}, []);
```

- [ ] **Step 6: Add SMA legend below chart**

After the chart container div and before the technical indicator cards grid, add the SMA legend:

```jsx
{/* SMA Legend */}
<div className="flex gap-3.5 mt-2.5 pt-2.5" style={{ borderTop: '1px solid rgba(255,255,255,0.04)' }}>
  {SMA_CONFIG.map(({ period, color, label }) => (
    <button
      key={period}
      onClick={() => toggleSMA(period)}
      className="flex items-center gap-1.5 text-[0.65rem] border-none bg-transparent cursor-pointer transition-opacity"
      style={{ color: smaVisibility[period] ? 'rgba(255,255,255,0.5)' : 'rgba(255,255,255,0.2)', opacity: smaVisibility[period] ? 1 : 0.5 }}
    >
      <div className="rounded-sm" style={{ width: 8, height: 2, background: color }} />
      {label}
    </button>
  ))}
</div>
```

- [ ] **Step 7: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/PriceChart.jsx
git commit -m "feat: add SMA overlays (9/20/50/100/200) with toggleable legend"
```

---

## Task 8: MetaFooter & Diagnostics Slide-Over

**Files:**
- Create: `frontend/src/components/MetaFooter.jsx`

Analysis metadata footer with a slide-over panel for diagnostics.

- [ ] **Step 1: Read DiagnosticsPanel.jsx for data shapes**

Read `frontend/src/components/DiagnosticsPanel.jsx` to understand what diagnostic data is available and how it's extracted.

- [ ] **Step 2: Create MetaFooter.jsx**

Create `frontend/src/components/MetaFooter.jsx`:

```jsx
import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

function DiagnosticsSlideOver({ analysis, onClose }) {
  const payload = analysis?.analysis || analysis || {};
  const agentResults = analysis?.agent_results || payload?.agent_results || {};
  const diagnostics = payload.diagnostics || {};
  const disagreement = diagnostics.disagreement || {};
  const dataQuality = diagnostics.data_quality || {};

  return (
    <>
      <motion.div
        className="slide-over-backdrop"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
      />
      <motion.div
        className="slide-over-panel"
        initial={{ x: '100%' }}
        animate={{ x: 0 }}
        exit={{ x: '100%' }}
        transition={{ type: 'spring', damping: 30, stiffness: 300 }}
      >
        <div className="flex justify-between items-center mb-6">
          <h3 className="text-[1rem] font-semibold text-white/90">Diagnostics</h3>
          <button
            onClick={onClose}
            className="text-white/40 hover:text-white/70 text-lg bg-transparent border-none cursor-pointer"
          >
            ✕
          </button>
        </div>

        {/* Agent Timing */}
        <div className="mb-6">
          <h4 className="text-[0.8rem] font-semibold text-white/60 mb-3">Agent Performance</h4>
          <div className="flex flex-col gap-1.5">
            {Object.entries(agentResults).map(([key, result]) => (
              <div key={key} className="flex items-center justify-between py-1.5 px-3 rounded-md" style={{ background: 'rgba(255,255,255,0.02)' }}>
                <div className="flex items-center gap-2">
                  <div className="w-1.5 h-1.5 rounded-full" style={{ background: result?.success ? '#17c964' : '#f31260' }} />
                  <span className="text-[0.78rem] text-white/70 capitalize">{key}</span>
                </div>
                <span className="text-[0.72rem] text-white/40 tabular-nums">
                  {result?.duration_seconds != null ? `${result.duration_seconds.toFixed(1)}s` : '—'}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Data Quality */}
        {dataQuality.quality_level && (
          <div className="mb-6">
            <h4 className="text-[0.8rem] font-semibold text-white/60 mb-3">Data Quality</h4>
            <div className="flex gap-4 text-[0.75rem]">
              <div>
                <span className="text-white/30">Level</span>{' '}
                <span className="text-white/70 font-medium capitalize">{dataQuality.quality_level}</span>
              </div>
              <div>
                <span className="text-white/30">Success Rate</span>{' '}
                <span className="text-white/70 font-medium">{((dataQuality.agent_success_rate || 0) * 100).toFixed(0)}%</span>
              </div>
            </div>
            {dataQuality.warnings?.length > 0 && (
              <div className="mt-2 flex flex-col gap-1">
                {dataQuality.warnings.map((w, i) => (
                  <div key={i} className="text-[0.72rem] text-[#f5a524]/70">⚠ {w}</div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Agent Disagreement */}
        {disagreement.is_conflicted && (
          <div className="mb-6">
            <h4 className="text-[0.8rem] font-semibold text-white/60 mb-3">Signal Disagreement</h4>
            <div className="flex gap-3 text-[0.75rem] mb-2">
              <span className="text-[#17c964]">▲ {disagreement.bullish_count || 0} bullish</span>
              <span className="text-[#f5a524]">● {disagreement.neutral_count || 0} neutral</span>
              <span className="text-[#f31260]">▼ {disagreement.bearish_count || 0} bearish</span>
            </div>
            {disagreement.agent_directions && (
              <div className="flex flex-wrap gap-2">
                {Object.entries(disagreement.agent_directions).map(([agent, direction]) => (
                  <span key={agent} className="text-[0.68rem] px-2 py-0.5 rounded text-white/50" style={{ background: 'rgba(255,255,255,0.03)' }}>
                    {agent}: <span className="capitalize font-medium">{direction}</span>
                  </span>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Guardrail Warnings */}
        {payload.guardrail_warnings?.length > 0 && (
          <div className="mb-6">
            <h4 className="text-[0.8rem] font-semibold text-white/60 mb-3">Guardrail Warnings</h4>
            {payload.guardrail_warnings.map((w, i) => (
              <div key={i} className="text-[0.72rem] text-[#f5a524]/70 mb-1">⚠ {w}</div>
            ))}
          </div>
        )}
      </motion.div>
    </>
  );
}

export default function MetaFooter({ analysis }) {
  const [showDiagnostics, setShowDiagnostics] = useState(false);

  if (!analysis) return null;

  const timestamp = analysis.timestamp;
  const agentResults = analysis.agent_results || analysis.analysis?.agent_results || {};
  const agentCount = Object.keys(agentResults).length;
  const successCount = Object.values(agentResults).filter((r) => r?.success).length;
  const totalDuration = Object.values(agentResults).reduce((sum, r) => sum + (r?.duration_seconds || 0), 0);

  const formatDate = (ts) => {
    if (!ts) return '—';
    const d = new Date(ts);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) +
      ' ' + d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
  };

  return (
    <>
      <div
        className="mx-6 mb-6 px-5 py-4 rounded-[10px] flex items-center gap-6"
        style={{
          background: 'rgba(255,255,255,0.015)',
          border: '1px solid rgba(255,255,255,0.04)',
        }}
      >
        <span className="text-[0.72rem] text-white/30">
          Analyzed <span className="text-white/50 font-medium">{formatDate(timestamp)}</span>
        </span>
        <span className="text-[0.72rem] text-white/30">
          Duration <span className="text-white/50 font-medium">{totalDuration.toFixed(1)}s</span>
        </span>
        <span className="text-[0.72rem] text-white/30">
          Agents <span className="text-white/50 font-medium">{successCount}/{agentCount} succeeded</span>
        </span>
        <button
          onClick={() => setShowDiagnostics(true)}
          className="ml-auto text-[0.72rem] font-medium bg-transparent border-none cursor-pointer"
          style={{ color: 'rgba(0,111,238,0.5)' }}
          onMouseEnter={(e) => (e.target.style.color = '#006fee')}
          onMouseLeave={(e) => (e.target.style.color = 'rgba(0,111,238,0.5)')}
        >
          View Diagnostics →
        </button>
      </div>

      <AnimatePresence>
        {showDiagnostics && (
          <DiagnosticsSlideOver analysis={analysis} onClose={() => setShowDiagnostics(false)} />
        )}
      </AnimatePresence>
    </>
  );
}
```

- [ ] **Step 3: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/MetaFooter.jsx
git commit -m "feat: add MetaFooter with diagnostics slide-over panel"
```

---

## Task 9: Dashboard Layout Rewrite

**Files:**
- Modify: `frontend/src/components/Dashboard.jsx`

This is the core task — rewire Dashboard from the tab-based layout to the new sidebar + scrollable narrative pattern. All new components get assembled here.

- [ ] **Step 1: Read current Dashboard.jsx thoroughly**

Read `frontend/src/components/Dashboard.jsx` to understand every piece of state, every handler, and every rendering path. Pay special attention to: `handleAnalyze`, `viewMode` switching, `activeTab` routing, the right sidebar rendering, and the alert polling.

- [ ] **Step 2: Rewrite Dashboard.jsx**

Replace the entire contents of `frontend/src/components/Dashboard.jsx`:

```jsx
import { useState, useEffect, useCallback } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { useAnalysisContext } from '../context/AnalysisContext';
import useAnalysis from '../hooks/useAnalysis';
import { getUnacknowledgedCount } from '../utils/api';

import Sidebar from './Sidebar';
import SearchBar from './SearchBar';
import ThesisCard from './ThesisCard';
import PriceChart from './PriceChart';
import SectionNav from './SectionNav';
import AnalysisSection from './AnalysisSection';
import MetaFooter from './MetaFooter';
import LeadershipPanel from './LeadershipPanel';
import CouncilPanel from './CouncilPanel';
import NewsFeed from './NewsFeed';
import OptionsFlow from './OptionsFlow';
import HistoryView from './HistoryView';
import WatchlistView from './WatchlistView';
import PortfolioView from './PortfolioView';
import SchedulesView from './SchedulesView';
import AlertsView from './AlertsView';

const VIEW_MODES = {
  ANALYSIS: 'analysis',
  HISTORY: 'history',
  WATCHLIST: 'watchlist',
  PORTFOLIO: 'portfolio',
  SCHEDULES: 'schedules',
  ALERTS: 'alerts',
};

// Map agent stance from data
function getStance(agentKey, result) {
  if (!result?.success || !result?.data) return 'neutral';
  const d = result.data;
  switch (agentKey) {
    case 'fundamentals': return d.health_score > 60 ? 'bullish' : d.health_score < 40 ? 'bearish' : 'neutral';
    case 'technical': return d.signals?.overall || 'neutral';
    case 'sentiment': return d.overall_sentiment > 0.3 ? 'bullish' : d.overall_sentiment < -0.3 ? 'bearish' : 'neutral';
    case 'market': {
      const t = (d.trend || '').toLowerCase();
      return t.includes('up') || t.includes('bull') ? 'bullish' : t.includes('down') || t.includes('bear') ? 'bearish' : 'neutral';
    }
    case 'macro': return d.risk_environment === 'dovish' ? 'bullish' : d.risk_environment === 'hawkish' ? 'bearish' : 'neutral';
    case 'options': return d.overall_signal || 'neutral';
    case 'news': {
      const articles = d.articles || [];
      if (!articles.length) return 'neutral';
      const avg = articles.reduce((s, a) => s + (a.overall_sentiment_score ?? a.sentiment_score ?? 0), 0) / articles.length;
      return avg > 0.15 ? 'bullish' : avg < -0.15 ? 'bearish' : 'neutral';
    }
    default: return 'neutral';
  }
}

const STANCE_COLORS = { bullish: '#17c964', bearish: '#f31260', neutral: '#f5a524' };

function getAgentSummary(agentKey, result) {
  if (!result?.success || !result?.data) return null;
  const d = result.data;
  return d.analysis || d.summary || d.executive_summary || null;
}

function getAgentMetrics(agentKey, result) {
  if (!result?.success || !result?.data) return [];
  const d = result.data;
  switch (agentKey) {
    case 'fundamentals': return [
      d.pe_ratio != null && { label: 'P/E', value: `${Number(d.pe_ratio).toFixed(1)}x` },
      d.revenue_growth != null && { label: 'Rev Growth', value: `${d.revenue_growth > 0 ? '+' : ''}${(d.revenue_growth * 100).toFixed(0)}%`, color: d.revenue_growth > 0 ? '#17c964' : '#f31260' },
      d.net_margin != null && { label: 'Margin', value: `${(d.net_margin * 100).toFixed(1)}%` },
      d.health_score != null && { label: 'Health', value: `${d.health_score}/100` },
    ].filter(Boolean);
    case 'technical': return [
      d.indicators?.rsi?.value != null && { label: 'RSI', value: `${Math.round(d.indicators.rsi.value)}` },
      d.indicators?.macd?.interpretation && { label: 'MACD', value: d.indicators.macd.interpretation, color: d.indicators.macd.interpretation?.toLowerCase().includes('bull') ? '#17c964' : undefined },
      d.signals?.strength != null && { label: 'Strength', value: `${(d.signals.strength * 100).toFixed(0)}%` },
    ].filter(Boolean);
    case 'sentiment': return [
      d.overall_sentiment != null && { label: 'Score', value: d.overall_sentiment.toFixed(2), color: d.overall_sentiment > 0.3 ? '#17c964' : d.overall_sentiment < -0.3 ? '#f31260' : undefined },
    ].filter(Boolean);
    case 'macro': return [
      d.fed_funds_rate != null && { label: 'Fed Rate', value: `${d.fed_funds_rate}%` },
      d.cpi != null && { label: 'CPI', value: `${d.cpi}%` },
      d.gdp_growth != null && { label: 'GDP', value: `${d.gdp_growth}%` },
    ].filter(Boolean);
    case 'options': return [
      d.put_call_ratio != null && { label: 'P/C Ratio', value: d.put_call_ratio.toFixed(2) },
      d.overall_signal && { label: 'Signal', value: d.overall_signal, color: STANCE_COLORS[d.overall_signal] },
      d.max_pain != null && { label: 'Max Pain', value: `$${d.max_pain}` },
    ].filter(Boolean);
    default: return [];
  }
}

export default function Dashboard() {
  const { analysis, loading, error, progress, stage, currentTicker } = useAnalysisContext();
  const { runAnalysis, fetchLatest } = useAnalysis();

  const [tickerInput, setTickerInput] = useState('');
  const [viewMode, setViewMode] = useState(VIEW_MODES.ANALYSIS);
  const [unacknowledgedCount, setUnacknowledgedCount] = useState(0);
  const [recentAnalyses, setRecentAnalyses] = useState([]);

  // Poll alert count
  useEffect(() => {
    const poll = () => getUnacknowledgedCount().then((r) => setUnacknowledgedCount(r?.data?.count || 0)).catch(() => {});
    poll();
    const id = setInterval(poll, 30000);
    return () => clearInterval(id);
  }, []);

  // Track recent analyses
  useEffect(() => {
    if (analysis?.ticker) {
      const rec = (analysis.analysis?.signal_contract_v2?.recommendation || analysis.analysis?.recommendation || 'HOLD').toUpperCase();
      setRecentAnalyses((prev) => {
        const filtered = prev.filter((r) => r.ticker !== analysis.ticker);
        return [{ ticker: analysis.ticker, recommendation: rec, onSelect: () => fetchLatest(analysis.ticker) }, ...filtered].slice(0, 5);
      });
    }
  }, [analysis, fetchLatest]);

  const handleAnalyze = useCallback((e) => {
    e?.preventDefault?.();
    if (tickerInput.trim() && !loading) {
      setViewMode(VIEW_MODES.ANALYSIS);
      runAnalysis(tickerInput.trim());
    }
  }, [tickerInput, loading, runAnalysis]);

  const agentResults = analysis?.agent_results || analysis?.analysis?.agent_results || {};
  const showAnalysis = viewMode === VIEW_MODES.ANALYSIS && (analysis || loading);

  // Narrative section configs
  const sections = [
    { id: 'section-fundamentals', key: 'fundamentals', name: 'Fundamentals' },
    { id: 'section-technical', key: 'technical', name: 'Technical' },
    { id: 'section-sentiment', key: 'sentiment', name: 'Sentiment' },
    { id: 'section-macro', key: 'macro', name: 'Macro' },
    { id: 'section-news', key: 'news', name: 'News' },
    { id: 'section-options', key: 'options', name: 'Options' },
    { id: 'section-leadership', key: 'leadership', name: 'Leadership' },
    { id: 'section-council', key: 'council', name: 'Council' },
  ];

  return (
    <div className="flex min-h-screen" style={{ background: 'var(--bg-primary)' }}>
      <Sidebar
        activeView={viewMode}
        onViewChange={setViewMode}
        unacknowledgedCount={unacknowledgedCount}
        recentAnalyses={recentAnalyses}
      />

      <main className="flex-1 flex flex-col" style={{ marginLeft: 'var(--sidebar-width, 220px)' }}>
        <SearchBar
          tickerInput={tickerInput}
          setTickerInput={setTickerInput}
          onAnalyze={handleAnalyze}
          loading={loading}
          analysis={analysis}
          stage={stage}
        />

        {/* Error banner */}
        {error && (
          <div className="mx-6 mt-3 px-4 py-3 rounded-lg text-[0.82rem] text-[#f31260] bg-[rgba(243,18,96,0.08)] border border-[rgba(243,18,96,0.15)]">
            {error}
          </div>
        )}

        {/* View content */}
        {viewMode === VIEW_MODES.HISTORY && <HistoryView onSelectAnalysis={(ticker) => { fetchLatest(ticker); setViewMode(VIEW_MODES.ANALYSIS); }} />}
        {viewMode === VIEW_MODES.WATCHLIST && <WatchlistView onSelectTicker={(ticker) => { setTickerInput(ticker); runAnalysis(ticker); setViewMode(VIEW_MODES.ANALYSIS); }} />}
        {viewMode === VIEW_MODES.PORTFOLIO && <PortfolioView onSelectTicker={(ticker) => { setTickerInput(ticker); runAnalysis(ticker); setViewMode(VIEW_MODES.ANALYSIS); }} />}
        {viewMode === VIEW_MODES.SCHEDULES && <SchedulesView />}
        {viewMode === VIEW_MODES.ALERTS && <AlertsView />}

        {viewMode === VIEW_MODES.ANALYSIS && (
          <>
            {!analysis && !loading && (
              <div className="flex-1 flex items-center justify-center">
                <div className="text-center">
                  <h2 className="text-2xl font-bold text-white/80 mb-2">Market Research</h2>
                  <p className="text-white/40 mb-6">Enter a ticker symbol to get started</p>
                  <div className="flex gap-2 justify-center">
                    {['AAPL', 'NVDA', 'TSLA', 'MSFT'].map((t) => (
                      <button
                        key={t}
                        onClick={() => { setTickerInput(t); runAnalysis(t); }}
                        className="px-4 py-2 rounded-lg text-[0.82rem] font-medium text-white/50 hover:text-white/70 cursor-pointer border-none"
                        style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.06)' }}
                      >
                        {t}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {showAnalysis && (
              <>
                <ThesisCard analysis={analysis} />
                <div className="mx-6 mt-4">
                  <PriceChart analysis={analysis} />
                </div>
                <SectionNav />

                {/* Narrative sections */}
                <div className="px-6 pt-4 pb-8 flex flex-col gap-3">
                  {sections.map(({ id, key, name }) => {
                    const result = agentResults[key];
                    const stance = getStance(key, result);
                    const summary = getAgentSummary(key, result);
                    const metrics = getAgentMetrics(key, result);

                    // Special sections with their own rendering
                    if (key === 'leadership') {
                      return (
                        <AnalysisSection
                          key={id}
                          id={id}
                          name={name}
                          stance={stance}
                          stanceColor={STANCE_COLORS[stance]}
                          summary={summary}
                          metrics={[]}
                          dataSource={result?.data?.data_source || 'LLM'}
                          duration={result?.duration_seconds}
                          fullContent={true}
                        >
                          <LeadershipPanel analysis={analysis} />
                        </AnalysisSection>
                      );
                    }

                    if (key === 'council') {
                      return (
                        <AnalysisSection
                          key={id}
                          id={id}
                          name={name}
                          stance="neutral"
                          stanceColor="#006fee"
                          summary="Investor council perspectives and thesis tracking"
                          metrics={[]}
                          dataSource="Council"
                          duration={null}
                          fullContent={true}
                        >
                          <CouncilPanel analysis={analysis} ticker={currentTicker} />
                        </AnalysisSection>
                      );
                    }

                    if (key === 'news') {
                      return (
                        <AnalysisSection
                          key={id}
                          id={id}
                          name={name}
                          stance={stance}
                          stanceColor={STANCE_COLORS[stance]}
                          summary={summary}
                          metrics={[]}
                          dataSource={result?.data?.data_source || 'Tavily'}
                          duration={result?.duration_seconds}
                          fullContent={true}
                        >
                          <NewsFeed analysis={analysis} />
                        </AnalysisSection>
                      );
                    }

                    if (key === 'options') {
                      return (
                        <AnalysisSection
                          key={id}
                          id={id}
                          name={name}
                          stance={stance}
                          stanceColor={STANCE_COLORS[stance]}
                          summary={summary}
                          metrics={metrics}
                          dataSource={result?.data?.data_source || 'yfinance'}
                          duration={result?.duration_seconds}
                          fullContent={true}
                        >
                          <OptionsFlow analysis={analysis} />
                        </AnalysisSection>
                      );
                    }

                    // Standard sections (fundamentals, technical, sentiment, macro)
                    return (
                      <AnalysisSection
                        key={id}
                        id={id}
                        name={name}
                        stance={stance}
                        stanceColor={STANCE_COLORS[stance]}
                        summary={summary}
                        metrics={metrics}
                        dataSource={result?.data?.data_source || ''}
                        duration={result?.duration_seconds}
                        fullContent={result?.data ? JSON.stringify(result.data, null, 2) : null}
                      />
                    );
                  })}
                </div>

                <MetaFooter analysis={analysis} />
              </>
            )}
          </>
        )}
      </main>
    </div>
  );
}
```

- [ ] **Step 3: Verify build**

Run: `cd frontend && npm run build`
Expected: May fail if HistoryView/WatchlistView/etc. don't exist yet. That's expected — those are Tasks 10-14. If only those imports fail, that's correct.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/Dashboard.jsx
git commit -m "feat: rewrite Dashboard with sidebar + scrollable narrative layout"
```

---

## Task 10: HistoryView

**Files:**
- Create: `frontend/src/components/HistoryView.jsx`

Rewritten history browser with filter pills and thesis summaries per row.

- [ ] **Step 1: Read HistoryDashboard.jsx and useHistory hook**

Read `frontend/src/components/HistoryDashboard.jsx` and `frontend/src/hooks/useHistory.js` to understand all data fetching, filtering, and state management.

- [ ] **Step 2: Create HistoryView.jsx**

Create `frontend/src/components/HistoryView.jsx`:

```jsx
import { useState, useMemo, useEffect } from 'react';
import useHistory from '../hooks/useHistory';
import { getCalibrationSummary } from '../utils/api';

const FILTERS = ['All', 'BUY', 'HOLD', 'SELL'];
const REC_COLORS = { BUY: '#17c964', SELL: '#f31260', HOLD: '#f5a524' };

function formatRelativeTime(ts) {
  if (!ts) return '';
  const diff = Date.now() - new Date(ts).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

export default function HistoryView({ onSelectAnalysis }) {
  const { tickers, tickersLoading, selectedTicker, setSelectedTicker, history, historyLoading, totalCount, hasMore, loadMore, filters, setFilters } = useHistory();
  const [recFilter, setRecFilter] = useState('All');
  const [search, setSearch] = useState('');
  const [calibration, setCalibration] = useState(null);

  useEffect(() => {
    getCalibrationSummary(180).then((r) => setCalibration(r?.data)).catch(() => {});
  }, []);

  const filteredTickers = useMemo(() => {
    let list = tickers || [];
    if (search) list = list.filter((t) => t.ticker.includes(search.toUpperCase()));
    return list;
  }, [tickers, search]);

  const filteredHistory = useMemo(() => {
    if (recFilter === 'All') return history;
    return (history || []).filter((h) => (h.recommendation || '').toUpperCase() === recFilter);
  }, [history, recFilter]);

  return (
    <div className="flex-1 p-6">
      <h2 className="text-lg font-bold text-white/90 mb-4">Analysis History</h2>

      {/* Filter bar */}
      <div className="flex items-center gap-2 mb-4">
        {FILTERS.map((f) => (
          <button
            key={f}
            onClick={() => setRecFilter(f)}
            className={`px-3 py-1.5 rounded-md text-[0.75rem] font-medium border-none cursor-pointer ${
              recFilter === f
                ? 'bg-[rgba(0,111,238,0.1)] text-[#006fee]'
                : 'bg-white/[0.04] text-white/40 hover:text-white/60'
            }`}
          >
            {f}
          </button>
        ))}
        <input
          type="text"
          placeholder="Search ticker..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="ml-4 px-3 py-1.5 rounded-md text-[0.75rem] text-white/70 placeholder:text-white/25 outline-none w-[140px]"
          style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.06)' }}
        />
        <span className="ml-auto text-[0.7rem] text-white/25">{totalCount ?? filteredHistory.length} analyses</span>
      </div>

      {/* Ticker pills */}
      {filteredTickers.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-4">
          {filteredTickers.map((t) => (
            <button
              key={t.ticker}
              onClick={() => setSelectedTicker(t.ticker)}
              className={`px-3 py-1 rounded-md text-[0.75rem] font-medium border-none cursor-pointer ${
                selectedTicker === t.ticker
                  ? 'bg-[rgba(0,111,238,0.12)] text-[#006fee]'
                  : 'bg-white/[0.03] text-white/40 hover:text-white/60'
              }`}
            >
              {t.ticker}
              <span className="ml-1.5 text-white/20">{t.analysis_count}</span>
            </button>
          ))}
        </div>
      )}

      {/* History rows */}
      <div className="flex flex-col gap-0.5">
        {historyLoading && (
          <div className="py-8 text-center text-white/30 text-[0.82rem]">Loading...</div>
        )}
        {!historyLoading && filteredHistory.length === 0 && (
          <div className="py-8 text-center text-white/30 text-[0.82rem]">No analyses found</div>
        )}
        {filteredHistory.map((item) => {
          const rec = (item.recommendation || 'HOLD').toUpperCase();
          const summary = item.executive_summary || item.synthesis || item.summary || '';
          return (
            <button
              key={item.id}
              onClick={() => onSelectAnalysis?.(item.ticker || selectedTicker)}
              className="flex items-center py-2.5 px-3 rounded-md text-[0.8rem] text-left w-full border-none cursor-pointer transition-colors hover:bg-white/[0.03]"
              style={{ background: 'rgba(255,255,255,0.02)' }}
            >
              <span className="flex-shrink-0 w-[70px] font-semibold text-white/85">{item.ticker || selectedTicker}</span>
              <span className="flex-shrink-0 w-[50px] text-[0.75rem] font-semibold" style={{ color: REC_COLORS[rec] || REC_COLORS.HOLD }}>
                {rec}
              </span>
              <span className="flex-1 text-white/45 text-[0.78rem] truncate mr-4">{summary}</span>
              <span className="flex-shrink-0 w-[80px] text-right text-[0.72rem] text-white/30 tabular-nums">
                {formatRelativeTime(item.timestamp)}
              </span>
            </button>
          );
        })}
      </div>

      {/* Load more */}
      {hasMore && !historyLoading && (
        <button
          onClick={loadMore}
          className="mt-4 w-full py-2 text-[0.78rem] text-[#006fee]/70 hover:text-[#006fee] bg-transparent border border-white/5 rounded-lg cursor-pointer"
        >
          Load more
        </button>
      )}

      {/* Calibration summary */}
      {calibration?.horizons && (
        <div className="mt-8">
          <h3 className="text-[0.85rem] font-semibold text-white/60 mb-3">Calibration (180d)</h3>
          <div className="flex gap-4">
            {Object.entries(calibration.horizons).map(([horizon, data]) => (
              <div key={horizon} className="flex-1 p-4 rounded-lg" style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)' }}>
                <div className="text-[0.65rem] text-white/30 uppercase mb-2">{horizon}</div>
                <div className="text-[1rem] font-bold tabular-nums text-white/80">
                  {((data.directional_accuracy || 0) * 100).toFixed(0)}%
                </div>
                <div className="text-[0.68rem] text-white/35">accuracy · {data.sample_size || 0} samples</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/HistoryView.jsx
git commit -m "feat: add HistoryView with filter pills and thesis summaries"
```

---

## Task 11: WatchlistView

**Files:**
- Create: `frontend/src/components/WatchlistView.jsx`

Rewritten watchlist with mini thesis card grid.

- [ ] **Step 1: Read WatchlistPanel.jsx**

Read `frontend/src/components/WatchlistPanel.jsx` to understand all watchlist API calls, batch analysis SSE, and data shapes.

- [ ] **Step 2: Create WatchlistView.jsx**

Create `frontend/src/components/WatchlistView.jsx`:

```jsx
import { useState, useEffect, useCallback, useRef } from 'react';
import { getWatchlists, getWatchlist, createWatchlist, deleteWatchlist, addTickerToWatchlist, removeTickerFromWatchlist, API_BASE_URL } from '../utils/api';

const REC_COLORS = { BUY: '#17c964', SELL: '#f31260', HOLD: '#f5a524' };
const STANCE_COLORS = { bullish: '#17c964', bearish: '#f31260', neutral: '#f5a524' };

function MiniThesisCard({ ticker, analysis, onSelect, onRemove }) {
  const rec = (analysis?.latest_analysis?.recommendation || 'HOLD').toUpperCase();
  const price = analysis?.latest_analysis?.current_price;
  const changePct = analysis?.latest_analysis?.change_percent;

  return (
    <div
      className="p-3.5 rounded-lg cursor-pointer transition-colors hover:border-white/10"
      style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)' }}
      onClick={() => onSelect?.(ticker)}
    >
      <div className="flex justify-between items-center mb-2">
        <span className="font-bold text-[0.9rem] text-white/90">{ticker}</span>
        <span className="text-[0.68rem] px-1.5 py-0.5 rounded font-medium" style={{ background: `${REC_COLORS[rec]}20`, color: REC_COLORS[rec] }}>
          {rec}
        </span>
      </div>
      {price != null && (
        <div className="text-[1rem] font-semibold tabular-nums text-white/80">${Number(price).toFixed(2)}</div>
      )}
      {changePct != null && (
        <div className="text-[0.75rem] mb-1.5" style={{ color: changePct >= 0 ? '#17c964' : '#f31260' }}>
          {changePct >= 0 ? '+' : ''}{Number(changePct).toFixed(1)}%
        </div>
      )}
      {onRemove && (
        <button
          onClick={(e) => { e.stopPropagation(); onRemove(ticker); }}
          className="text-[0.65rem] text-white/20 hover:text-[#f31260] bg-transparent border-none cursor-pointer mt-1"
        >
          Remove
        </button>
      )}
    </div>
  );
}

export default function WatchlistView({ onSelectTicker }) {
  const [watchlists, setWatchlists] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(false);
  const [newName, setNewName] = useState('');
  const [addTicker, setAddTicker] = useState('');
  const [batchRunning, setBatchRunning] = useState(false);
  const eventSourceRef = useRef(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await getWatchlists();
      const list = r?.data || [];
      setWatchlists(list);
      if (!activeId && list.length > 0) setActiveId(list[0].id);
    } catch {}
    setLoading(false);
  }, [activeId]);

  const loadDetail = useCallback(async (id) => {
    try {
      const r = await getWatchlist(id);
      setDetail(r?.data || null);
    } catch {}
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { if (activeId) loadDetail(activeId); }, [activeId, loadDetail]);

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!newName.trim()) return;
    await createWatchlist(newName.trim());
    setNewName('');
    load();
  };

  const handleDelete = async (id) => {
    await deleteWatchlist(id);
    if (activeId === id) setActiveId(null);
    load();
  };

  const handleAddTicker = async (e) => {
    e.preventDefault();
    if (!addTicker.trim() || !activeId) return;
    await addTickerToWatchlist(activeId, addTicker.trim().toUpperCase());
    setAddTicker('');
    loadDetail(activeId);
  };

  const handleRemoveTicker = async (ticker) => {
    if (!activeId) return;
    await removeTickerFromWatchlist(activeId, ticker);
    loadDetail(activeId);
  };

  const handleBatchAnalyze = () => {
    if (!activeId || batchRunning) return;
    setBatchRunning(true);
    const es = new EventSource(`${API_BASE_URL}/api/watchlists/${activeId}/analyze`);
    eventSourceRef.current = es;
    es.addEventListener('result', () => { loadDetail(activeId); });
    es.addEventListener('complete', () => { es.close(); setBatchRunning(false); });
    es.onerror = () => { es.close(); setBatchRunning(false); };
  };

  const tickers = detail?.tickers || [];
  const analyses = detail?.analyses || [];
  const analysisByTicker = Object.fromEntries(analyses.map((a) => [a.ticker, a]));

  return (
    <div className="flex-1 p-6">
      <h2 className="text-lg font-bold text-white/90 mb-4">Watchlists</h2>

      {/* Watchlist tabs */}
      <div className="flex items-center gap-2 mb-4 flex-wrap">
        {watchlists.map((w) => (
          <button
            key={w.id}
            onClick={() => setActiveId(w.id)}
            className={`px-3 py-1.5 rounded-md text-[0.75rem] font-medium border-none cursor-pointer ${
              activeId === w.id ? 'bg-[rgba(0,111,238,0.1)] text-[#006fee]' : 'bg-white/[0.04] text-white/40'
            }`}
          >
            {w.name}
          </button>
        ))}
        <form onSubmit={handleCreate} className="flex gap-1.5 ml-2">
          <input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="+ New"
            className="px-2 py-1 rounded text-[0.72rem] text-white/60 placeholder:text-white/25 outline-none w-[80px]"
            style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.06)' }}
          />
        </form>
      </div>

      {activeId && (
        <>
          {/* Add ticker + actions */}
          <div className="flex items-center gap-2 mb-4">
            <form onSubmit={handleAddTicker} className="flex gap-1.5">
              <input
                value={addTicker}
                onChange={(e) => setAddTicker(e.target.value.toUpperCase())}
                placeholder="Add ticker..."
                maxLength={5}
                className="px-3 py-1.5 rounded-md text-[0.78rem] text-white/70 placeholder:text-white/25 outline-none w-[120px]"
                style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.06)' }}
              />
              <button type="submit" className="px-3 py-1.5 rounded-md text-[0.78rem] font-medium text-white/60 border-none cursor-pointer" style={{ background: 'rgba(255,255,255,0.06)' }}>
                Add
              </button>
            </form>
            <button
              onClick={handleBatchAnalyze}
              disabled={batchRunning || tickers.length === 0}
              className="px-3 py-1.5 rounded-md text-[0.78rem] font-medium text-white border-none cursor-pointer disabled:opacity-40"
              style={{ background: '#006fee' }}
            >
              {batchRunning ? 'Analyzing...' : 'Re-analyze All'}
            </button>
            <button
              onClick={() => handleDelete(activeId)}
              className="ml-auto text-[0.72rem] text-white/25 hover:text-[#f31260] bg-transparent border-none cursor-pointer"
            >
              Delete watchlist
            </button>
          </div>

          {/* Ticker grid */}
          <div className="grid grid-cols-3 gap-3 xl:grid-cols-4">
            {tickers.map((t) => (
              <MiniThesisCard
                key={t.ticker}
                ticker={t.ticker}
                analysis={analysisByTicker[t.ticker]}
                onSelect={onSelectTicker}
                onRemove={handleRemoveTicker}
              />
            ))}
            {tickers.length === 0 && (
              <div className="col-span-3 py-8 text-center text-white/30 text-[0.82rem]">
                No tickers in this watchlist. Add one above.
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/WatchlistView.jsx
git commit -m "feat: add WatchlistView with mini thesis card grid"
```

---

## Task 12: PortfolioView

**Files:**
- Create: `frontend/src/components/PortfolioView.jsx`

Rewritten portfolio with summary strip and holdings table.

- [ ] **Step 1: Read PortfolioPanel.jsx**

Read `frontend/src/components/PortfolioPanel.jsx` to understand all portfolio API calls, form state, and data shapes.

- [ ] **Step 2: Create PortfolioView.jsx**

Create `frontend/src/components/PortfolioView.jsx`:

```jsx
import { useState, useEffect, useCallback } from 'react';
import { getPortfolio, updatePortfolioProfile, createPortfolioHolding, updatePortfolioHolding, deletePortfolioHolding } from '../utils/api';

const EMPTY_HOLDING = { ticker: '', shares: '', avg_cost: '', sector: '' };

export default function PortfolioView({ onSelectTicker }) {
  const [portfolio, setPortfolio] = useState(null);
  const [loading, setLoading] = useState(false);
  const [holdingForm, setHoldingForm] = useState(EMPTY_HOLDING);
  const [editingId, setEditingId] = useState(null);
  const [showForm, setShowForm] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await getPortfolio();
      setPortfolio(r?.data || null);
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    const data = {
      ticker: holdingForm.ticker.toUpperCase(),
      shares: Number(holdingForm.shares),
      avg_cost: Number(holdingForm.avg_cost),
      sector: holdingForm.sector || undefined,
    };
    if (editingId) await updatePortfolioHolding(editingId, data);
    else await createPortfolioHolding(data);
    setHoldingForm(EMPTY_HOLDING);
    setEditingId(null);
    setShowForm(false);
    load();
  };

  const handleEdit = (h) => {
    setHoldingForm({ ticker: h.ticker, shares: String(h.shares), avg_cost: String(h.avg_cost), sector: h.sector || '' });
    setEditingId(h.id);
    setShowForm(true);
  };

  const handleDelete = async (id) => {
    await deletePortfolioHolding(id);
    load();
  };

  const snapshot = portfolio?.snapshot || {};
  const holdings = snapshot.by_ticker || portfolio?.holdings || [];
  const totalValue = snapshot.total_market_value || holdings.reduce((s, h) => s + (h.market_value || 0), 0);
  const sectorBreakdown = snapshot.by_sector || [];
  const topSector = sectorBreakdown[0];

  return (
    <div className="flex-1 p-6">
      <h2 className="text-lg font-bold text-white/90 mb-4">Portfolio</h2>

      {/* Summary strip */}
      <div className="flex gap-6 mb-6 pb-4" style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
        <div>
          <div className="text-[0.65rem] text-white/30 uppercase tracking-wide">Total Value</div>
          <div className="text-[1.3rem] font-bold tabular-nums text-white/90">${totalValue.toLocaleString()}</div>
        </div>
        <div>
          <div className="text-[0.65rem] text-white/30 uppercase tracking-wide">Holdings</div>
          <div className="text-[1.3rem] font-bold text-white/90">{holdings.length}</div>
        </div>
        {topSector && (
          <div>
            <div className="text-[0.65rem] text-white/30 uppercase tracking-wide">Top Sector</div>
            <div className="text-[1.3rem] font-bold text-[#f5a524]">
              {Math.round(topSector.exposure_pct || 0)}% {topSector.sector}
            </div>
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2 mb-4">
        <button
          onClick={() => { setShowForm(!showForm); setEditingId(null); setHoldingForm(EMPTY_HOLDING); }}
          className="px-3 py-1.5 rounded-md text-[0.78rem] font-medium text-white border-none cursor-pointer"
          style={{ background: '#006fee' }}
        >
          {showForm ? 'Cancel' : '+ Add Holding'}
        </button>
      </div>

      {/* Add/edit form */}
      {showForm && (
        <form onSubmit={handleSubmit} className="flex gap-2 mb-4 p-4 rounded-lg" style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)' }}>
          <input value={holdingForm.ticker} onChange={(e) => setHoldingForm({ ...holdingForm, ticker: e.target.value })} placeholder="Ticker" maxLength={5}
            className="px-3 py-1.5 rounded-md text-[0.78rem] text-white/70 placeholder:text-white/25 outline-none w-[80px]" style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.06)' }} />
          <input value={holdingForm.shares} onChange={(e) => setHoldingForm({ ...holdingForm, shares: e.target.value })} placeholder="Shares" type="number"
            className="px-3 py-1.5 rounded-md text-[0.78rem] text-white/70 placeholder:text-white/25 outline-none w-[80px]" style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.06)' }} />
          <input value={holdingForm.avg_cost} onChange={(e) => setHoldingForm({ ...holdingForm, avg_cost: e.target.value })} placeholder="Avg Cost" type="number" step="0.01"
            className="px-3 py-1.5 rounded-md text-[0.78rem] text-white/70 placeholder:text-white/25 outline-none w-[100px]" style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.06)' }} />
          <input value={holdingForm.sector} onChange={(e) => setHoldingForm({ ...holdingForm, sector: e.target.value })} placeholder="Sector"
            className="px-3 py-1.5 rounded-md text-[0.78rem] text-white/70 placeholder:text-white/25 outline-none w-[100px]" style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.06)' }} />
          <button type="submit" className="px-4 py-1.5 rounded-md text-[0.78rem] font-medium text-white border-none cursor-pointer" style={{ background: '#006fee' }}>
            {editingId ? 'Update' : 'Add'}
          </button>
        </form>
      )}

      {/* Holdings table */}
      <div className="flex flex-col gap-0.5">
        {holdings.map((h) => {
          const returnPct = h.avg_cost > 0 ? ((h.market_value / (h.shares * h.avg_cost)) - 1) * 100 : 0;
          return (
            <div key={h.id || h.ticker} className="flex items-center py-2 px-3 rounded-md text-[0.8rem]" style={{ background: 'rgba(255,255,255,0.02)' }}>
              <button onClick={() => onSelectTicker?.(h.ticker)} className="flex-shrink-0 w-[60px] font-semibold text-white/85 bg-transparent border-none cursor-pointer text-left text-[0.8rem] hover:text-[#006fee]">
                {h.ticker}
              </button>
              <span className="flex-shrink-0 w-[60px] tabular-nums text-white/50">{h.shares}</span>
              <span className="flex-shrink-0 w-[90px] tabular-nums text-white/70">${(h.market_value || 0).toLocaleString()}</span>
              <span className="flex-shrink-0 w-[70px] tabular-nums" style={{ color: returnPct >= 0 ? '#17c964' : '#f31260' }}>
                {returnPct >= 0 ? '+' : ''}{returnPct.toFixed(1)}%
              </span>
              <span className="flex-1 text-white/30 text-[0.72rem]">{h.sector || ''}</span>
              <button onClick={() => handleEdit(h)} className="text-[0.68rem] text-white/25 hover:text-white/60 bg-transparent border-none cursor-pointer mr-2">Edit</button>
              <button onClick={() => handleDelete(h.id)} className="text-[0.68rem] text-white/25 hover:text-[#f31260] bg-transparent border-none cursor-pointer">Delete</button>
            </div>
          );
        })}
        {holdings.length === 0 && !loading && (
          <div className="py-8 text-center text-white/30 text-[0.82rem]">No holdings. Add one above.</div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Verify build and commit**

Run: `cd frontend && npm run build`

```bash
git add frontend/src/components/PortfolioView.jsx
git commit -m "feat: add PortfolioView with summary strip and holdings table"
```

---

## Task 13: SchedulesView

**Files:**
- Create: `frontend/src/components/SchedulesView.jsx`

- [ ] **Step 1: Read SchedulePanel.jsx**

Read `frontend/src/components/SchedulePanel.jsx` to understand schedule API calls and data shapes.

- [ ] **Step 2: Create SchedulesView.jsx**

Create `frontend/src/components/SchedulesView.jsx`:

```jsx
import { useState, useEffect, useCallback } from 'react';
import { getSchedules, createSchedule, updateSchedule, deleteSchedule, getScheduleWithRuns } from '../utils/api';

function formatInterval(minutes) {
  if (minutes < 60) return `Every ${minutes}m`;
  if (minutes < 1440) return `Every ${Math.round(minutes / 60)}h`;
  return `Every ${Math.round(minutes / 1440)}d`;
}

function formatRelativeTime(ts) {
  if (!ts) return 'Never';
  const diff = Date.now() - new Date(ts).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 0) return 'Upcoming';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

export default function SchedulesView() {
  const [schedules, setSchedules] = useState([]);
  const [loading, setLoading] = useState(false);
  const [ticker, setTicker] = useState('');
  const [interval, setInterval_] = useState('60');
  const [expandedId, setExpandedId] = useState(null);
  const [runs, setRuns] = useState([]);

  const load = useCallback(async () => {
    setLoading(true);
    try { const r = await getSchedules(); setSchedules(r?.data || []); } catch {}
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!ticker.trim()) return;
    await createSchedule(ticker.trim().toUpperCase(), Number(interval));
    setTicker('');
    load();
  };

  const handleToggle = async (id, enabled) => {
    await updateSchedule(id, { enabled: !enabled });
    load();
  };

  const handleDelete = async (id) => {
    await deleteSchedule(id);
    load();
  };

  const handleExpand = async (id) => {
    if (expandedId === id) { setExpandedId(null); return; }
    setExpandedId(id);
    try {
      const r = await getScheduleWithRuns(id);
      setRuns(r?.data?.runs || []);
    } catch { setRuns([]); }
  };

  return (
    <div className="flex-1 p-6">
      <h2 className="text-lg font-bold text-white/90 mb-4">Schedules</h2>

      {/* Create form */}
      <form onSubmit={handleCreate} className="flex gap-2 mb-6">
        <input value={ticker} onChange={(e) => setTicker(e.target.value.toUpperCase())} placeholder="Ticker" maxLength={5}
          className="px-3 py-2 rounded-lg text-[0.82rem] text-white/70 placeholder:text-white/25 outline-none w-[100px]"
          style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.06)' }} />
        <select value={interval} onChange={(e) => setInterval_(e.target.value)}
          className="px-3 py-2 rounded-lg text-[0.82rem] text-white/70 outline-none"
          style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.06)' }}>
          <option value="30">Every 30m</option>
          <option value="60">Every 1h</option>
          <option value="360">Every 6h</option>
          <option value="720">Every 12h</option>
          <option value="1440">Daily</option>
          <option value="10080">Weekly</option>
        </select>
        <button type="submit" className="px-4 py-2 rounded-lg text-[0.82rem] font-medium text-white border-none cursor-pointer" style={{ background: '#006fee' }}>
          Create Schedule
        </button>
      </form>

      {/* Schedule cards */}
      <div className="flex flex-col gap-3">
        {schedules.map((s) => (
          <div key={s.id} className="rounded-lg p-4" style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)' }}>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-2 h-2 rounded-full" style={{ background: s.enabled ? '#17c964' : 'rgba(255,255,255,0.15)' }} />
                <span className="font-semibold text-[0.9rem] text-white/85">{s.ticker}</span>
                <span className="text-[0.75rem] text-white/40">{formatInterval(s.interval_minutes)}</span>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-[0.7rem] text-white/25">Last: {formatRelativeTime(s.last_run_at)}</span>
                <button onClick={() => handleToggle(s.id, s.enabled)} className="text-[0.72rem] text-white/40 hover:text-white/70 bg-transparent border-none cursor-pointer">
                  {s.enabled ? 'Pause' : 'Resume'}
                </button>
                <button onClick={() => handleExpand(s.id)} className="text-[0.72rem] text-[#006fee]/70 hover:text-[#006fee] bg-transparent border-none cursor-pointer">
                  {expandedId === s.id ? 'Hide runs' : 'Show runs'}
                </button>
                <button onClick={() => handleDelete(s.id)} className="text-[0.72rem] text-white/25 hover:text-[#f31260] bg-transparent border-none cursor-pointer">
                  Delete
                </button>
              </div>
            </div>
            {expandedId === s.id && runs.length > 0 && (
              <div className="mt-3 pt-3 flex flex-col gap-1" style={{ borderTop: '1px solid rgba(255,255,255,0.04)' }}>
                {runs.slice(0, 10).map((run, i) => (
                  <div key={i} className="flex items-center gap-3 text-[0.75rem] text-white/40 px-2 py-1">
                    <div className="w-1.5 h-1.5 rounded-full" style={{ background: run.success ? '#17c964' : '#f31260' }} />
                    <span className="capitalize">{run.recommendation || '—'}</span>
                    <span className="ml-auto tabular-nums">{formatRelativeTime(run.completed_at || run.timestamp)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
        {schedules.length === 0 && !loading && (
          <div className="py-8 text-center text-white/30 text-[0.82rem]">No schedules. Create one above.</div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Verify build and commit**

Run: `cd frontend && npm run build`

```bash
git add frontend/src/components/SchedulesView.jsx
git commit -m "feat: add SchedulesView with card layout and run history"
```

---

## Task 14: AlertsView

**Files:**
- Create: `frontend/src/components/AlertsView.jsx`

- [ ] **Step 1: Read AlertPanel.jsx**

Read `frontend/src/components/AlertPanel.jsx` to understand alert API calls and data shapes.

- [ ] **Step 2: Create AlertsView.jsx**

Create `frontend/src/components/AlertsView.jsx`:

```jsx
import { useState, useEffect, useCallback } from 'react';
import { getAlertRules, createAlertRule, updateAlertRule, deleteAlertRule, getAlertNotifications, acknowledgeAlert } from '../utils/api';

const RULE_TYPES = [
  { value: 'price_above', label: 'Price Above' },
  { value: 'price_below', label: 'Price Below' },
  { value: 'recommendation_change', label: 'Rec. Change' },
  { value: 'sentiment_shift', label: 'Sentiment Shift' },
  { value: 'volume_spike', label: 'Volume Spike' },
];

function formatRelativeTime(ts) {
  if (!ts) return '';
  const diff = Date.now() - new Date(ts).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

export default function AlertsView() {
  const [rules, setRules] = useState([]);
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(false);
  const [ticker, setTicker] = useState('');
  const [ruleType, setRuleType] = useState('price_below');
  const [threshold, setThreshold] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [rulesRes, notifsRes] = await Promise.all([getAlertRules(), getAlertNotifications()]);
      setRules(rulesRes?.data || []);
      setNotifications(notifsRes?.data || []);
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!ticker.trim() || !threshold) return;
    await createAlertRule(ticker.trim().toUpperCase(), ruleType, Number(threshold));
    setTicker('');
    setThreshold('');
    load();
  };

  const handleToggle = async (id, enabled) => {
    await updateAlertRule(id, { enabled: !enabled });
    load();
  };

  const handleDelete = async (id) => {
    await deleteAlertRule(id);
    load();
  };

  const handleAcknowledge = async (id) => {
    await acknowledgeAlert(id);
    load();
  };

  return (
    <div className="flex-1 p-6">
      <h2 className="text-lg font-bold text-white/90 mb-4">Alerts</h2>

      {/* Create form */}
      <form onSubmit={handleCreate} className="flex gap-2 mb-6">
        <input value={ticker} onChange={(e) => setTicker(e.target.value.toUpperCase())} placeholder="Ticker" maxLength={5}
          className="px-3 py-2 rounded-lg text-[0.82rem] text-white/70 placeholder:text-white/25 outline-none w-[80px]"
          style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.06)' }} />
        <select value={ruleType} onChange={(e) => setRuleType(e.target.value)}
          className="px-3 py-2 rounded-lg text-[0.82rem] text-white/70 outline-none"
          style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.06)' }}>
          {RULE_TYPES.map((rt) => <option key={rt.value} value={rt.value}>{rt.label}</option>)}
        </select>
        <input value={threshold} onChange={(e) => setThreshold(e.target.value)} placeholder="Threshold" type="number" step="0.01"
          className="px-3 py-2 rounded-lg text-[0.82rem] text-white/70 placeholder:text-white/25 outline-none w-[100px]"
          style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.06)' }} />
        <button type="submit" className="px-4 py-2 rounded-lg text-[0.82rem] font-medium text-white border-none cursor-pointer" style={{ background: '#006fee' }}>
          Create Alert
        </button>
      </form>

      {/* Active rules */}
      <h3 className="text-[0.85rem] font-semibold text-white/60 mb-3">Active Rules</h3>
      <div className="flex flex-col gap-2 mb-8">
        {rules.map((rule) => (
          <div key={rule.id} className="flex items-center justify-between p-3 rounded-lg" style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)' }}>
            <div className="flex items-center gap-3">
              <div className="w-2 h-2 rounded-full" style={{ background: rule.enabled ? '#17c964' : 'rgba(255,255,255,0.15)' }} />
              <span className="text-[0.82rem] font-medium text-white/80">{rule.ticker}</span>
              <span className="text-[0.75rem] text-white/40">
                {RULE_TYPES.find((t) => t.value === rule.rule_type)?.label || rule.rule_type}
              </span>
              <span className="text-[0.75rem] text-white/50 tabular-nums">{rule.threshold}</span>
            </div>
            <div className="flex items-center gap-3">
              <button onClick={() => handleToggle(rule.id, rule.enabled)} className="text-[0.72rem] text-white/40 hover:text-white/70 bg-transparent border-none cursor-pointer">
                {rule.enabled ? 'Disable' : 'Enable'}
              </button>
              <button onClick={() => handleDelete(rule.id)} className="text-[0.72rem] text-white/25 hover:text-[#f31260] bg-transparent border-none cursor-pointer">
                Delete
              </button>
            </div>
          </div>
        ))}
        {rules.length === 0 && <div className="py-4 text-center text-white/25 text-[0.78rem]">No alert rules</div>}
      </div>

      {/* Recent triggers */}
      <h3 className="text-[0.85rem] font-semibold text-white/60 mb-3">Recent Triggers</h3>
      <div className="flex flex-col gap-2">
        {notifications.map((n) => {
          const isPrice = n.trigger_context?.rule_type?.includes('price');
          const borderColor = isPrice ? '#f31260' : '#f5a524';
          return (
            <div
              key={n.id}
              className="p-3 rounded-lg"
              style={{
                background: `${borderColor}08`,
                borderLeft: `3px solid ${borderColor}`,
                opacity: n.acknowledged ? 0.5 : 1,
              }}
            >
              <div className="flex justify-between items-start">
                <div>
                  <div className="text-[0.82rem] font-medium text-white/80">{n.ticker}: {n.message}</div>
                  <div className="text-[0.7rem] text-white/35 mt-0.5">{formatRelativeTime(n.created_at)}</div>
                </div>
                {!n.acknowledged && (
                  <button onClick={() => handleAcknowledge(n.id)} className="text-[0.68rem] text-white/30 hover:text-white/60 bg-transparent border-none cursor-pointer">
                    Dismiss
                  </button>
                )}
              </div>
            </div>
          );
        })}
        {notifications.length === 0 && <div className="py-4 text-center text-white/25 text-[0.78rem]">No recent triggers</div>}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Verify build and commit**

Run: `cd frontend && npm run build`

```bash
git add frontend/src/components/AlertsView.jsx
git commit -m "feat: add AlertsView with rules and trigger cards"
```

---

## Task 15: Delete Old Components

**Files:**
- Delete: `frontend/src/components/ContentHeader.jsx`
- Delete: `frontend/src/components/Recommendation.jsx`
- Delete: `frontend/src/components/AnalysisTabs.jsx`
- Delete: `frontend/src/components/AgentPipelineBar.jsx`
- Delete: `frontend/src/components/Summary.jsx`
- Delete: `frontend/src/components/ScenarioPanel.jsx`
- Delete: `frontend/src/components/MacroSnapshot.jsx`
- Delete: `frontend/src/components/CalibrationCard.jsx`
- Delete: `frontend/src/components/DiagnosticsPanel.jsx`
- Delete: `frontend/src/components/HistoryDashboard.jsx`
- Delete: `frontend/src/components/WatchlistPanel.jsx`
- Delete: `frontend/src/components/PortfolioPanel.jsx`
- Delete: `frontend/src/components/SchedulePanel.jsx`
- Delete: `frontend/src/components/AlertPanel.jsx`

- [ ] **Step 1: Verify no remaining imports of old components**

Search all .jsx and .js files for imports of the deleted components:

Run: `cd frontend && grep -r "import.*from.*\(ContentHeader\|Recommendation\|AnalysisTabs\|AgentPipelineBar\|Summary\|ScenarioPanel\|MacroSnapshot\|CalibrationCard\|DiagnosticsPanel\|HistoryDashboard\|WatchlistPanel\|PortfolioPanel\|SchedulePanel\|AlertPanel\)" src/ --include="*.jsx" --include="*.js"`

Expected: No matches (all references should have been replaced in Tasks 2-14). If any remain, update the importing file to remove the reference before deleting.

- [ ] **Step 2: Delete old files**

```bash
cd frontend/src/components
rm -f ContentHeader.jsx Recommendation.jsx AnalysisTabs.jsx AgentPipelineBar.jsx Summary.jsx ScenarioPanel.jsx MacroSnapshot.jsx CalibrationCard.jsx DiagnosticsPanel.jsx HistoryDashboard.jsx WatchlistPanel.jsx PortfolioPanel.jsx SchedulePanel.jsx AlertPanel.jsx
```

- [ ] **Step 3: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no missing module errors.

- [ ] **Step 4: Commit**

```bash
git add -A frontend/src/components/
git commit -m "chore: remove old components replaced by redesign"
```

---

## Task 16: Visual Verification & Polish

**Files:** Various — fix any issues found during visual review.

- [ ] **Step 1: Start the frontend dev server**

Run: `cd frontend && npm run dev`
Expected: Dev server starts on :5173.

- [ ] **Step 2: Start the backend**

Run (separate terminal): `source venv/bin/activate && python run.py`
Expected: Backend on :8000.

- [ ] **Step 3: Visual verification checklist**

Open http://localhost:5173 in a browser and verify:

1. **Welcome state:** Sidebar (220px, labeled), search bar, quick-start ticker buttons centered
2. **Run analysis (AAPL):** Agent dots animate → thesis card appears with verdict/evidence split → chart renders with SMA legend → section nav sticks on scroll → analysis sections render with stance badges and metrics → meta footer at bottom
3. **Section nav:** Click pills to jump between sections, active state highlights on scroll
4. **Expand sections:** "Show full analysis" expands with animation, "Hide details" collapses
5. **SMA toggles:** Click SMA legend items to show/hide lines on chart
6. **Diagnostics:** Click "View Diagnostics →" in footer, slide-over opens from right with agent timing
7. **Secondary views:** Click each sidebar nav item: History (filter pills, table rows), Watchlist (grid of mini cards), Portfolio (summary strip, holdings table), Schedules (cards), Alerts (rules + triggers)
8. **Recent tickers:** After running analysis, sidebar "Recent" section shows the ticker with recommendation

- [ ] **Step 4: Fix any visual issues found**

Adjust spacing, colors, font sizes, or layout issues found during the visual review. Common fixes:
- Sidebar overlap with main content
- Sticky header z-index conflicts
- Missing data graceful fallbacks (null checks)
- Section nav scroll offset miscalculation

- [ ] **Step 5: Final build check**

Run: `cd frontend && npm run build`
Expected: Build succeeds.

- [ ] **Step 6: Commit any fixes**

```bash
git add frontend/src/
git commit -m "fix: visual polish and layout adjustments from review"
```
