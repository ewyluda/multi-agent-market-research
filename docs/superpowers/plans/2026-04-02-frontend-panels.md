# Frontend Panels Implementation Plan — Thesis, EarningsReview, Narrative, RiskDiff

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 4 new React panel components that visualize output from the CapRelay synthesis agents (thesis, earnings_review, narrative, risk_diff) and integrate them into the Dashboard section order.

**Architecture:** Each panel is a child of `AnalysisSection` (the existing wrapper), rendered via `renderSpecialChildren` in Dashboard.jsx. The new agents store data at `analysis.thesis`, `analysis.earnings_review`, `analysis.narrative`, `analysis.risk_diff` — top-level fields on the analysis object, NOT inside `agent_results`. Dashboard data extraction is patched to create synthetic result objects from these fields.

**Tech Stack:** React, Tailwind CSS v4, Framer Motion (frontend panels only — no backend changes)

**Spec:** `docs/superpowers/specs/2026-04-02-frontend-panels-design.md`

**Pattern Reference:** `frontend/src/components/EarningsPanel.jsx` — follow exactly for imports, animation variants, glass-card styling, null handling

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `frontend/src/components/ThesisPanel.jsx` | Bull/bear thesis cards, tension points, management questions |
| Create | `frontend/src/components/EarningsReviewPanel.jsx` | Beat/miss badges, KPI table, quotes, thesis impact |
| Create | `frontend/src/components/NarrativePanel.jsx` | Company arc, year sections, thematic chapters |
| Create | `frontend/src/components/RiskDiffPanel.jsx` | Risk score gauge, emerging threats, change cards, filing metadata |
| Modify | `frontend/src/components/Dashboard.jsx:1-29,54-112,117-121,124-161,164-174,266-281,467-468` | Imports, stance/summary/metrics helpers, SECTION_ORDER, renderSpecialChildren, data extraction |
| Modify | `frontend/src/components/SectionNav.jsx:3-12` | Add 4 new section entries to SECTIONS array |

---

### Task 1: Create ThesisPanel.jsx (~250 lines)

**Files:**
- Create: `frontend/src/components/ThesisPanel.jsx`

- [ ] **Step 1: Create `frontend/src/components/ThesisPanel.jsx`**

Write the complete component file. Follow the EarningsPanel pattern exactly for imports and animation.

