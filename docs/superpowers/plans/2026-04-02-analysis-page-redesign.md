# Analysis Page Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure the analysis page layout — new spacing tokens, pill tabs, composite sections (Company Overview, Technicals & Options), macro standalone page, remove all collapsibles, always-visible council scenarios.

**Architecture:** Component Restructure approach — establish spacing tokens first, then build new composite components, rework Dashboard section ordering and navigation, add Macro as a standalone page with sidebar grouping.

**Tech Stack:** React, Tailwind CSS v4, Framer Motion, lightweight-charts

---

### Task 1: Add Spacing Tokens to index.css

**Files:**
- Modify: `frontend/src/index.css:52-135`

- [ ] **Step 1: Add spacing custom properties**

In `frontend/src/index.css`, add inside the `:root` block (after line 135, before the closing `}`):

```css
  /* Spacing tokens */
  --space-card-gap: 20px;
  --space-section-gap: 32px;
  --space-card-padding: 20px;
  --space-metrics-gap: 16px;
```

- [ ] **Step 2: Verify the dev server picks up the changes**

Run: `cd frontend && npm run dev`
Expected: Dev server starts without CSS errors. Open browser, inspect any element — verify the custom properties are available in `:root`.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/index.css
git commit -m "feat(frontend): add spacing design tokens to CSS custom properties"
```

---

### Task 2: Rework SectionNav to Pill Tabs

**Files:**
- Modify: `frontend/src/components/SectionNav.jsx`

- [ ] **Step 1: Update the SECTIONS array**

Replace the entire `SECTIONS` constant at the top of `SectionNav.jsx` with:

```jsx
const SECTIONS = [
  { id: 'section-company_overview', label: 'Company Overview' },
  { id: 'section-earnings', label: 'Earnings' },
  { id: 'section-earnings_review', label: 'Earnings Review' },
  { id: 'section-thesis', label: 'Thesis' },
  { id: 'section-risk_diff', label: 'Risk Analysis' },
  { id: 'section-technicals_options', label: 'Technicals & Options' },
  { id: 'section-sentiment', label: 'Sentiment' },
  { id: 'section-news', label: 'News' },
  { id: 'section-leadership', label: 'Leadership' },
  { id: 'section-council', label: 'Council' },
];
```

- [ ] **Step 2: Restyle the nav container and buttons as pills**

Replace the return JSX in `SectionNav` with:

```jsx
  return (
    <div
      className="sticky z-[35] flex px-6 py-3 overflow-x-auto"
      style={{
        top: `${searchBarHeight}px`,
        background: 'rgba(9,9,11,0.9)',
        backdropFilter: 'blur(8px)',
        borderBottom: '1px solid rgba(255,255,255,0.04)',
        gap: '16px',
      }}
    >
      {SECTIONS.map(({ id, label }) => {
        const isActive = activeId === id;
        return (
          <button
            key={id}
            onClick={() => handleClick(id)}
            className="border-none cursor-pointer whitespace-nowrap transition-all duration-150"
            style={{
              padding: '10px 20px',
              borderRadius: '9999px',
              fontSize: '0.8rem',
              fontWeight: 500,
              background: isActive ? 'var(--accent-blue)' : 'transparent',
              color: isActive ? '#ffffff' : 'var(--text-muted)',
              border: isActive ? 'none' : '1px solid rgba(255,255,255,0.06)',
            }}
            onMouseEnter={(e) => {
              if (!isActive) {
                e.target.style.background = 'rgba(255,255,255,0.06)';
                e.target.style.color = 'var(--text-secondary)';
              }
            }}
            onMouseLeave={(e) => {
              if (!isActive) {
                e.target.style.background = 'transparent';
                e.target.style.color = 'var(--text-muted)';
              }
            }}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
```

- [ ] **Step 3: Verify in browser**

Run: `cd frontend && npm run dev`
Expected: Pill-shaped tabs with 16px gaps, active tab has blue fill, inactive tabs have subtle border, hover shows background shift. 10 tabs total.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/SectionNav.jsx
git commit -m "feat(frontend): rework SectionNav to pill-style tabs with new section list"
```

---

### Task 3: Remove Collapsibles from AnalysisSection

**Files:**
- Modify: `frontend/src/components/AnalysisSection.jsx`

- [ ] **Step 1: Remove expand/collapse state and button**

Replace the entire `AnalysisSection.jsx` content with:

```jsx
import { forwardRef } from 'react';

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
  const config = STANCE_CONFIG[stance] || STANCE_CONFIG.neutral;

  return (
    <div
      ref={ref}
      id={id}
      className="rounded-[10px]"
      style={{
        padding: 'var(--space-card-padding, 20px)',
        background: 'rgba(255,255,255,0.02)',
        border: '1px solid rgba(255,255,255,0.06)',
      }}
    >
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

      {summary && (
        <div className="text-[0.88rem] text-white/65 leading-relaxed mb-3">{summary}</div>
      )}

      {metrics && metrics.length > 0 && (
        <div className="flex gap-6 mb-2.5">
          {metrics.map((m, i) => (
            <MetricItem key={i} label={m.label} value={m.value} color={m.color} />
          ))}
        </div>
      )}

      {(fullContent || children) && (
        <div className="mt-3 pt-3" style={{ borderTop: '1px solid rgba(255,255,255,0.05)' }}>
          {children || (
            <div className="text-[0.82rem] text-white/55 leading-relaxed whitespace-pre-wrap">
              {typeof fullContent === 'string' ? fullContent : JSON.stringify(fullContent, null, 2)}
            </div>
          )}
        </div>
      )}
    </div>
  );
});

export default AnalysisSection;
```

Key changes: removed `useState`, `motion`, `AnimatePresence` imports; removed `expanded` state; removed toggle button; content always renders fully.

- [ ] **Step 2: Verify in browser**

Expected: All sections that use `AnalysisSection` wrapper (Sentiment, News via wrapper) now show full content without needing to click "Show full analysis".

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/AnalysisSection.jsx
git commit -m "feat(frontend): remove collapsible toggle from AnalysisSection, always show full content"
```

---

### Task 4: Update PriceChart — All SMAs Visible, 1Y Default

**Files:**
- Modify: `frontend/src/components/PriceChart.jsx:17-23`

- [ ] **Step 1: Set all SMAs to defaultVisible: true**

Replace the `SMA_CONFIG` array (lines 17-23) with:

```jsx
const SMA_CONFIG = [
  { period: 9, color: '#ef4444', label: 'SMA 9', defaultVisible: true },
  { period: 20, color: '#f59e0b', label: 'SMA 20', defaultVisible: true },
  { period: 50, color: '#22c55e', label: 'SMA 50', defaultVisible: true },
  { period: 100, color: '#3b82f6', label: 'SMA 100', defaultVisible: true },
  { period: 200, color: '#a855f7', label: 'SMA 200', defaultVisible: true },
];
```

- [ ] **Step 2: Verify the backend returns sufficient data**

Check that the market agent's price history request returns at least 1 year of daily data. The chart uses `chart.timeScale().fitContent()` which auto-fits to whatever data is available. If the backend already returns ~1Y of data, no change needed. If it returns less, this is a separate backend task — note it and move on.

- [ ] **Step 3: Verify in browser**

Expected: All 5 SMA lines visible on chart load. Toggle buttons still work to hide/show individual lines.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/PriceChart.jsx
git commit -m "feat(frontend): show all 5 SMA lines by default on price chart"
```

---

### Task 5: Create CompanyOverview Component

**Files:**
- Create: `frontend/src/components/CompanyOverview.jsx`

- [ ] **Step 1: Create the component file**

Create `frontend/src/components/CompanyOverview.jsx`:

```jsx
/**
 * CompanyOverview - Composite section combining Company Description,
 * Narrative, and Fundamentals into stacked glass cards.
 */

import React from 'react';
import { motion as Motion } from 'framer-motion';
import NarrativePanel from './NarrativePanel';

const fadeUp = {
  hidden: { opacity: 0, y: 12 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.22, 1, 0.36, 1] } },
};

// ─── Metric Card ────────────────────────────────────────────────────────────

const MetricCard = ({ label, value, delta }) => (
  <div
    className="bg-dark-inset rounded-lg border border-white/[0.04] hover:border-white/[0.08] transition-colors"
    style={{ padding: 'var(--space-card-padding, 20px)' }}
  >
    <div className="text-[11px] uppercase tracking-wider font-medium" style={{ color: 'var(--text-muted)' }}>
      {label}
    </div>
    <div className="text-lg font-bold mt-1 font-mono tabular-nums" style={{ color: 'var(--text-primary)' }}>
      {value}
    </div>
    {delta && (
      <div
        className="text-[11px] mt-0.5 font-mono"
        style={{ color: delta.startsWith('+') || delta.startsWith('▲') ? 'var(--accent-green)' : 'var(--accent-red)' }}
      >
        {delta}
      </div>
    )}
  </div>
);

// ─── Description Card ───────────────────────────────────────────────────────

const DescriptionCard = ({ data }) => {
  const description = data?.company_overview || data?.description || data?.company_description || null;
  if (!description) return null;

  return (
    <div className="glass-card rounded-xl" style={{ padding: 'var(--space-card-padding, 20px)' }}>
      <div className="text-sm font-semibold mb-3 flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
        <span style={{ color: 'var(--accent-blue)' }}>◆</span> Company Description
      </div>
      <p className="text-[0.88rem] leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
        {description}
      </p>
    </div>
  );
};

// ─── Fundamentals Metrics Card ──────────────────────────────────────────────

const FundamentalsCard = ({ data }) => {
  if (!data) return null;

  const metrics = [
    data.pe_ratio != null && { label: 'P/E Ratio', value: Number(data.pe_ratio).toFixed(1) },
    data.revenue_growth != null && { label: 'Rev Growth', value: `${(data.revenue_growth * 100).toFixed(1)}%` },
    (data.profit_margin ?? data.net_margin) != null && {
      label: 'Net Margin',
      value: `${((data.profit_margin ?? data.net_margin) * 100).toFixed(1)}%`,
    },
    (data.health_score ?? data.fundamental_health_score) != null && {
      label: 'Health Score',
      value: `${data.health_score ?? data.fundamental_health_score}/100`,
    },
    data.market_cap != null && {
      label: 'Market Cap',
      value: formatMarketCap(data.market_cap),
    },
    data.eps != null && { label: 'EPS', value: `$${Number(data.eps).toFixed(2)}` },
    data.dividend_yield != null && {
      label: 'Div Yield',
      value: `${(data.dividend_yield * 100).toFixed(2)}%`,
    },
  ].filter(Boolean);

  const summary = data.analysis || data.summary || null;

  return (
    <div className="glass-card rounded-xl" style={{ padding: 'var(--space-card-padding, 20px)' }}>
      <div className="text-sm font-semibold mb-4 flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
        <span style={{ color: 'var(--accent-green)' }}>◆</span> Fundamentals
      </div>

      {metrics.length > 0 && (
        <div
          className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4"
          style={{ gap: 'var(--space-metrics-gap, 16px)', marginBottom: summary ? '20px' : '0' }}
        >
          {metrics.map((m, i) => (
            <MetricCard key={i} label={m.label} value={m.value} />
          ))}
        </div>
      )}

      {summary && (
        <div className="text-[0.88rem] leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
          {formatParagraphs(summary)}
        </div>
      )}
    </div>
  );
};

// ─── Helpers ────────────────────────────────────────────────────────────────

function formatMarketCap(value) {
  if (value == null) return 'N/A';
  const num = Number(value);
  if (num >= 1e12) return `$${(num / 1e12).toFixed(2)}T`;
  if (num >= 1e9) return `$${(num / 1e9).toFixed(2)}B`;
  if (num >= 1e6) return `$${(num / 1e6).toFixed(0)}M`;
  return `$${num.toLocaleString()}`;
}

function formatParagraphs(text) {
  if (!text) return null;
  const paragraphs = text.split(/\n\n+/).filter(Boolean);
  if (paragraphs.length <= 1) return text;
  return paragraphs.map((p, i) => (
    <p key={i} className={i > 0 ? 'mt-3' : ''}>{p}</p>
  ));
}

// ─── Main Component ─────────────────────────────────────────────────────────

const CompanyOverview = ({ analysis }) => {
  const fundamentalsData = analysis?.agent_results?.fundamentals?.data || null;
  const hasNarrative = !!(analysis?.analysis?.narrative);

  return (
    <Motion.div
      variants={fadeUp}
      initial="hidden"
      animate="visible"
      className="flex flex-col"
      style={{ gap: 'var(--space-card-gap, 20px)' }}
    >
      <DescriptionCard data={fundamentalsData} />

      {hasNarrative && <NarrativePanel analysis={analysis} />}

      <FundamentalsCard data={fundamentalsData} />
    </Motion.div>
  );
};

export default CompanyOverview;
```

- [ ] **Step 2: Verify it renders standalone**

Temporarily import and render in Dashboard to check. Expected: Three stacked glass cards with description, narrative, and fundamentals metric grid.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/CompanyOverview.jsx
git commit -m "feat(frontend): add CompanyOverview composite component with description, narrative, fundamentals cards"
```

---

### Task 6: Create TechnicalsOptionsSection Component

**Files:**
- Create: `frontend/src/components/TechnicalsOptionsSection.jsx`

- [ ] **Step 1: Create the component file**

Create `frontend/src/components/TechnicalsOptionsSection.jsx`:

```jsx
/**
 * TechnicalsOptionsSection - Combined Technical Indicators + Options Flow
 * in two stacked glass cards under one section.
 */

import React from 'react';
import { motion as Motion } from 'framer-motion';
import OptionsFlow from './OptionsFlow';

const fadeUp = {
  hidden: { opacity: 0, y: 12 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.22, 1, 0.36, 1] } },
};

// ─── Technical Metric Card ──────────────────────────────────────────────────

const TechMetricCard = ({ label, value, badge, badgeColor }) => (
  <div
    className="bg-dark-inset rounded-lg border border-white/[0.04] hover:border-white/[0.08] transition-colors"
    style={{ padding: 'var(--space-card-padding, 20px)' }}
  >
    <div className="flex justify-between items-center mb-1.5">
      <span className="text-[11px] text-gray-500 uppercase tracking-wider font-medium">{label}</span>
      {badge && (
        <span
          className="text-[10px] px-1.5 py-0.5 rounded font-medium"
          style={{ background: `${badgeColor}20`, color: badgeColor }}
        >
          {badge}
        </span>
      )}
    </div>
    <div className="text-lg font-bold font-mono tabular-nums" style={{ color: 'var(--text-primary)' }}>
      {value}
    </div>
  </div>
);

// ─── RSI color helper ───────────────────────────────────────────────────────

function getRsiColor(value) {
  if (value > 70) return 'var(--accent-red)';
  if (value < 30) return 'var(--accent-green)';
  return 'var(--text-muted)';
}

function getRsiLabel(value) {
  if (value > 70) return 'Overbought';
  if (value < 30) return 'Oversold';
  return 'Neutral';
}

// ─── Technical Indicators Card ──────────────────────────────────────────────

const TechnicalCard = ({ data }) => {
  if (!data) return null;

  const indicators = data.indicators || {};
  const signals = data.signals || {};
  const summary = data.analysis || data.summary || null;

  const rsi = indicators.rsi;
  const macd = indicators.macd;
  const strength = signals.strength;
  const overall = signals.overall;

  return (
    <div className="glass-card rounded-xl" style={{ padding: 'var(--space-card-padding, 20px)' }}>
      <div className="text-sm font-semibold mb-4 flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
        <span style={{ color: 'var(--accent-blue)' }}>◆</span> Technical Indicators
      </div>

      <div
        className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4"
        style={{ gap: 'var(--space-metrics-gap, 16px)' }}
      >
        {rsi && (
          <TechMetricCard
            label="RSI"
            value={rsi.value?.toFixed(1) ?? 'N/A'}
            badge={getRsiLabel(rsi.value)}
            badgeColor={getRsiColor(rsi.value)}
          />
        )}
        {macd && (
          <TechMetricCard
            label="MACD"
            value={macd.macd_line?.toFixed(2) ?? macd.value?.toFixed(2) ?? 'N/A'}
            badge={macd.interpretation || null}
            badgeColor={macd.interpretation?.includes('bullish') ? 'var(--accent-green)' : 'var(--accent-red)'}
          />
        )}
        {strength != null && (
          <TechMetricCard
            label="Signal Strength"
            value={`${(strength * 100).toFixed(0)}%`}
            badge={overall || null}
            badgeColor={
              overall === 'bullish' ? 'var(--accent-green)' :
              overall === 'bearish' ? 'var(--accent-red)' :
              'var(--accent-amber)'
            }
          />
        )}
        {indicators.bollinger_bands && (
          <TechMetricCard
            label="Bollinger"
            value={indicators.bollinger_bands.interpretation || 'N/A'}
            badge="Band"
            badgeColor="var(--accent-purple)"
          />
        )}
      </div>

      {summary && (
        <div className="mt-4 text-[0.88rem] leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
          {summary}
        </div>
      )}
    </div>
  );
};

// ─── Main Component ─────────────────────────────────────────────────────────

const TechnicalsOptionsSection = ({ analysis }) => {
  const technicalData = analysis?.agent_results?.technical?.data || null;

  return (
    <Motion.div
      variants={fadeUp}
      initial="hidden"
      animate="visible"
      className="flex flex-col"
      style={{ gap: 'var(--space-card-gap, 20px)' }}
    >
      <TechnicalCard data={technicalData} />
      <OptionsFlow analysis={analysis} />
    </Motion.div>
  );
};

export default TechnicalsOptionsSection;
```

- [ ] **Step 2: Verify in browser**

Expected: Technical metrics in a grid above the existing OptionsFlow card. Both render as stacked glass cards.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/TechnicalsOptionsSection.jsx
git commit -m "feat(frontend): add TechnicalsOptionsSection combining technical indicators and options flow"
```

---

### Task 7: Add Thesis Empty State with Retry

**Files:**
- Modify: `frontend/src/components/ThesisPanel.jsx`

- [ ] **Step 1: Add empty state with retry at the top of the component**

In `ThesisPanel.jsx`, find the main `ThesisPanel` component function. Add a `useState` import if not already present, and add a `useCallback` import. Then replace the empty-data early return with an empty state that includes a retry button.

Add these imports at the top of the file (merge with existing):

```jsx
import React, { useState, useCallback } from 'react';
```

Find the main component (should be near the bottom). Replace the early return for no data with:

```jsx
const ThesisPanel = ({ analysis }) => {
  const data = getThesisData(analysis);
  const [retrying, setRetrying] = useState(false);
  const [retryError, setRetryError] = useState(null);
  const [retryData, setRetryData] = useState(null);

  const ticker = analysis?.ticker;

  const handleRetry = useCallback(async () => {
    if (!ticker) return;
    setRetrying(true);
    setRetryError(null);
    try {
      const res = await fetch(`/api/analyze/${ticker}?agents=thesis`, { method: 'POST' });
      if (!res.ok) throw new Error(`Failed (${res.status})`);
      const result = await res.json();
      const thesisResult = result?.analysis?.thesis || result?.agent_results?.thesis?.data || null;
      if (thesisResult) {
        setRetryData(thesisResult);
      } else {
        setRetryError('Thesis agent returned no data');
      }
    } catch (err) {
      setRetryError(err.message || 'Retry failed');
    } finally {
      setRetrying(false);
    }
  }, [ticker]);

  const activeData = retryData || data;

  if (!activeData) {
    return (
      <div className="glass-card rounded-xl flex flex-col items-center justify-center py-12 px-6 text-center"
        style={{ padding: 'var(--space-card-padding, 20px)' }}
      >
        <svg width="40" height="40" viewBox="0 0 40 40" fill="none" className="mb-4 opacity-40">
          <rect x="8" y="6" width="24" height="28" rx="3" stroke="#52525b" strokeWidth="1.5" fill="none" />
          <line x1="13" y1="14" x2="27" y2="14" stroke="#3f3f46" strokeWidth="1" />
          <line x1="13" y1="19" x2="24" y2="19" stroke="#3f3f46" strokeWidth="1" />
          <line x1="13" y1="24" x2="21" y2="24" stroke="#3f3f46" strokeWidth="1" />
        </svg>
        <p className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>
          Thesis analysis unavailable
        </p>
        <p className="text-xs mt-1 mb-4" style={{ color: 'var(--text-muted)' }}>
          The thesis agent didn't return data for this analysis
        </p>
        <button
          onClick={handleRetry}
          disabled={retrying}
          className="px-5 py-2.5 rounded-full text-sm font-medium border cursor-pointer transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          style={{
            color: 'var(--accent-blue)',
            borderColor: 'rgba(0,111,238,0.3)',
            background: 'rgba(0,111,238,0.08)',
          }}
          onMouseEnter={(e) => { e.target.style.background = 'rgba(0,111,238,0.15)'; }}
          onMouseLeave={(e) => { e.target.style.background = 'rgba(0,111,238,0.08)'; }}
        >
          {retrying ? 'Retrying...' : 'Retry Thesis Analysis'}
        </button>
        {retryError && (
          <p className="text-xs mt-2" style={{ color: 'var(--accent-red)' }}>{retryError}</p>
        )}
      </div>
    );
  }

  // ... rest of the existing render logic using `activeData` instead of `data`
```

Update all references to `data` in the rest of the component to use `activeData` instead.

- [ ] **Step 2: Verify in browser**

Run an analysis. If thesis data is missing, verify the empty state renders with the retry button. Click retry and verify it shows loading state.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ThesisPanel.jsx
git commit -m "feat(frontend): add thesis empty state with retry button"
```

---

### Task 8: Update EarningsPanel Summary Format (Hybrid)

**Files:**
- Modify: `frontend/src/components/EarningsPanel.jsx`

- [ ] **Step 1: Add a summary section to EarningsPanel**

The current EarningsPanel doesn't render a summary text block — it goes straight to sub-cards. Add a summary section after `HeaderRow` and before the grid. Find the main `EarningsPanel` component return, and add between `<HeaderRow>` and the first grid:

```jsx
      {/* Summary — hybrid format: paragraph + bullets */}
      {data.summary && (
        <div className="glass-card" style={{ padding: 'var(--space-card-padding, 20px)' }}>
          <EarningsSummary text={data.summary} />
        </div>
      )}
```

Add the `EarningsSummary` sub-component above the main component:

```jsx
const EarningsSummary = ({ text }) => {
  if (!text) return null;

  // Split into sentences
  const sentences = text.match(/[^.!?]+[.!?]+/g) || [text];
  const introParagraph = sentences.slice(0, 3).join(' ').trim();
  const bulletPoints = sentences.slice(3);

  return (
    <div>
      {introParagraph && (
        <p className="text-[0.88rem] leading-relaxed mb-3" style={{ color: 'var(--text-secondary)' }}>
          {introParagraph}
        </p>
      )}
      {bulletPoints.length > 0 && (
        <ul className="space-y-1.5">
          {bulletPoints.map((point, i) => (
            <li key={i} className="flex items-start gap-2">
              <span className="text-accent-blue mt-1.5 text-[8px] flex-shrink-0">●</span>
              <span className="text-[0.85rem] leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                {point.trim()}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};
```

- [ ] **Step 2: Update spacing in EarningsPanel**

Replace the gap values in the main return JSX. Change `gap-4` to use the spacing token:

```jsx
    <Motion.div variants={fadeUp} initial="hidden" animate="visible"
      className="flex flex-col"
      style={{ gap: 'var(--space-card-gap, 20px)' }}
    >
```

Also update the two grid containers from `gap-4` to:

```jsx
      <div className="grid grid-cols-1 sm:grid-cols-2" style={{ gap: 'var(--space-card-gap, 20px)' }}>
```

- [ ] **Step 3: Verify in browser**

Expected: Summary appears as paragraph + bullets above the existing card grid. Spacing between all cards is 20px.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/EarningsPanel.jsx
git commit -m "feat(frontend): add hybrid summary format to EarningsPanel, update spacing tokens"
```

---

### Task 9: Remove Scenario Toggle from CouncilPanel

**Files:**
- Modify: `frontend/src/components/CouncilPanel.jsx`

- [ ] **Step 1: Update the InvestorCard component**

In `CouncilPanel.jsx`, find the `InvestorCard` component (around line 157). Remove the `expanded` state and the toggle button. Replace the scenarios toggle section (the `{scenarios.length > 0 && (` block starting around line 227) with:

```jsx
      {/* Scenarios — always visible */}
      {scenarios.length > 0 && (
        <div className="border-t border-white/5 px-4 py-3" style={{ gap: 'var(--space-card-gap, 20px)' }}>
          <div className="text-[10px] font-semibold uppercase tracking-wider text-gray-500 mb-2">
            If-Then Scenarios
          </div>
          <div className="space-y-2">
            {scenarios.map((s, i) => (
              <ScenarioPill key={i} scenario={s} idx={i} />
            ))}
          </div>
        </div>
      )}
```

Also remove the `useState` import for `expanded` from the InvestorCard (remove `const [expanded, setExpanded] = useState(false);`). Remove the `AnimatePresence` import if it's no longer used elsewhere in the file — check first. If other parts use it, keep the import.

- [ ] **Step 2: Update investor card spacing**

Update the card padding. In the InvestorCard's header `<div className="px-4 pt-4 pb-3 ...">`, change to use the token: add `style={{ padding: 'var(--space-card-padding, 20px)' }}` on the outer card div and remove individual px-4/pt-4/pb-3 padding from sub-sections accordingly, or more simply, just update the overall container padding.

Actually, to minimize churn, just update the gap between investor cards. Find where InvestorCards are rendered in a grid/flex and ensure the gap uses `var(--space-card-gap, 20px)`.

- [ ] **Step 3: Verify in browser**

Expected: Each investor card now shows IF-THEN scenarios inline at the bottom with a "If-Then Scenarios" sub-header. No toggle button. Scenarios animate in on page load via stagger.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/CouncilPanel.jsx
git commit -m "feat(frontend): show council IF-THEN scenarios always visible, remove toggle"
```

---

### Task 10: Rewire Dashboard — New Section Order and Components

**Files:**
- Modify: `frontend/src/components/Dashboard.jsx`

- [ ] **Step 1: Add new imports**

At the top of `Dashboard.jsx`, add:

```jsx
import CompanyOverview from './CompanyOverview';
import TechnicalsOptionsSection from './TechnicalsOptionsSection';
```

- [ ] **Step 2: Replace SECTION_ORDER**

Replace the `SECTION_ORDER` array (lines 182-196) with:

```jsx
const SECTION_ORDER = [
  { key: 'company_overview', name: 'Company Overview', special: 'company_overview' },
  { key: 'earnings', name: 'Earnings', special: 'earnings' },
  { key: 'earnings_review', name: 'Earnings Review', special: 'earnings_review' },
  { key: 'thesis', name: 'Thesis', special: 'thesis' },
  { key: 'risk_diff', name: 'Risk Analysis', special: 'risk_diff' },
  { key: 'technicals_options', name: 'Technicals & Options', special: 'technicals_options' },
  { key: 'sentiment', name: 'Sentiment', special: false },
  { key: 'news', name: 'News', special: 'news' },
  { key: 'leadership', name: 'Leadership', special: 'leadership' },
  { key: 'council', name: 'Council', special: 'council' },
];
```

- [ ] **Step 3: Update renderSpecialChildren**

Add cases for the new composite sections in `renderSpecialChildren`:

```jsx
      case 'company_overview':
        return <CompanyOverview analysis={analysis} />;
      case 'technicals_options':
        return <TechnicalsOptionsSection analysis={analysis} />;
```

- [ ] **Step 4: Update the result resolution for composite sections**

In the section rendering loop (around line 497-520), the `result` lookup needs to handle composite keys. Update:

```jsx
                {SECTION_ORDER.map(({ key, name, special }) => {
                    // Composite sections don't have their own agent result — derive stance differently
                    let result;
                    let stance;
                    let summary;
                    let metrics;

                    if (key === 'company_overview') {
                      result = agentResults.fundamentals
                        || (analysis?.analysis?.fundamentals ? { success: true, data: analysis.analysis.fundamentals } : null);
                      stance = getAgentStance('fundamentals', result);
                      summary = null; // CompanyOverview handles its own rendering
                      metrics = [];
                    } else if (key === 'technicals_options') {
                      result = agentResults.technical
                        || (analysis?.analysis?.technical ? { success: true, data: analysis.analysis.technical } : null);
                      stance = getAgentStance('technical', result);
                      summary = null; // TechnicalsOptionsSection handles its own rendering
                      metrics = [];
                    } else {
                      result = agentResults[key]
                        || (analysis?.analysis?.[key] ? { success: true, data: analysis.analysis[key] } : null);
                      stance = getAgentStance(key, result);
                      summary = getAgentSummary(result);
                      metrics = getAgentMetrics(key, result);
                    }

                    return (
                      <AnalysisSection
                        key={key}
                        id={`section-${key}`}
                        name={name}
                        stance={stance}
                        stanceColor={STANCE_COLORS[stance]}
                        summary={summary}
                        metrics={metrics}
                        fullContent={result?.data?.analysis || result?.data?.full_analysis || null}
                        dataSource={result?.data?.data_source || result?.data_source || null}
                        duration={result?.duration_seconds}
                      >
                        {special ? renderSpecialChildren(special) : null}
                      </AnalysisSection>
                    );
                  })}
```

- [ ] **Step 5: Update the section container gap**

Change the section container gap from `gap-3` to use the spacing token. Find:

```jsx
                <div className="px-6 pt-4 pb-8 flex flex-col gap-3">
```

Replace with:

```jsx
                <div className="px-6 pt-4 pb-8 flex flex-col" style={{ gap: 'var(--space-section-gap, 32px)' }}>
```

- [ ] **Step 6: Verify in browser**

Run an analysis. Expected:
- Company Overview section at top with 3 stacked cards (description, narrative, fundamentals)
- Earnings, Earnings Review, Thesis, Risk Analysis sections follow
- Technicals & Options combined section
- Sentiment, News, Leadership, Council at bottom
- Macro is gone
- 32px gaps between sections

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/Dashboard.jsx
git commit -m "feat(frontend): rewire Dashboard with new section order, composite components, spacing tokens"
```

---

### Task 11: Create MacroPage and Update Sidebar

**Files:**
- Create: `frontend/src/components/MacroPage.jsx`
- Modify: `frontend/src/components/Sidebar.jsx`
- Modify: `frontend/src/components/Dashboard.jsx`

- [ ] **Step 1: Create MacroPage component**

Create `frontend/src/components/MacroPage.jsx`:

```jsx
/**
 * MacroPage - Standalone macro environment page
 * Shows macro economic indicators and summary.
 */

import React, { useState, useEffect } from 'react';
import { motion as Motion } from 'framer-motion';

const fadeUp = {
  hidden: { opacity: 0, y: 12 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.22, 1, 0.36, 1] } },
};

const MetricCard = ({ label, value }) => (
  <div
    className="bg-dark-inset rounded-lg border border-white/[0.04] hover:border-white/[0.08] transition-colors"
    style={{ padding: 'var(--space-card-padding, 20px)' }}
  >
    <div className="text-[11px] uppercase tracking-wider font-medium" style={{ color: 'var(--text-muted)' }}>
      {label}
    </div>
    <div className="text-lg font-bold mt-1 font-mono tabular-nums" style={{ color: 'var(--text-primary)' }}>
      {value}
    </div>
  </div>
);

const MacroPage = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchMacro = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch('/api/macro-events');
        if (!res.ok) throw new Error(`Failed to fetch macro data (${res.status})`);
        const json = await res.json();
        setData(json);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    fetchMacro();
  }, []);

  if (loading) {
    return (
      <div className="px-6 py-8">
        <div className="skeleton h-8 w-48 mb-6 rounded-lg" />
        <div className="grid grid-cols-3 gap-4">
          <div className="skeleton h-24 rounded-lg" />
          <div className="skeleton h-24 rounded-lg" />
          <div className="skeleton h-24 rounded-lg" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="px-6 py-8">
        <div className="glass-card rounded-xl p-6 text-center">
          <p className="text-sm" style={{ color: 'var(--accent-red)' }}>{error}</p>
        </div>
      </div>
    );
  }

  const indicators = data?.indicators || data || {};
  const summary = data?.summary || data?.analysis || null;
  const lastUpdated = data?.last_updated || data?.timestamp || null;

  return (
    <div className="px-6 py-8">
      <Motion.div variants={fadeUp} initial="hidden" animate="visible">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
            Macro Environment
          </h1>
          {lastUpdated && (
            <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
              Updated: {new Date(lastUpdated).toLocaleString()}
            </span>
          )}
        </div>

        <div
          className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4"
          style={{ gap: 'var(--space-card-gap, 20px)', marginBottom: 'var(--space-section-gap, 32px)' }}
        >
          {indicators.fed_funds_rate != null && (
            <MetricCard label="Fed Funds Rate" value={`${indicators.fed_funds_rate}%`} />
          )}
          {indicators.cpi != null && (
            <MetricCard label="CPI" value={`${indicators.cpi}%`} />
          )}
          {indicators.gdp_growth != null && (
            <MetricCard label="GDP Growth" value={`${indicators.gdp_growth}%`} />
          )}
          {indicators.unemployment_rate != null && (
            <MetricCard label="Unemployment" value={`${indicators.unemployment_rate}%`} />
          )}
          {indicators.treasury_10y != null && (
            <MetricCard label="10Y Treasury" value={`${indicators.treasury_10y}%`} />
          )}
          {indicators.treasury_2y != null && (
            <MetricCard label="2Y Treasury" value={`${indicators.treasury_2y}%`} />
          )}
        </div>

        {summary && (
          <div className="glass-card rounded-xl" style={{ padding: 'var(--space-card-padding, 20px)' }}>
            <div className="text-sm font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>
              Analysis
            </div>
            <div className="text-[0.88rem] leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              {summary}
            </div>
          </div>
        )}
      </Motion.div>
    </div>
  );
};

export default MacroPage;
```

- [ ] **Step 2: Update Sidebar with Research/Tools/History groups**

In `Sidebar.jsx`, replace the `NAV_SECTIONS` constant with:

```jsx
const MacroIcon = () => (
  <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
    <path d="M1 12.5A4.5 4.5 0 005.5 17H15a4 4 0 001.866-7.539 3.504 3.504 0 00-4.504-4.272A4.5 4.5 0 004.06 8.235 4.502 4.502 0 001 12.5z" />
  </svg>
);

const NAV_SECTIONS = [
  {
    label: 'Research',
    items: [
      { key: 'analysis', label: 'Analysis', Icon: PulseIcon },
      { key: 'macro', label: 'Macro', Icon: MacroIcon },
    ],
  },
  {
    label: 'Tools',
    items: [
      { key: 'watchlist', label: 'Watchlist', Icon: ChartBarIcon },
      { key: 'portfolio', label: 'Holdings', Icon: BuildingIcon },
      { key: 'schedules', label: 'Schedules', Icon: ClockIcon },
      { key: 'alerts', label: 'Alerts', Icon: BellIcon },
    ],
  },
  {
    label: 'History',
    items: [
      { key: 'history', label: 'History', Icon: HistoryIcon },
      { key: 'inflections', label: 'Inflections', Icon: ActivityIcon },
    ],
  },
];
```

- [ ] **Step 3: Add MACRO view mode and MacroPage to Dashboard**

In `Dashboard.jsx`, add to `VIEW_MODES`:

```jsx
  MACRO: 'macro',
```

Add import:

```jsx
import MacroPage from './MacroPage';
```

Add the macro view rendering alongside the other non-analysis views (around line 354):

```jsx
        {viewMode === VIEW_MODES.MACRO && <MacroPage />}
```

- [ ] **Step 4: Verify in browser**

Expected: Sidebar shows Research/Tools/History groupings. Clicking "Macro" in sidebar navigates to the standalone macro page with metric cards and summary.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/MacroPage.jsx frontend/src/components/Sidebar.jsx frontend/src/components/Dashboard.jsx
git commit -m "feat(frontend): add standalone Macro page, restructure sidebar into Research/Tools/History groups"
```

---

### Task 12: Final Spacing Polish Pass

**Files:**
- Modify: `frontend/src/components/NarrativePanel.jsx`
- Modify: `frontend/src/components/OptionsFlow.jsx`
- Modify: `frontend/src/components/CouncilPanel.jsx`

- [ ] **Step 1: Update NarrativePanel spacing**

In `NarrativePanel.jsx`, find gap/padding values used between cards and sections. Update:
- Change `gap-3` or `gap-4` on the main container to `style={{ gap: 'var(--space-card-gap, 20px)' }}`
- Change card padding `p-4` to `style={{ padding: 'var(--space-card-padding, 20px)' }}` on glass-card divs

- [ ] **Step 2: Update OptionsFlow spacing**

In `OptionsFlow.jsx`, update:
- Card-level gaps to use `var(--space-card-gap, 20px)`
- Card padding to use `var(--space-card-padding, 20px)`

- [ ] **Step 3: Update CouncilPanel investor card grid spacing**

Find where investor cards are laid out (likely a flex or grid container) and ensure gap uses `var(--space-card-gap, 20px)`.

- [ ] **Step 4: Verify in browser — full walkthrough**

Do a complete analysis run and scroll through every section:
1. Price chart shows all 5 SMAs
2. Company Overview: description card → narrative card → fundamentals metrics card
3. Earnings: hybrid summary → card grid
4. Earnings Review: unchanged
5. Thesis: shows content or empty state with retry
6. Risk Analysis: unchanged
7. Technicals & Options: technical metric grid → options flow
8. Sentiment: full content visible, no toggle
9. News: full content visible, no toggle
10. Leadership: unchanged
11. Council: scenarios always visible
12. 32px between sections, 20px between cards within sections
13. Pill tabs in section nav
14. Macro in sidebar → standalone page

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/NarrativePanel.jsx frontend/src/components/OptionsFlow.jsx frontend/src/components/CouncilPanel.jsx
git commit -m "feat(frontend): apply spacing tokens to NarrativePanel, OptionsFlow, CouncilPanel"
```

---

## Summary

| Task | Description | New Files | Modified Files |
|------|-------------|-----------|----------------|
| 1 | Spacing tokens | — | index.css |
| 2 | Pill tabs | — | SectionNav.jsx |
| 3 | Remove collapsibles | — | AnalysisSection.jsx |
| 4 | All SMAs visible | — | PriceChart.jsx |
| 5 | CompanyOverview | CompanyOverview.jsx | — |
| 6 | TechnicalsOptions | TechnicalsOptionsSection.jsx | — |
| 7 | Thesis empty state | — | ThesisPanel.jsx |
| 8 | Earnings hybrid summary | — | EarningsPanel.jsx |
| 9 | Council scenarios visible | — | CouncilPanel.jsx |
| 10 | Dashboard rewire | — | Dashboard.jsx |
| 11 | Macro page + sidebar | MacroPage.jsx | Sidebar.jsx, Dashboard.jsx |
| 12 | Spacing polish | — | NarrativePanel.jsx, OptionsFlow.jsx, CouncilPanel.jsx |
