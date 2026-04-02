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