```jsx
/**
 * ThesisPanel - Investment thesis visualization with bull/bear cases,
 * tension points, and management questions for the CEO/CFO.
 */

import React from 'react';
import { motion as Motion } from 'framer-motion';

const fadeUp = {
  hidden: { opacity: 0, y: 12 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.22, 1, 0.36, 1] } },
};

// ─── Helpers ─────────────────────────────────────────────────────────────────

const getThesisData = (analysis) =>
  analysis?.analysis?.thesis || null;

// ─── Sub-components ──────────────────────────────────────────────────────────

const ThesisSummary = ({ data }) => {
  const summary = data?.thesis_summary;
  const completeness = data?.data_completeness;
  if (!summary) return null;

  return (
    <div className="glass-card p-4 mb-4">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
          Investment Thesis
        </span>
        {completeness && (
          <span
            className="text-[10px] px-1.5 py-0.5 rounded font-medium"
            style={{
              background: 'rgba(0,111,238,0.1)',
              color: '#006fee',
            }}
          >
            {completeness}
          </span>
        )}
      </div>
      <p className="text-[13px] leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
        {summary}
      </p>
    </div>
  );
};

const BullBearCards = ({ data }) => {
  const bull = data?.bull_case;
  const bear = data?.bear_case;
  if (!bull && !bear) return null;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
      {/* Bull Case */}
      {bull && (
        <div
          className="glass-card p-4"
          style={{ borderLeft: '3px solid #17c964' }}
        >
          <div className="text-sm font-semibold mb-2" style={{ color: '#17c964' }}>
            Bull Case
          </div>
          {bull.thesis && (
            <p className="text-[13px] leading-relaxed mb-3" style={{ color: 'var(--text-secondary)' }}>
              {bull.thesis}
            </p>
          )}
          {bull.key_drivers?.length > 0 && (
            <div className="mb-2">
              <div className="text-[11px] uppercase tracking-wider mb-1.5" style={{ color: 'var(--text-muted)' }}>
                Key Drivers
              </div>
              <div className="flex flex-col gap-1">
                {bull.key_drivers.map((driver, i) => (
                  <div key={i} className="flex items-start gap-1.5">
                    <span className="text-[10px] mt-0.5" style={{ color: '#17c964' }}>+</span>
                    <span className="text-[12px]" style={{ color: 'var(--text-secondary)' }}>{driver}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
          {bull.catalysts?.length > 0 && (
            <div>
              <div className="text-[11px] uppercase tracking-wider mb-1.5" style={{ color: 'var(--text-muted)' }}>
                Catalysts
              </div>
              <div className="flex flex-wrap gap-1.5">
                {bull.catalysts.map((c, i) => (
                  <span
                    key={i}
                    className="text-[10px] px-2 py-0.5 rounded-full"
                    style={{ background: 'rgba(23,201,100,0.1)', color: '#17c964' }}
                  >
                    {c}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Bear Case */}
      {bear && (
        <div
          className="glass-card p-4"
          style={{ borderLeft: '3px solid #f31260' }}
        >
          <div className="text-sm font-semibold mb-2" style={{ color: '#f31260' }}>
            Bear Case
          </div>
          {bear.thesis && (
            <p className="text-[13px] leading-relaxed mb-3" style={{ color: 'var(--text-secondary)' }}>
              {bear.thesis}
            </p>
          )}
          {bear.key_drivers?.length > 0 && (
            <div className="mb-2">
              <div className="text-[11px] uppercase tracking-wider mb-1.5" style={{ color: 'var(--text-muted)' }}>
                Key Risks
              </div>
              <div className="flex flex-col gap-1">
                {bear.key_drivers.map((driver, i) => (
                  <div key={i} className="flex items-start gap-1.5">
                    <span className="text-[10px] mt-0.5" style={{ color: '#f31260' }}>-</span>
                    <span className="text-[12px]" style={{ color: 'var(--text-secondary)' }}>{driver}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
          {bear.catalysts?.length > 0 && (
            <div>
              <div className="text-[11px] uppercase tracking-wider mb-1.5" style={{ color: 'var(--text-muted)' }}>
                Risk Triggers
              </div>
              <div className="flex flex-wrap gap-1.5">
                {bear.catalysts.map((c, i) => (
                  <span
                    key={i}
                    className="text-[10px] px-2 py-0.5 rounded-full"
                    style={{ background: 'rgba(243,18,96,0.1)', color: '#f31260' }}
                  >
                    {c}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

const TensionPointsList = ({ tensionPoints }) => {
  if (!tensionPoints?.length) return null;

  return (
    <div className="glass-card p-4 mb-4">
      <div className="text-sm font-semibold mb-3 flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
        <span style={{ color: '#f5a524' }}>&#x25C6;</span> Tension Points
      </div>
      <div className="flex flex-col gap-3">
        {tensionPoints.map((tp, i) => (
          <div key={i} className="glass-card p-3">
            <div className="text-[13px] font-medium mb-2" style={{ color: 'var(--text-primary)' }}>
              {tp.point || tp.description}
            </div>
            <div className="grid grid-cols-2 gap-3 mb-2">
              <div>
                <div className="text-[10px] uppercase tracking-wider mb-1" style={{ color: '#17c964' }}>
                  Bull View
                </div>
                <div className="text-[12px]" style={{ color: 'var(--text-secondary)' }}>
                  {tp.bull_view}
                </div>
              </div>
              <div>
                <div className="text-[10px] uppercase tracking-wider mb-1" style={{ color: '#f31260' }}>
                  Bear View
                </div>
                <div className="text-[12px]" style={{ color: 'var(--text-secondary)' }}>
                  {tp.bear_view}
                </div>
              </div>
            </div>
            {tp.evidence && (
              <div className="text-[11px] italic mb-1" style={{ color: 'var(--text-muted)' }}>
                Evidence: {tp.evidence}
              </div>
            )}
            {tp.resolution_catalyst && (
              <div className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
                &#x2192; {tp.resolution_catalyst}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

const ManagementQuestions = ({ questions }) => {
  if (!questions?.length) return null;

  const ROLE_COLORS = {
    CEO: { bg: 'rgba(0,111,238,0.1)', text: '#006fee' },
    CFO: { bg: 'rgba(120,40,200,0.1)', text: '#7828c8' },
  };

  return (
    <div className="glass-card p-4">
      <div className="text-sm font-semibold mb-3 flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
        <span style={{ color: '#006fee' }}>&#x25C8;</span> Management Questions
      </div>
      <div className="flex flex-col gap-2.5">
        {questions.map((q, i) => {
          const role = q.for_role?.toUpperCase() || 'CEO';
          const roleColor = ROLE_COLORS[role] || ROLE_COLORS.CEO;
          return (
            <div key={i} className="flex gap-2 items-start">
              <span
                className="text-[10px] px-1.5 py-0.5 rounded font-medium whitespace-nowrap mt-0.5"
                style={{ background: roleColor.bg, color: roleColor.text }}
              >
                {role}
              </span>
              <span className="text-[13px] leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                {q.question || q.text || q}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
};

// ─── Main Component ──────────────────────────────────────────────────────────

const ThesisPanel = ({ analysis }) => {
  const data = getThesisData(analysis);

  if (!data) {
    return (
      <div className="text-sm py-4 text-center" style={{ color: 'var(--text-muted)' }}>
        Thesis analysis not available
      </div>
    );
  }

  if (data.error) {
    return (
      <div className="text-sm py-4 text-center" style={{ color: 'var(--text-muted)' }}>
        Thesis analysis not available
      </div>
    );
  }

  return (
    <Motion.div variants={fadeUp} initial="hidden" animate="visible" className="flex flex-col gap-0">
      <ThesisSummary data={data} />
      <BullBearCards data={data} />
      <TensionPointsList tensionPoints={data.tension_points} />
      <ManagementQuestions questions={data.management_questions} />
    </Motion.div>
  );
};

export default ThesisPanel;
```

- [ ] **Step 2: Verify file created**

```bash
wc -l frontend/src/components/ThesisPanel.jsx
```

Expected: ~230-260 lines.

---

### Task 2: Create EarningsReviewPanel.jsx (~300 lines)

**Files:**
- Create: `frontend/src/components/EarningsReviewPanel.jsx`

- [ ] **Step 1: Create `frontend/src/components/EarningsReviewPanel.jsx`**

Write the complete component file.

