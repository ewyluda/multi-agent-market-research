/**
 * EarningsReviewPanel - Deep earnings review with beat/miss verdicts,
 * KPI table, notable quotes, thesis impact, and one-off flags.
 */

import React from 'react';
import { motion as Motion } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

const fadeUp = {
  hidden: { opacity: 0, y: 12 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.22, 1, 0.36, 1] } },
};

// ─── Helpers ─────────────────────────────────────────────────────────────────

const getReviewData = (analysis) =>
  analysis?.analysis?.earnings_review || null;

const VERDICT_BADGE_VARIANTS = {
  beat: 'success',
  miss: 'danger',
  inline: 'secondary',
};

const SOURCE_BADGE_VARIANTS = {
  reported: 'secondary',
  call: 'default',
  call_disclosed: 'default',
  calc: 'secondary',
  calculated: 'secondary',
};

// ─── Sub-components ──────────────────────────────────────────────────────────

const ExecutiveSummary = ({ summary }) => {
  if (!summary) return null;
  return (
    <Card className="mb-4">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
          <span style={{ color: 'var(--primary)' }}>&#x2726;</span> Executive Summary
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-[13px] leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
          {summary}
        </p>
      </CardContent>
    </Card>
  );
};

const BeatMissBadges = ({ beatMiss }) => {
  if (!beatMiss?.length) return null;

  return (
    <div className="grid grid-cols-3 gap-3 mb-4">
      {beatMiss.map((item, i) => {
        const verdict = item.verdict?.toLowerCase() || 'inline';
        const badgeVariant = VERDICT_BADGE_VARIANTS[verdict] || 'secondary';
        return (
          <Card key={i}>
            <CardContent className="pt-4 text-center">
              <div className="text-[11px] uppercase tracking-wider mb-2" style={{ color: 'var(--text-muted)' }}>
                {item.metric || item.label}
              </div>
              <Badge variant={badgeVariant} className="capitalize text-base font-bold px-3 py-1">
                {verdict}
              </Badge>
              {item.detail && (
                <div className="text-[11px] mt-2" style={{ color: 'var(--text-muted)' }}>
                  {item.detail}
                </div>
              )}
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
};

const KPITable = ({ kpis }) => {
  if (!kpis?.length) return null;

  return (
    <Card className="mb-4">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm" style={{ color: 'var(--text-primary)' }}>
          Key Performance Indicators
        </CardTitle>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="text-[11px]">Metric</TableHead>
              <TableHead className="text-right text-[11px]">Value</TableHead>
              <TableHead className="text-right text-[11px]">Prior</TableHead>
              <TableHead className="text-right text-[11px]">YoY</TableHead>
              <TableHead className="text-right text-[11px]">Source</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {kpis.map((kpi, i) => {
              const source = kpi.source?.toLowerCase() || 'reported';
              const srcBadgeVariant = SOURCE_BADGE_VARIANTS[source] || 'secondary';
              const yoyVal = kpi.yoy_change || kpi.yoy;
              const yoyColor = yoyVal && typeof yoyVal === 'string' && yoyVal.startsWith('-') ? 'var(--danger)' : 'var(--success)';
              return (
                <TableRow key={i}>
                  <TableCell className="text-[13px]" style={{ color: 'var(--text-secondary)' }}>{kpi.metric || kpi.name}</TableCell>
                  <TableCell className="text-right text-[13px] font-data" style={{ color: 'var(--text-primary)' }}>{kpi.value}</TableCell>
                  <TableCell className="text-right text-[13px] font-data" style={{ color: 'var(--text-muted)' }}>{kpi.prior || '—'}</TableCell>
                  <TableCell className="text-right text-[13px] font-data" style={{ color: yoyVal ? yoyColor : 'var(--text-muted)' }}>
                    {yoyVal || '—'}
                  </TableCell>
                  <TableCell className="text-right">
                    <Badge variant={srcBadgeVariant} className="text-[10px]">
                      {source}
                    </Badge>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
};

const BottomRow = ({ quotes, thesisImpact, oneOffs, partial }) => {
  const hasQuotes = quotes?.length > 0;
  const hasImpact = thesisImpact || oneOffs?.length > 0;
  if (!hasQuotes && !hasImpact) return null;

  if (partial) {
    return (
      <Card>
        <CardContent className="pt-4">
          <div className="text-sm text-center py-2" style={{ color: 'var(--text-muted)' }}>
            No transcript available — LLM-derived sections limited
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
      {/* Notable Quotes */}
      {hasQuotes && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm" style={{ color: 'var(--text-primary)' }}>Notable Quotes</CardTitle>
          </CardHeader>
          <CardContent>
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
          </CardContent>
        </Card>
      )}

      {/* Thesis Impact + One-offs */}
      {hasImpact && (
        <Card>
          <CardContent className="pt-5">
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
                  <span style={{ color: 'var(--warning)' }}>&#x26A0;</span> One-off Items
                </div>
                <div className="flex flex-col gap-1.5">
                  {oneOffs.map((item, i) => (
                    <div
                      key={i}
                      className="text-[12px] px-2 py-1 rounded"
                      style={{ background: 'rgba(245,165,36,0.08)', color: 'var(--warning)' }}
                    >
                      {item.description || item}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
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
