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