```jsx
/**
 * EarningsReviewPanel - Deep earnings review with beat/miss verdicts,
 * KPI table, notable quotes, thesis impact, and one-off flags.
 */

import React from 'react';
import { motion as Motion } from 'framer-motion';

const fadeUp = {
  hidden: { opacity: 0, y: 12 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.22, 1, 0.36, 1] } },
};

// ─── Helpers ─────────────────────────────────────────────────────────────────

const getReviewData = (analysis) =>
  analysis?.analysis?.earnings_review || null;

const VERDICT_COLORS = {
  beat: { bg: 'rgba(23,201,100,0.1)', text: '#17c964', border: 'rgba(23,201,100,0.25)' },
  miss: { bg: 'rgba(243,18,96,0.1)', text: '#f31260', border: 'rgba(243,18,96,0.25)' },
  inline: { bg: 'rgba(255,255,255,0.04)', text: 'rgba(255,255,255,0.5)', border: 'rgba(255,255,255,0.08)' },
};

const GUIDANCE_COLORS = {
  raised: { text: '#17c964' },
  lowered: { text: '#f31260' },
  maintained: { text: 'rgba(255,255,255,0.5)' },
};

const SOURCE_BADGES = {
  reported: { bg: 'rgba(255,255,255,0.06)', text: 'rgba(255,255,255,0.4)' },
  call: { bg: 'rgba(0,111,238,0.1)', text: '#006fee' },
  calc: { bg: 'rgba(255,255,255,0.06)', text: 'rgba(255,255,255,0.4)' },
};

// ─── Sub-components ──────────────────────────────────────────────────────────

const ExecutiveSummary = ({ summary }) => {
  if (!summary) return null;
  return (
    <div className="glass-card p-4 mb-4">
      <div className="text-sm font-semibold mb-2 flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
        <span style={{ color: 'var(--accent-blue)' }}>&#x2726;</span> Executive Summary
      </div>
      <p className="text-[13px] leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
        {summary}
      </p>
    </div>
  );
};

const BeatMissBadges = ({ beatMiss }) => {
  if (!beatMiss?.length) return null;

  return (
    <div className="grid grid-cols-3 gap-3 mb-4">
      {beatMiss.map((item, i) => {
        const verdict = item.verdict?.toLowerCase() || 'inline';
        const colors = VERDICT_COLORS[verdict] || VERDICT_COLORS.inline;
        return (
          <div
            key={i}
            className="glass-card p-4 text-center"
            style={{ background: colors.bg, border: `1px solid ${colors.border}` }}
          >
            <div className="text-[11px] uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>
              {item.metric || item.label}
            </div>
            <div className="text-xl font-bold capitalize" style={{ color: colors.text }}>
              {verdict}
            </div>
            {item.detail && (
              <div className="text-[11px] mt-1" style={{ color: 'var(--text-muted)' }}>
                {item.detail}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};

const KPITable = ({ kpis }) => {
  if (!kpis?.length) return null;

  return (
    <div className="glass-card p-4 mb-4">
      <div className="text-sm font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>
        Key Performance Indicators
      </div>
      <table className="w-full">
        <thead>
          <tr className="border-b border-white/[0.08]">
            <th className="text-left text-[11px] font-medium pb-1.5 pr-2" style={{ color: 'var(--text-muted)' }}>Metric</th>
            <th className="text-right text-[11px] font-medium pb-1.5 px-2" style={{ color: 'var(--text-muted)' }}>Value</th>
            <th className="text-right text-[11px] font-medium pb-1.5 px-2" style={{ color: 'var(--text-muted)' }}>Prior</th>
            <th className="text-right text-[11px] font-medium pb-1.5 px-2" style={{ color: 'var(--text-muted)' }}>YoY</th>
            <th className="text-right text-[11px] font-medium pb-1.5 pl-2" style={{ color: 'var(--text-muted)' }}>Source</th>
          </tr>
        </thead>
        <tbody>
          {kpis.map((kpi, i) => {
            const source = kpi.source?.toLowerCase() || 'reported';
            const srcStyle = SOURCE_BADGES[source] || SOURCE_BADGES.reported;
            const yoyVal = kpi.yoy_change || kpi.yoy;
            const yoyColor = yoyVal && typeof yoyVal === 'string' && yoyVal.startsWith('-') ? '#f31260' : '#17c964';
            return (
              <tr key={i} className={i < kpis.length - 1 ? 'border-b border-white/[0.04]' : ''}>
                <td className="text-[13px] py-2 pr-2" style={{ color: 'var(--text-secondary)' }}>{kpi.metric || kpi.name}</td>
                <td className="text-right text-[13px] py-2 px-2 font-mono" style={{ color: 'var(--text-primary)' }}>{kpi.value}</td>
                <td className="text-right text-[13px] py-2 px-2 font-mono" style={{ color: 'var(--text-muted)' }}>{kpi.prior || '—'}</td>
                <td className="text-right text-[13px] py-2 px-2 font-mono" style={{ color: yoyVal ? yoyColor : 'var(--text-muted)' }}>
                  {yoyVal || '—'}
                </td>
                <td className="text-right py-2 pl-2">
                  <span
                    className="text-[10px] px-1.5 py-0.5 rounded font-medium"
                    style={{ background: srcStyle.bg, color: srcStyle.text }}
                  >
                    {source}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};

const BottomRow = ({ quotes, thesisImpact, oneOffs, partial }) => {
  const hasQuotes = quotes?.length > 0;
  const hasImpact = thesisImpact || oneOffs?.length > 0;
  if (!hasQuotes && !hasImpact) return null;

  if (partial) {
    return (
      <div className="glass-card p-4">
        <div className="text-sm text-center py-2" style={{ color: 'var(--text-muted)' }}>
          No transcript available — LLM-derived sections limited
        </div>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
      {/* Notable Quotes */}
      {hasQuotes && (
        <div className="glass-card p-4">
          <div className="text-sm font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>
            Notable Quotes
          </div>
          <div className="flex flex-col gap-2.5">
            {quotes.map((q, i) => (
              <div key={i} className="border-l-2 border-white/10 pl-3">
                <div className="text-[13px] italic leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                  "{q.text || q.quote || q}"
                </div>
                {q.speaker && (
                  <div className="text-[11px] mt-1" style={{ color: 'var(--text-muted)' }}>
                    — {q.speaker}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Thesis Impact + One-offs */}
      {hasImpact && (
        <div className="glass-card p-4">
          {thesisImpact && (
            <div className="mb-3">
              <div className="text-sm font-semibold mb-2" style={{ color: 'var(--text-primary)' }}>
                Thesis Impact
              </div>
              <p className="text-[13px] leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                {thesisImpact}
              </p>
            </div>
          )}
          {oneOffs?.length > 0 && (
            <div>
              <div className="text-sm font-semibold mb-2 flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
                <span style={{ color: '#f5a524' }}>&#x26A0;</span> One-off Items
              </div>
              <div className="flex flex-col gap-1.5">
                {oneOffs.map((item, i) => (
                  <div
                    key={i}
                    className="text-[12px] px-2 py-1 rounded"
                    style={{ background: 'rgba(245,165,36,0.08)', color: '#f5a524' }}
                  >
                    {item.description || item}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

// ─── Main Component ──────────────────────────────────────────────────────────

const EarningsReviewPanel = ({ analysis }) => {
  const data = getReviewData(analysis);

  if (!data) {
    return (
      <div className="text-sm py-4 text-center" style={{ color: 'var(--text-muted)' }}>
        Earnings review not available
      </div>
    );
  }

  return (
    <Motion.div variants={fadeUp} initial="hidden" animate="visible" className="flex flex-col gap-0">
      <ExecutiveSummary summary={data.executive_summary} />
      <BeatMissBadges beatMiss={data.beat_miss} />
      <KPITable kpis={data.kpis} />
      <BottomRow
        quotes={data.notable_quotes}
        thesisImpact={data.thesis_impact}
        oneOffs={data.one_offs}
        partial={data.partial}
      />
    </Motion.div>
  );
};

export default EarningsReviewPanel;
```

