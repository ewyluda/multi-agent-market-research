/**
 * NarrativePanel - Multi-year financial narrative visualization showing
 * company arc, year-by-year performance, thematic chapters, and current state.
 */

import React from 'react';
import { motion as Motion } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

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
    if (growth > 10) return 'var(--success)';
    if (growth > 0) return 'var(--primary)';
  }
  return 'rgba(255,255,255,0.15)';
};

const INFLECTION_BADGE_VARIANTS = {
  positive: 'success',
  negative: 'danger',
  pivotal: 'default',
};

// ─── Sub-components ──────────────────────────────────────────────────────────

const CompanyArc = ({ arc, metadata }) => {
  if (!arc) return null;

  return (
    <Card
      className="mb-4"
      style={{
        background: 'linear-gradient(135deg, rgba(0,111,238,0.08) 0%, rgba(120,40,200,0.08) 100%)',
        borderLeft: '3px solid var(--primary)',
      }}
    >
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
          <span style={{ color: 'var(--primary)' }}>&#x25C6;</span> Company Arc
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-[13px] leading-relaxed mb-3" style={{ color: 'var(--text-secondary)' }}>
          {arc}
        </p>
        {metadata && (
          <div className="flex flex-wrap gap-2">
            {metadata.years_covered && (
              <Badge variant="default" className="text-[10px]">
                {metadata.years_covered}
              </Badge>
            )}
            {metadata.filings_analyzed != null && (
              <Badge variant="secondary" className="text-[10px]">
                {metadata.filings_analyzed} filings
              </Badge>
            )}
            {metadata.sector && (
              <Badge variant="secondary" className="text-[10px]">
                {metadata.sector}
              </Badge>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

const YearSections = ({ years }) => {
  if (!years?.length) return null;

  return (
    <div className="mb-4">
      <div className="text-sm font-semibold mb-3 px-1" style={{ color: 'var(--text-primary)' }}>
        Year-by-Year Performance
      </div>
      <Card className="overflow-hidden">
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
                  className="text-base font-bold font-data flex-shrink-0 w-12"
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
                        const badgeVariant = INFLECTION_BADGE_VARIANTS[type] || 'default';
                        return (
                          <Badge key={j} variant={badgeVariant} className="text-[10px] rounded-full">
                            {inf.quarter && `${inf.quarter}: `}{inf.description || inf.event}
                            {inf.impact && ` (${inf.impact})`}
                          </Badge>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </Card>
    </div>
  );
};

const NarrativeChapters = ({ chapters }) => {
  if (!chapters?.length) return null;

  const CHAPTER_COLORS = [
    { border: 'var(--primary)', bg: 'rgba(0,111,238,0.06)' },
    { border: 'var(--success)', bg: 'rgba(23,201,100,0.06)' },
    { border: 'var(--warning)', bg: 'rgba(245,165,36,0.06)' },
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
            <Card
              key={i}
              style={{ borderLeft: `3px solid ${colorSet.border}`, background: colorSet.bg, padding: 'var(--space-card-padding, 20px)' }}
            >
              <CardContent className="p-0">
                <div className="text-[13px] font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                  {ch.title || ch.theme}
                </div>
                <p className="text-[12px] leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                  {ch.narrative || ch.description}
                </p>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
};

const CurrentChapter = ({ current }) => {
  if (!current) return null;

  return (
    <Card style={{ borderLeft: '3px solid var(--warning)' }}>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
          <span style={{ color: 'var(--warning)' }}>&#x25B6;</span> Where We Are Now
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-[13px] leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
          {typeof current === 'string' ? current : current.narrative || current.description}
        </p>
      </CardContent>
    </Card>
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
