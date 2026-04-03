/**
 * RiskDiffPanel - Risk factor diff visualization showing risk score changes,
 * emerging threats, detailed change cards, and filing metadata.
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

const getRiskData = (analysis) =>
  analysis?.analysis?.risk_diff || null;

const CHANGE_TYPE_COLORS = {
  NEW: { bg: 'rgba(243,18,96,0.1)', text: 'var(--danger)', border: 'rgba(243,18,96,0.25)' },
  ESCALATED: { bg: 'rgba(245,165,36,0.1)', text: 'var(--warning)', border: 'rgba(245,165,36,0.25)' },
  'DE-ESCALATED': { bg: 'rgba(23,201,100,0.1)', text: 'var(--success)', border: 'rgba(23,201,100,0.25)' },
  REMOVED: { bg: 'rgba(255,255,255,0.04)', text: 'rgba(255,255,255,0.4)', border: 'rgba(255,255,255,0.08)' },
  REWORDED: { bg: 'rgba(0,111,238,0.1)', text: 'var(--primary)', border: 'rgba(0,111,238,0.25)' },
};

const SEVERITY_BADGE_VARIANTS = {
  HIGH: 'danger',
  MEDIUM: 'warning',
  LOW: 'secondary',
};

const EXTRACTION_BADGE_VARIANTS = {
  pattern: 'secondary',
  llm_fallback: 'default',
};

// ─── Sub-components ──────────────────────────────────────────────────────────

const SummaryAndScore = ({ data }) => {
  const summary = data?.summary;
  const riskScore = data?.risk_score;
  const delta = data?.risk_score_delta;

  return (
    <Card className="mb-4">
      <CardContent className="pt-5">
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
                  className="text-3xl font-bold font-data"
                  style={{
                    color: riskScore > 70 ? 'var(--danger)' : riskScore > 40 ? 'var(--warning)' : 'var(--success)',
                  }}
                >
                  {riskScore}
                </div>
                {delta != null && delta !== 0 && (
                  <div
                    className="text-sm font-data mt-1"
                    style={{ color: delta > 0 ? 'var(--danger)' : 'var(--success)' }}
                  >
                    {delta > 0 ? '+' : ''}{delta}
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

const EmergingThreats = ({ threats }) => {
  if (!threats?.length) return null;

  return (
    <Card
      className="mb-4"
      style={{ background: 'rgba(243,18,96,0.04)', border: '1px solid rgba(243,18,96,0.15)' }}
    >
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center gap-2" style={{ color: 'var(--danger)' }}>
          <span>&#x26A0;</span> Emerging Threats
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex flex-wrap gap-2">
          {threats.map((threat, i) => (
            <Badge key={i} variant="danger" className="text-[11px] rounded-full">
              {typeof threat === 'string' ? threat : threat.name || threat.description}
            </Badge>
          ))}
        </div>
      </CardContent>
    </Card>
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
        const sevBadgeVariant = SEVERITY_BADGE_VARIANTS[severity] || 'warning';

        return (
          <Card key={i}>
            <CardContent className="pt-4">
              {/* Header badges */}
              <div className="flex items-center gap-2 mb-2">
                <span
                  className="text-[10px] px-2 py-0.5 rounded font-medium border"
                  style={{ background: typeColors.bg, color: typeColors.text, borderColor: typeColors.border }}
                >
                  {type}
                </span>
                <Badge variant={sevBadgeVariant} className="text-[10px]">
                  {severity}
                </Badge>
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
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
};

const RiskInventoryTable = ({ inventory }) => {
  if (!inventory?.length) return null;

  return (
    <Card className="mb-4">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm" style={{ color: 'var(--text-primary)' }}>
          Risk Inventory
        </CardTitle>
      </CardHeader>
      <CardContent>
        <Table>
          <TableBody>
            {inventory.map((item, i) => {
              const severity = item.severity?.toUpperCase() || 'MEDIUM';
              const sevBadgeVariant = SEVERITY_BADGE_VARIANTS[severity] || 'warning';
              return (
                <TableRow key={i}>
                  <TableCell className="w-24">
                    <Badge variant={sevBadgeVariant} className="text-[10px]">
                      {severity}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-[12px]" style={{ color: 'var(--text-secondary)' }}>
                    {item.description || item.name || item}
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

const FilingMetadata = ({ filings }) => {
  if (!filings?.length) return null;

  return (
    <Card>
      <CardContent className="pt-3 pb-3">
        <div className="flex flex-wrap gap-2 items-center">
          <span className="text-[11px] font-medium" style={{ color: 'var(--text-muted)' }}>Filings:</span>
          {filings.map((f, i) => {
            const method = f.extraction_method?.toLowerCase() || 'pattern';
            const methodBadgeVariant = EXTRACTION_BADGE_VARIANTS[method] || 'secondary';
            return (
              <div key={i} className="flex items-center gap-1.5">
                <span className="text-[11px]" style={{ color: 'var(--text-secondary)' }}>
                  {f.type || f.filing_type} {f.date && `(${f.date})`}
                </span>
                <Badge variant={methodBadgeVariant} className="text-[9px]">
                  {method}
                </Badge>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
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
        <Card className="mb-4 text-center">
          <CardContent className="pt-4">
            <div className="text-sm" style={{ color: 'var(--text-muted)' }}>
              Only 1 filing available — no diff
            </div>
          </CardContent>
        </Card>
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
