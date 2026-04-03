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
    <div className="mb-4">
      <div className="text-sm font-semibold mb-3 px-1" style={{ color: 'var(--text-primary)' }}>
        Year-by-Year Performance
      </div>
      <div className="flex flex-col gap-0 rounded-xl overflow-hidden border border-white/[0.06]">
        {years.map((year, i) => {
          const borderColor = getYearBorderColor(year);
          const inflections = year.quarterly_inflections || year.inflections || [];

          // Collect detail fields — try multiple key patterns
          const details = [
            { label: 'Revenue', value: year.revenue },
            { label: 'Margins', value: year.margins },
            { label: 'Strategy', value: year.strategy },
            { label: 'Capital', value: year.capital_allocation },
          ].filter((d) => d.value);

          // Fallback: if no structured details, use headline or summary
          const headline = year.headline || year.summary || year.description || null;

          return (
            <div
              key={i}
              className="px-5 py-4"
              style={{
                borderLeft: `3px solid ${borderColor}`,
                background: i % 2 === 0 ? 'rgba(255,255,255,0.02)' : 'transparent',
                borderBottom: i < years.length - 1 ? '1px solid rgba(255,255,255,0.04)' : 'none',
              }}
            >
              <div className="flex items-start gap-4">
                {/* Year badge */}
                <div
                  className="text-base font-bold font-mono tabular-nums flex-shrink-0 w-12"
                  style={{ color: borderColor }}
                >
                  {year.year || year.period}
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                  {headline && (
                    <p className="text-[13px] leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                      {headline}
                    </p>
                  )}

                  {details.length > 0 && (
                    <div className="grid grid-cols-2 gap-x-6 gap-y-2 mt-2">
                      {details.map((d, j) => (
                        <div key={j}>
                          <span className="text-[10px] uppercase tracking-wider font-medium" style={{ color: 'var(--text-muted)' }}>
                            {d.label}
                          </span>
                          <span className="text-[12px] ml-2" style={{ color: 'var(--text-secondary)' }}>
                            {d.value}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Quarterly inflections */}
                  {inflections.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mt-2">
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
              </div>
            </div>
          );
        })}
      </div>
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
      <div className="grid grid-cols-1 sm:grid-cols-2" style={{ gap: 'var(--space-card-gap, 20px)' }}>
        {chapters.map((ch, i) => {
          const colorSet = CHAPTER_COLORS[i % CHAPTER_COLORS.length];
          return (
            <div
              key={i}
              className="glass-card"
              style={{ borderLeft: `3px solid ${colorSet.border}`, background: colorSet.bg, padding: 'var(--space-card-padding, 20px)' }}
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
