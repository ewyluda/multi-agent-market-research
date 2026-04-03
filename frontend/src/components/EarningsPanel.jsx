/**
 * EarningsPanel - Earnings call transcript analysis visualization
 * Shows highlights, guidance breakdown, Q&A summaries, EPS chart, and tone analysis
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

const getEarningsData = (analysis) =>
  analysis?.agent_results?.earnings?.data || null;

const TAG_BADGE_VARIANTS = {
  BEAT: 'success',
  MISS: 'danger',
  NEW: 'default',
  WATCH: 'warning',
};

const DIRECTION_COLORS = {
  raised: 'text-success-400',
  lowered: 'text-danger-400',
  maintained: 'text-[var(--text-muted)]',
  introduced: 'text-accent-blue',
  withdrawn: 'text-danger-400',
};

const DIRECTION_ARROWS = {
  raised: '▲',
  lowered: '▼',
  maintained: '—',
  introduced: '●',
  withdrawn: '✕',
};

const TONE_BADGE_VARIANTS = {
  confident: 'success',
  optimistic: 'success',
  cautious: 'warning',
  defensive: 'danger',
  evasive: 'danger',
  neutral: 'secondary',
};

const GUIDANCE_BADGE_VARIANTS = {
  raised: 'success',
  lowered: 'danger',
  maintained: 'secondary',
  mixed: 'warning',
};

const TOPIC_COLORS = [
  'bg-accent-blue/10 text-accent-blue border-accent-blue/25',
  'bg-success/10 text-success-400 border-success/25',
  'bg-danger/10 text-danger-400 border-danger/25',
  'bg-warning/10 text-warning-400 border-warning/25',
  'bg-purple-500/10 text-purple-400 border-purple-500/25',
];

const getToneBarColor = (key, value) => {
  if (key === 'defensiveness' || key === 'hedging') {
    if (value <= 30) return 'bg-success-400';
    if (value <= 60) return 'bg-warning-400';
    return 'bg-danger-400';
  }
  if (value >= 70) return 'bg-success-400';
  if (value >= 40) return 'bg-accent-blue';
  return 'bg-warning-400';
};

const getToneLabel = (key, value) => {
  if (key === 'defensiveness' || key === 'hedging') {
    if (value <= 25) return 'Low';
    if (value <= 50) return 'Moderate';
    if (value <= 75) return 'High';
    return 'Very High';
  }
  if (value >= 75) return 'Strong';
  if (value >= 50) return 'Medium';
  if (value >= 25) return 'Low';
  return 'Weak';
};

const formatDate = (dateStr) => {
  if (!dateStr) return '';
  try {
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'long', day: 'numeric', year: 'numeric',
    });
  } catch {
    return dateStr;
  }
};

// ─── Sub-components ──────────────────────────────────────────────────────────

const HeaderRow = ({ data }) => {
  const meta = data.call_metadata || {};
  const tone = data.tone || 'neutral';
  const guidanceDir = data.guidance_direction || 'maintained';
  const toneBadgeVariant = TONE_BADGE_VARIANTS[tone] || 'secondary';
  const guidanceBadgeVariant = GUIDANCE_BADGE_VARIANTS[guidanceDir] || 'secondary';

  return (
    <div className="flex gap-3 mb-4">
      <Card className="flex-1" style={{ borderLeft: '3px solid var(--primary)' }}>
        <CardContent className="px-4 py-3 pt-3">
          <div className="text-[11px] uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Latest Call</div>
          <div className="text-base font-semibold mt-1" style={{ color: 'var(--text-primary)' }}>
            Q{meta.quarter} {meta.year} Earnings Call
          </div>
          <div className="text-xs mt-0.5" style={{ color: 'var(--text-secondary)' }}>{formatDate(meta.date)}</div>
        </CardContent>
      </Card>
      <Card className="px-4 py-3 text-center min-w-[100px]">
        <CardContent className="px-4 py-3 pt-3">
          <div className="text-[11px] uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>Tone</div>
          <Badge variant={toneBadgeVariant} className="capitalize">{tone}</Badge>
        </CardContent>
      </Card>
      <Card className="px-4 py-3 text-center min-w-[100px]">
        <CardContent className="px-4 py-3 pt-3">
          <div className="text-[11px] uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>Guidance</div>
          <Badge variant={guidanceBadgeVariant} className="capitalize">{guidanceDir}</Badge>
        </CardContent>
      </Card>
    </div>
  );
};

const HighlightsCard = ({ highlights }) => {
  if (!highlights?.length) return null;
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
          <span style={{ color: 'var(--primary)' }}>✦</span> Key Highlights
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex flex-col gap-2.5">
          {highlights.map((h, i) => {
            const badgeVariant = TAG_BADGE_VARIANTS[h.tag] || 'warning';
            return (
              <div key={i} className="flex gap-2 items-start">
                <Badge variant={badgeVariant} className="text-[10px] whitespace-nowrap mt-0.5 shrink-0">
                  {h.tag}
                </Badge>
                <span className="text-[13px] leading-relaxed" style={{ color: 'var(--text-secondary)' }}>{h.text}</span>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
};

const GuidanceCard = ({ guidance }) => {
  if (!guidance?.length) return null;
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
          <span style={{ color: 'var(--warning)' }}>⬥</span> Guidance Breakdown
        </CardTitle>
      </CardHeader>
      <CardContent>
        <table className="w-full">
          <thead>
            <tr className="border-b border-white/[0.08]">
              <th className="text-left text-[11px] font-medium pb-1.5 pr-2" style={{ color: 'var(--text-muted)' }}>Metric</th>
              <th className="text-right text-[11px] font-medium pb-1.5 px-2" style={{ color: 'var(--text-muted)' }}>Prior</th>
              <th className="text-right text-[11px] font-medium pb-1.5 px-2" style={{ color: 'var(--text-muted)' }}>Current</th>
              <th className="text-right text-[11px] font-medium pb-1.5 pl-2" style={{ color: 'var(--text-muted)' }}>Change</th>
            </tr>
          </thead>
          <tbody>
            {guidance.map((g, i) => {
              const dirColor = DIRECTION_COLORS[g.direction] || 'text-[var(--text-muted)]';
              const arrow = DIRECTION_ARROWS[g.direction] || '—';
              return (
                <tr key={i} className={i < guidance.length - 1 ? 'border-b border-white/[0.04]' : ''}>
                  <td className="text-[13px] py-2 pr-2" style={{ color: 'var(--text-secondary)' }}>{g.metric}</td>
                  <td className="text-right text-[13px] py-2 px-2 font-data" style={{ color: 'var(--text-muted)' }}>{g.prior}</td>
                  <td className="text-right text-[13px] py-2 px-2 font-data" style={{ color: 'var(--text-primary)' }}>{g.current}</td>
                  <td className={`text-right text-[13px] py-2 pl-2 font-data capitalize ${dirColor}`}>{arrow} {g.direction}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
};

const QACard = ({ qaHighlights }) => {
  if (!qaHighlights?.length) return null;
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
          <span className="text-purple-400">◈</span> Q&A Session Highlights
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex flex-col gap-3">
          {qaHighlights.map((qa, i) => {
            const topicClass = TOPIC_COLORS[i % TOPIC_COLORS.length];
            return (
              <div key={i} className="border-l-2 border-purple-500/40 pl-3">
                <div className="flex justify-between items-center mb-1">
                  <span className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
                    {qa.firm} — {qa.analyst}
                  </span>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded border ${topicClass}`}>
                    {qa.topic}
                  </span>
                </div>
                <div className="text-xs italic mb-1" style={{ color: 'var(--text-muted)' }}>
                  Q: {qa.question}
                </div>
                <div className="text-[13px] leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                  {qa.answer}
                </div>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
};

const EPSChart = ({ epsHistory }) => {
  if (!epsHistory?.length) return null;
  const maxVal = Math.max(...epsHistory.map((e) => Math.max(e.actual, e.estimate)));

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm" style={{ color: 'var(--text-primary)' }}>
          EPS: Actual vs. Estimate
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex flex-col gap-1.5">
          {epsHistory.map((e, i) => {
            const beat = e.actual >= e.estimate;
            const actualPct = maxVal > 0 ? (e.actual / maxVal) * 100 : 0;
            const estPct = maxVal > 0 ? (e.estimate / maxVal) * 100 : 0;
            return (
              <div key={i} className="flex items-center gap-2">
                <div className="text-[11px] w-[50px] font-data" style={{ color: 'var(--text-muted)' }}>{e.quarter}</div>
                <div className="flex-1 flex gap-0.5 items-center">
                  <div
                    className="h-5 rounded-sm flex items-center justify-end pr-1.5"
                    style={{
                      width: `${actualPct}%`,
                      background: beat
                        ? 'linear-gradient(90deg, rgba(23,201,100,0.3), rgba(23,201,100,0.5))'
                        : 'linear-gradient(90deg, rgba(243,18,96,0.3), rgba(243,18,96,0.5))',
                    }}
                  >
                    <span className={`text-[11px] font-data ${beat ? 'text-success-400' : 'text-danger-400'}`}>
                      ${e.actual.toFixed(2)}
                    </span>
                  </div>
                  <div
                    className="h-5 rounded-sm flex items-center justify-end pr-1.5"
                    style={{ width: `${estPct}%`, background: 'rgba(255,255,255,0.08)' }}
                  >
                    <span className="text-[11px] font-data" style={{ color: 'var(--text-muted)' }}>
                      ${e.estimate.toFixed(2)}
                    </span>
                  </div>
                </div>
                <div className={`text-[11px] w-[45px] text-right font-data ${beat ? 'text-success-400' : 'text-danger-400'}`}>
                  {e.surprise_pct >= 0 ? '+' : ''}{e.surprise_pct.toFixed(1)}%
                </div>
              </div>
            );
          })}
        </div>
        <div className="flex gap-3 mt-2 pt-2 border-t border-white/[0.06]">
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 rounded-sm" style={{ background: 'rgba(23,201,100,0.4)' }} />
            <span className="text-[10px]" style={{ color: 'var(--text-muted)' }}>Actual</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 rounded-sm" style={{ background: 'rgba(255,255,255,0.1)' }} />
            <span className="text-[10px]" style={{ color: 'var(--text-muted)' }}>Estimate</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

const ToneChart = ({ toneAnalysis }) => {
  if (!toneAnalysis) return null;
  const dimensions = [
    { key: 'confidence', label: 'Confidence' },
    { key: 'specificity', label: 'Specificity' },
    { key: 'defensiveness', label: 'Defensiveness' },
    { key: 'forward_looking', label: 'Forward-Looking' },
    { key: 'hedging', label: 'Hedging Language' },
  ];

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm" style={{ color: 'var(--text-primary)' }}>
          Management Tone Analysis
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex flex-col gap-2">
          {dimensions.map(({ key, label }) => {
            const value = toneAnalysis[key] ?? 50;
            const barColor = getToneBarColor(key, value);
            const valueLabel = getToneLabel(key, value);
            return (
              <div key={key}>
                <div className="flex justify-between mb-1">
                  <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>{label}</span>
                  <span className={`text-xs font-data ${barColor.replace('bg-', 'text-')}`}>{valueLabel}</span>
                </div>
                <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.06)' }}>
                  <div
                    className={`h-full rounded-full ${barColor}`}
                    style={{ width: `${value}%`, opacity: 0.8 }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
};

const QuarterIndicator = ({ availableQuarters }) => {
  if (!availableQuarters?.length) return null;
  return (
    <div className="flex gap-2 justify-center mt-4">
      {availableQuarters.map((q, i) => (
        <div
          key={i}
          className={`text-xs px-3 py-1 rounded-md border ${
            i === 0
              ? 'bg-accent-blue/15 border-accent-blue/30 text-accent-blue'
              : 'bg-white/[0.04] border-white/[0.08]'
          }`}
          style={i !== 0 ? { color: 'var(--text-muted)' } : {}}
        >
          Q{q.quarter} {q.year}
        </div>
      ))}
    </div>
  );
};

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

// ─── Main Component ──────────────────────────────────────────────────────────

const EarningsPanel = ({ analysis }) => {
  const data = getEarningsData(analysis);

  if (!data) {
    return (
      <div className="text-sm py-4 text-center" style={{ color: 'var(--text-muted)' }}>
        Earnings call data unavailable
      </div>
    );
  }

  return (
    <Motion.div variants={fadeUp} initial="hidden" animate="visible" className="flex flex-col" style={{ gap: 'var(--space-card-gap, 20px)' }}>
      <HeaderRow data={data} />

      {/* Summary — hybrid format: paragraph + bullets */}
      {data.summary && (
        <Card>
          <CardContent className="pt-5">
            <EarningsSummary text={data.summary} />
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2" style={{ gap: 'var(--space-card-gap, 20px)' }}>
        <HighlightsCard highlights={data.highlights} />
        <GuidanceCard guidance={data.guidance} />
      </div>

      <QACard qaHighlights={data.qa_highlights} />

      <div className="grid grid-cols-1 sm:grid-cols-2" style={{ gap: 'var(--space-card-gap, 20px)' }}>
        <EPSChart epsHistory={data.eps_history} />
        <ToneChart toneAnalysis={data.tone_analysis} />
      </div>

      <QuarterIndicator availableQuarters={data.available_quarters} />
    </Motion.div>
  );
};

export default EarningsPanel;