- [ ] **Step 2: Verify file created**

```bash
wc -l frontend/src/components/EarningsReviewPanel.jsx
```

Expected: ~280-320 lines.

---

### Task 3: Create NarrativePanel.jsx (~280 lines)

**Files:**
- Create: `frontend/src/components/NarrativePanel.jsx`

- [ ] **Step 1: Create `frontend/src/components/NarrativePanel.jsx`**

Write the complete component file.

```jsx
/**
 * NarrativePanel - Multi-year financial narrative visualization showing
 * company arc, year-by-year performance, thematic chapters, and current state.
 */

import React from 'react';
import { motion as Motion } from 'framer-motion';

const fadeUp = {
  hidden: { opacity: 0, y: 12 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.22, 1, 0.36, 1] } },
};

// ─── Helpers ─────────────────────────────────────────────────────────────────

const getNarrativeData = (analysis) =>
  analysis?.analysis?.narrative || null;

const getYearBorderColor = (year) => {
  const growth = year?.revenue_growth || year?.growth_rate || 0;
  if (typeof growth === 'number') {
    if (growth > 10) return '#17c964';
    if (growth > 0) return '#006fee';
  }
  return 'rgba(255,255,255,0.15)';
};

const INFLECTION_COLORS = {
  positive: { bg: 'rgba(23,201,100,0.1)', text: '#17c964', border: 'rgba(23,201,100,0.25)' },
  negative: { bg: 'rgba(243,18,96,0.1)', text: '#f31260', border: 'rgba(243,18,96,0.25)' },
  pivotal: { bg: 'rgba(0,111,238,0.1)', text: '#006fee', border: 'rgba(0,111,238,0.25)' },
};

// ─── Sub-components ──────────────────────────────────────────────────────────

const CompanyArc = ({ arc, metadata }) => {
  if (!arc) return null;

  return (
    <div
      className="glass-card-elevated p-5 mb-4"
      style={{
        background: 'linear-gradient(135deg, rgba(0,111,238,0.08) 0%, rgba(120,40,200,0.08) 100%)',
        borderLeft: '3px solid #006fee',
      }}
    >
      <div className="text-sm font-semibold mb-2 flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
        <span style={{ color: '#006fee' }}>&#x25C6;</span> Company Arc
      </div>
      <p className="text-[13px] leading-relaxed mb-3" style={{ color: 'var(--text-secondary)' }}>
        {arc}
      </p>
      {metadata && (
        <div className="flex flex-wrap gap-2">
          {metadata.years_covered && (
            <span className="text-[10px] px-2 py-0.5 rounded" style={{ background: 'rgba(0,111,238,0.1)', color: '#006fee' }}>
              {metadata.years_covered}
            </span>
          )}
          {metadata.filings_analyzed != null && (
            <span className="text-[10px] px-2 py-0.5 rounded" style={{ background: 'rgba(255,255,255,0.06)', color: 'var(--text-muted)' }}>
              {metadata.filings_analyzed} filings
            </span>
          )}
          {metadata.sector && (
            <span className="text-[10px] px-2 py-0.5 rounded" style={{ background: 'rgba(255,255,255,0.06)', color: 'var(--text-muted)' }}>
              {metadata.sector}
            </span>
          )}
        </div>
      )}
    </div>
  );
};

const YearSections = ({ years }) => {
  if (!years?.length) return null;

  return (
    <div className="flex flex-col gap-3 mb-4">
      {years.map((year, i) => {
        const borderColor = getYearBorderColor(year);
        const inflections = year.quarterly_inflections || year.inflections || [];

        return (
          <div
            key={i}
            className="glass-card p-4"
            style={{ borderLeft: `3px solid ${borderColor}` }}
          >
            <div className="flex items-center justify-between mb-2">
              <div className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                {year.year || year.period}
              </div>
              {year.headline && (
                <div className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
                  {year.headline}
                </div>
              )}
            </div>

            {/* 2x2 grid: revenue, margins, strategy, capital */}
            <div className="grid grid-cols-2 gap-3 mb-2">
              {year.revenue && (
                <div>
                  <div className="text-[10px] uppercase tracking-wider mb-0.5" style={{ color: 'var(--text-muted)' }}>Revenue</div>
                  <div className="text-[12px]" style={{ color: 'var(--text-secondary)' }}>{year.revenue}</div>
                </div>
              )}
              {year.margins && (
                <div>
                  <div className="text-[10px] uppercase tracking-wider mb-0.5" style={{ color: 'var(--text-muted)' }}>Margins</div>
                  <div className="text-[12px]" style={{ color: 'var(--text-secondary)' }}>{year.margins}</div>
                </div>
              )}
              {year.strategy && (
                <div>
                  <div className="text-[10px] uppercase tracking-wider mb-0.5" style={{ color: 'var(--text-muted)' }}>Strategy</div>
                  <div className="text-[12px]" style={{ color: 'var(--text-secondary)' }}>{year.strategy}</div>
                </div>
              )}
              {year.capital_allocation && (
                <div>
                  <div className="text-[10px] uppercase tracking-wider mb-0.5" style={{ color: 'var(--text-muted)' }}>Capital</div>
                  <div className="text-[12px]" style={{ color: 'var(--text-secondary)' }}>{year.capital_allocation}</div>
                </div>
              )}
            </div>

            {/* Quarterly inflections */}
            {inflections.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-2 pt-2 border-t border-white/[0.06]">
                {inflections.map((inf, j) => {
                  const type = inf.type?.toLowerCase() || 'pivotal';
                  const colors = INFLECTION_COLORS[type] || INFLECTION_COLORS.pivotal;
                  return (
                    <span
                      key={j}
                      className="text-[10px] px-2 py-0.5 rounded border"
                      style={{ background: colors.bg, color: colors.text, borderColor: colors.border }}
                    >
                      {inf.quarter && `${inf.quarter}: `}{inf.description || inf.event}
                      {inf.impact && ` (${inf.impact})`}
                    </span>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};

const NarrativeChapters = ({ chapters }) => {
  if (!chapters?.length) return null;

  const CHAPTER_COLORS = [
    { border: '#006fee', bg: 'rgba(0,111,238,0.06)' },
    { border: '#17c964', bg: 'rgba(23,201,100,0.06)' },
    { border: '#f5a524', bg: 'rgba(245,165,36,0.06)' },
    { border: '#7828c8', bg: 'rgba(120,40,200,0.06)' },
  ];

  return (
    <div className="mb-4">
      <div className="text-sm font-semibold mb-3 px-1" style={{ color: 'var(--text-primary)' }}>
        Thematic Threads
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {chapters.map((ch, i) => {
          const colorSet = CHAPTER_COLORS[i % CHAPTER_COLORS.length];
          return (
            <div
              key={i}
              className="glass-card p-4"
              style={{ borderLeft: `3px solid ${colorSet.border}`, background: colorSet.bg }}
            >
              <div className="text-[13px] font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                {ch.title || ch.theme}
              </div>
              <p className="text-[12px] leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                {ch.narrative || ch.description}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
};

const CurrentChapter = ({ current }) => {
  if (!current) return null;

  return (
    <div className="glass-card-elevated p-4" style={{ borderLeft: '3px solid #f5a524' }}>
      <div className="text-sm font-semibold mb-2 flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
        <span style={{ color: '#f5a524' }}>&#x25B6;</span> Where We Are Now
      </div>
      <p className="text-[13px] leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
        {typeof current === 'string' ? current : current.narrative || current.description}
      </p>
    </div>
  );
};

// ─── Main Component ──────────────────────────────────────────────────────────

const NarrativePanel = ({ analysis }) => {
  const data = getNarrativeData(analysis);

  if (!data) {
    return (
      <div className="text-sm py-4 text-center" style={{ color: 'var(--text-muted)' }}>
        Financial narrative not available
      </div>
    );
  }

  return (
    <Motion.div variants={fadeUp} initial="hidden" animate="visible" className="flex flex-col gap-0">
      <CompanyArc arc={data.company_arc} metadata={data.metadata} />
      <YearSections years={data.years || data.year_sections} />
      <NarrativeChapters chapters={data.chapters || data.thematic_threads} />
      <CurrentChapter current={data.current_chapter || data.where_we_are_now} />
    </Motion.div>
  );
};

export default NarrativePanel;
```

