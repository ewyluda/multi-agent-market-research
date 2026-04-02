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
