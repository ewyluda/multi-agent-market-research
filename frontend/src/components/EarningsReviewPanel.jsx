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
  call_disclosed: { bg: 'rgba(0,111,238,0.1)', text: '#006fee' },
  calc: { bg: 'rgba(255,255,255,0.06)', text: 'rgba(255,255,255,0.4)' },
  calculated: { bg: 'rgba(255,255,255,0.06)', text: 'rgba(255,255,255,0.4)' },
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