- [ ] **Step 2: Verify file created**

```bash
wc -l frontend/src/components/NarrativePanel.jsx
```

Expected: ~250-290 lines.

---

### Task 4: Create RiskDiffPanel.jsx (~300 lines)

**Files:**
- Create: `frontend/src/components/RiskDiffPanel.jsx`

- [ ] **Step 1: Create `frontend/src/components/RiskDiffPanel.jsx`**

Write the complete component file.

```jsx
/**
 * RiskDiffPanel - Risk factor diff visualization showing risk score changes,
 * emerging threats, detailed change cards, and filing metadata.
 */

import React from 'react';
import { motion as Motion } from 'framer-motion';

const fadeUp = {
  hidden: { opacity: 0, y: 12 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.22, 1, 0.36, 1] } },
};

// ─── Helpers ─────────────────────────────────────────────────────────────────

const getRiskData = (analysis) =>
  analysis?.analysis?.risk_diff || null;

const CHANGE_TYPE_COLORS = {
  NEW: { bg: 'rgba(243,18,96,0.1)', text: '#f31260', border: 'rgba(243,18,96,0.25)' },
  ESCALATED: { bg: 'rgba(245,165,36,0.1)', text: '#f5a524', border: 'rgba(245,165,36,0.25)' },
  'DE-ESCALATED': { bg: 'rgba(23,201,100,0.1)', text: '#17c964', border: 'rgba(23,201,100,0.25)' },
  REMOVED: { bg: 'rgba(255,255,255,0.04)', text: 'rgba(255,255,255,0.4)', border: 'rgba(255,255,255,0.08)' },
  REWORDED: { bg: 'rgba(0,111,238,0.1)', text: '#006fee', border: 'rgba(0,111,238,0.25)' },
};

const SEVERITY_COLORS = {
  HIGH: { bg: 'rgba(243,18,96,0.1)', text: '#f31260' },
  MEDIUM: { bg: 'rgba(245,165,36,0.1)', text: '#f5a524' },
  LOW: { bg: 'rgba(255,255,255,0.06)', text: 'rgba(255,255,255,0.4)' },
};

const EXTRACTION_BADGES = {
  pattern: { bg: 'rgba(255,255,255,0.06)', text: 'rgba(255,255,255,0.4)' },
  llm_fallback: { bg: 'rgba(0,111,238,0.1)', text: '#006fee' },
};

// ─── Sub-components ──────────────────────────────────────────────────────────

const SummaryAndScore = ({ data }) => {
  const summary = data?.summary;
  const riskScore = data?.risk_score;
  const delta = data?.risk_score_delta;

  return (
    <div className="glass-card p-4 mb-4">
      <div className="flex gap-4">
        {/* Summary text — flex:2 */}
        <div className="flex-[2]">
          <div className="text-sm font-semibold mb-2" style={{ color: 'var(--text-primary)' }}>
            Risk Summary
          </div>
          {summary && (
            <p className="text-[13px] leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              {summary}
            </p>
          )}
        </div>

        {/* Risk score gauge — flex:1 */}
        <div className="flex-1 flex flex-col items-center justify-center">
          {riskScore != null && (
            <>
              <div className="text-[11px] uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>
                Risk Score
              </div>
              <div
                className="text-3xl font-bold"
                style={{
                  color: riskScore > 70 ? '#f31260' : riskScore > 40 ? '#f5a524' : '#17c964',
                }}
              >
                {riskScore}
              </div>
              {delta != null && delta !== 0 && (
                <div
                  className="text-sm font-mono mt-1"
                  style={{ color: delta > 0 ? '#f31260' : '#17c964' }}
                >
                  {delta > 0 ? '+' : ''}{delta}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};

const EmergingThreats = ({ threats }) => {
  if (!threats?.length) return null;

  return (
    <div
      className="glass-card p-4 mb-4"
      style={{ background: 'rgba(243,18,96,0.04)', border: '1px solid rgba(243,18,96,0.15)' }}
    >
      <div className="text-sm font-semibold mb-3 flex items-center gap-2" style={{ color: '#f31260' }}>
        <span>&#x26A0;</span> Emerging Threats
      </div>
      <div className="flex flex-wrap gap-2">
        {threats.map((threat, i) => (
          <span
            key={i}
            className="text-[11px] px-2.5 py-1 rounded-full border"
            style={{ background: 'rgba(243,18,96,0.1)', color: '#f31260', borderColor: 'rgba(243,18,96,0.25)' }}
          >
            {typeof threat === 'string' ? threat : threat.name || threat.description}
          </span>
        ))}
      </div>
    </div>
  );
};

const RiskChangeCards = ({ changes }) => {
  if (!changes?.length) return null;

  return (
    <div className="flex flex-col gap-3 mb-4">
      <div className="text-sm font-semibold px-1" style={{ color: 'var(--text-primary)' }}>
        Risk Factor Changes
      </div>
      {changes.map((change, i) => {
        const type = change.type?.toUpperCase() || 'REWORDED';
        const typeColors = CHANGE_TYPE_COLORS[type] || CHANGE_TYPE_COLORS.REWORDED;
        const severity = change.severity?.toUpperCase() || 'MEDIUM';
        const sevColors = SEVERITY_COLORS[severity] || SEVERITY_COLORS.MEDIUM;

        return (
          <div key={i} className="glass-card p-4">
            {/* Header badges */}
            <div className="flex items-center gap-2 mb-2">
              <span
                className="text-[10px] px-2 py-0.5 rounded font-medium border"
                style={{ background: typeColors.bg, color: typeColors.text, borderColor: typeColors.border }}
              >
                {type}
              </span>
              <span
                className="text-[10px] px-1.5 py-0.5 rounded font-medium"
                style={{ background: sevColors.bg, color: sevColors.text }}
              >
                {severity}
              </span>
              {change.category && (
                <span className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
                  {change.category}
                </span>
              )}
            </div>

            {/* Analysis text */}
            {change.analysis && (
              <p className="text-[13px] leading-relaxed mb-2" style={{ color: 'var(--text-secondary)' }}>
                {change.analysis}
              </p>
            )}
            {change.description && !change.analysis && (
              <p className="text-[13px] leading-relaxed mb-2" style={{ color: 'var(--text-secondary)' }}>
                {change.description}
              </p>
            )}

            {/* Prior/Current excerpts for escalated risks */}
            {(change.prior_excerpt || change.current_excerpt) && (
              <div className="grid grid-cols-2 gap-3 mt-2 pt-2 border-t border-white/[0.06]">
                {change.prior_excerpt && (
                  <div>
                    <div className="text-[10px] uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>Prior</div>
                    <div className="text-[11px] italic" style={{ color: 'var(--text-muted)' }}>
                      "{change.prior_excerpt}"
                    </div>
                  </div>
                )}
                {change.current_excerpt && (
                  <div>
                    <div className="text-[10px] uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>Current</div>
                    <div className="text-[11px] italic" style={{ color: 'var(--text-secondary)' }}>
                      "{change.current_excerpt}"
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};

const RiskInventoryTable = ({ inventory }) => {
  if (!inventory?.length) return null;

  return (
    <div className="glass-card p-4 mb-4">
      <div className="text-sm font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>
        Risk Inventory
      </div>
      <div className="flex flex-col gap-2">
        {inventory.map((item, i) => {
          const severity = item.severity?.toUpperCase() || 'MEDIUM';
          const sevColors = SEVERITY_COLORS[severity] || SEVERITY_COLORS.MEDIUM;
          return (
            <div key={i} className="flex items-start gap-2">
              <span
                className="text-[10px] px-1.5 py-0.5 rounded font-medium whitespace-nowrap mt-0.5"
                style={{ background: sevColors.bg, color: sevColors.text }}
              >
                {severity}
              </span>
              <span className="text-[12px]" style={{ color: 'var(--text-secondary)' }}>
                {item.description || item.name || item}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
};

const FilingMetadata = ({ filings }) => {
  if (!filings?.length) return null;

  return (
    <div className="glass-card p-3">
      <div className="flex flex-wrap gap-2 items-center">
        <span className="text-[11px] font-medium" style={{ color: 'var(--text-muted)' }}>Filings:</span>
        {filings.map((f, i) => {
          const method = f.extraction_method?.toLowerCase() || 'pattern';
          const methodStyle = EXTRACTION_BADGES[method] || EXTRACTION_BADGES.pattern;
          return (
            <div key={i} className="flex items-center gap-1.5">
              <span className="text-[11px]" style={{ color: 'var(--text-secondary)' }}>
                {f.type || f.filing_type} {f.date && `(${f.date})`}
              </span>
              <span
                className="text-[9px] px-1.5 py-0.5 rounded"
                style={{ background: methodStyle.bg, color: methodStyle.text }}
              >
                {method}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
};

// ─── Main Component ──────────────────────────────────────────────────────────

const RiskDiffPanel = ({ analysis }) => {
  const data = getRiskData(analysis);

  if (!data) {
    return (
      <div className="text-sm py-4 text-center" style={{ color: 'var(--text-muted)' }}>
        Risk analysis not available
      </div>
    );
  }

  // No diff available — show inventory only
  if (data.has_diff === false) {
    return (
      <Motion.div variants={fadeUp} initial="hidden" animate="visible" className="flex flex-col gap-0">
        <div className="glass-card p-4 mb-4 text-center">
          <div className="text-sm" style={{ color: 'var(--text-muted)' }}>
            Only 1 filing available — no diff
          </div>
        </div>
        <RiskInventoryTable inventory={data.risk_inventory || data.current_risks} />
        <FilingMetadata filings={data.filings} />
      </Motion.div>
    );
  }

  return (
    <Motion.div variants={fadeUp} initial="hidden" animate="visible" className="flex flex-col gap-0">
      <SummaryAndScore data={data} />
      <EmergingThreats threats={data.emerging_threats} />
      <RiskChangeCards changes={data.changes || data.risk_changes} />
      <FilingMetadata filings={data.filings} />
    </Motion.div>
  );
};

export default RiskDiffPanel;
```

- [ ] **Step 2: Verify file created**

```bash
wc -l frontend/src/components/RiskDiffPanel.jsx
```

Expected: ~280-320 lines.

---

### Task 5: Dashboard.jsx + SectionNav.jsx Integration

**Files:**
- Modify: `frontend/src/components/Dashboard.jsx:1-29,54-112,117-121,124-161,164-174,266-281,467-468`
- Modify: `frontend/src/components/SectionNav.jsx:3-12`

- [ ] **Step 1: Add imports to Dashboard.jsx**

After the existing `EarningsPanel` import (line 22), add 4 new imports:

```javascript
// ADD after line 22 (import EarningsPanel from './EarningsPanel';)
import ThesisPanel from './ThesisPanel';
import EarningsReviewPanel from './EarningsReviewPanel';
import NarrativePanel from './NarrativePanel';
import RiskDiffPanel from './RiskDiffPanel';
```

- [ ] **Step 2: Add getAgentStance cases**

In `getAgentStance()` (line 54-112), add 4 new cases before the `default` case (line 109):

```javascript
    // ADD before `default:` (line 109)
    case 'thesis':
      return 'neutral';
    case 'earnings_review': {
      const verdict = d.beat_miss?.[0]?.verdict;
      if (verdict === 'beat') return 'bullish';
      if (verdict === 'miss') return 'bearish';
      return 'neutral';
    }
    case 'narrative':
      return 'neutral';
    case 'risk_diff': {
      const delta = d.risk_score_delta ?? 0;
      if (delta > 5) return 'bearish';
      if (delta < -5) return 'bullish';
      return 'neutral';
    }
```

- [ ] **Step 3: Add getAgentSummary cases**

In `getAgentSummary()` (line 117-121), replace the function body to add explicit cases before the fallback:

```javascript
// REPLACE getAgentSummary function (lines 117-121):
function getAgentSummary(agentKey, result) {
  if (!result?.success || !result?.data) return null;
  const d = result.data;
  switch (agentKey) {
    case 'thesis': return d.thesis_summary;
    case 'earnings_review': return d.executive_summary;
    case 'narrative': return d.company_arc;
    case 'risk_diff': return d.summary;
    default: return d.analysis || d.summary || d.executive_summary || d.assessment || null;
  }
}
```

**IMPORTANT:** This changes the function signature from `getAgentSummary(result)` to `getAgentSummary(agentKey, result)`. Update the call site at line 470:

```javascript
// CHANGE line 470 from:
const summary = getAgentSummary(result);
// TO:
const summary = getAgentSummary(key, result);
```

- [ ] **Step 4: Update SECTION_ORDER**

Replace the `SECTION_ORDER` constant (lines 164-174) with the new order that includes the 4 synthesis sections:

```javascript
const SECTION_ORDER = [
  { key: 'fundamentals', name: 'Fundamentals', special: false },
  { key: 'earnings', name: 'Earnings', special: 'earnings' },
  { key: 'earnings_review', name: 'Earnings Review', special: 'earnings_review' },
  { key: 'thesis', name: 'Thesis', special: 'thesis' },
  { key: 'narrative', name: 'Narrative', special: 'narrative' },
  { key: 'risk_diff', name: 'Risk Analysis', special: 'risk_diff' },
  { key: 'technical', name: 'Technical', special: false },
  { key: 'sentiment', name: 'Sentiment', special: false },
  { key: 'macro', name: 'Macro', special: false },
  { key: 'news', name: 'News', special: 'news' },
  { key: 'options', name: 'Options', special: 'options' },
  { key: 'leadership', name: 'Leadership', special: 'leadership' },
  { key: 'council', name: 'Council', special: 'council' },
];
```

- [ ] **Step 5: Add renderSpecialChildren cases**

In `renderSpecialChildren()` (line 266-281), add 4 new cases before `default`:

```javascript
      // ADD before `default:` (line 279)
      case 'earnings_review':
        return <EarningsReviewPanel analysis={analysis} />;
      case 'thesis':
        return <ThesisPanel analysis={analysis} />;
      case 'narrative':
        return <NarrativePanel analysis={analysis} />;
      case 'risk_diff':
        return <RiskDiffPanel analysis={analysis} />;
```

- [ ] **Step 6: Fix data extraction for synthesis sections**

At line 468, change the result lookup to fall back to top-level analysis fields:

```javascript
// CHANGE line 468 from:
const result = agentResults[key];
// TO:
const result = agentResults[key]
  || (analysis?.analysis?.[key] ? { success: true, data: analysis.analysis[key] } : null);
```

This creates a synthetic result object for thesis, earnings_review, narrative, and risk_diff — which live on `analysis.analysis.*` rather than `analysis.agent_results.*`.

- [ ] **Step 7: Update SectionNav.jsx**

Replace the `SECTIONS` array (lines 3-12) with the expanded version:

```javascript
const SECTIONS = [
  { id: 'section-fundamentals', label: 'Fundamentals' },
  { id: 'section-earnings', label: 'Earnings' },
  { id: 'section-earnings_review', label: 'Earnings Review' },
  { id: 'section-thesis', label: 'Thesis' },
  { id: 'section-narrative', label: 'Narrative' },
  { id: 'section-risk_diff', label: 'Risk Analysis' },
  { id: 'section-technical', label: 'Technical' },
  { id: 'section-sentiment', label: 'Sentiment' },
  { id: 'section-macro', label: 'Macro' },
  { id: 'section-news', label: 'News' },
  { id: 'section-options', label: 'Options' },
  { id: 'section-leadership', label: 'Leadership' },
  { id: 'section-council', label: 'Council' },
];
```

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/Dashboard.jsx frontend/src/components/SectionNav.jsx
git commit -m "feat(frontend): integrate 4 synthesis panels into Dashboard and SectionNav"
```

---

### Task 6: Lint + Visual Verification

**Files:** None (verification only)

- [ ] **Step 1: Run ESLint**

```bash
cd frontend && npm run lint
```

Fix any warnings/errors. Common issues to watch for:
- Unused imports
- Missing keys in `.map()` calls
- Prop-types warnings (this project doesn't use PropTypes — ignore if linter allows)

- [ ] **Step 2: Verify all imports resolve**

```bash
cd frontend && npx vite build --mode development 2>&1 | head -50
```

This will catch any missing file references or broken imports.

- [ ] **Step 3: Visual verification instructions**

Start the frontend dev server:
```bash
cd frontend && npm run dev
```

Then verify:
1. Navigate to the analysis view (analyze any ticker)
2. Scroll through sections — the new "deep research" block should appear between Earnings and Technical: **Earnings Review > Thesis > Narrative > Risk Analysis**
3. Each section should show "not available" gracefully when the backend hasn't provided synthesis data
4. SectionNav bar should show all 13 sections (scrollable if needed)
5. Clicking a SectionNav label should smooth-scroll to the correct section

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat(frontend): add ThesisPanel, EarningsReviewPanel, NarrativePanel, RiskDiffPanel components"
```

---

## Summary of All Changes

| # | Task | Files | Est. Lines |
|---|------|-------|-----------|
| 1 | ThesisPanel.jsx | 1 new | ~250 |
| 2 | EarningsReviewPanel.jsx | 1 new | ~300 |
| 3 | NarrativePanel.jsx | 1 new | ~280 |
| 4 | RiskDiffPanel.jsx | 1 new | ~300 |
| 5 | Dashboard.jsx + SectionNav.jsx | 2 modified | ~60 |
| 6 | Lint + Verify | 0 | 0 |
| **Total** | | **4 new, 2 modified** | **~1190** |

## Dependency Graph

```
Tasks 1-4 are independent (can run in parallel).
Task 5 depends on Tasks 1-4 (imports the new components).
Task 6 depends on Task 5 (lint + verify the full integration).
```

## Gotchas

1. **Data location**: Synthesis data is at `analysis.analysis.thesis` (etc.), NOT `analysis.agent_results.thesis`. The synthetic result object pattern in Task 5 Step 6 bridges this gap.
2. **getAgentSummary signature change**: Task 5 Step 3 changes the function from 1 param to 2 params. The call site must be updated in the same step (Step 3).
3. **Null safety**: Every panel handles `null` data gracefully — always show a "not available" message. Every sub-component checks its input before rendering.
4. **No PropTypes**: This project uses plain JSX without PropTypes or TypeScript — don't add type checking.
5. **Framer Motion import**: Use `import { motion as Motion }` to match existing pattern (capital M).
