/**
 * CompanyOverview - Composite section combining Company Description,
 * Narrative, and Fundamentals into stacked glass cards.
 */

import React from 'react';
import { motion as Motion } from 'framer-motion';
import NarrativePanel from './NarrativePanel';

const fadeUp = {
  hidden: { opacity: 0, y: 12 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.22, 1, 0.36, 1] } },
};

// ─── Metric Card ────────────────────────────────────────────────────────────

const MetricCard = ({ label, value, delta }) => (
  <div
    className="bg-dark-inset rounded-lg border border-white/[0.04] hover:border-white/[0.08] transition-colors"
    style={{ padding: 'var(--space-card-padding, 20px)' }}
  >
    <div className="text-[11px] uppercase tracking-wider font-medium" style={{ color: 'var(--text-muted)' }}>
      {label}
    </div>
    <div className="text-lg font-bold mt-1 font-mono tabular-nums" style={{ color: 'var(--text-primary)' }}>
      {value}
    </div>
    {delta && (
      <div
        className="text-[11px] mt-0.5 font-mono"
        style={{ color: delta.startsWith('+') || delta.startsWith('▲') ? 'var(--accent-green)' : 'var(--accent-red)' }}
      >
        {delta}
      </div>
    )}
  </div>
);

// ─── Description Card ───────────────────────────────────────────────────────

const DescriptionCard = ({ data }) => {
  const description = data?.company_overview || data?.description || data?.company_description || null;
  if (!description) return null;

  return (
    <div className="glass-card rounded-xl" style={{ padding: 'var(--space-card-padding, 20px)' }}>
      <div className="text-sm font-semibold mb-3 flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
        <span style={{ color: 'var(--accent-blue)' }}>◆</span> Company Description
      </div>
      <p className="text-[0.88rem] leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
        {description}
      </p>
    </div>
  );
};

// ─── Fundamentals Metrics Card ──────────────────────────────────────────────

const FundamentalsCard = ({ data }) => {
  if (!data) return null;

  const metrics = [
    data.pe_ratio != null && { label: 'P/E Ratio', value: Number(data.pe_ratio).toFixed(1) },
    data.revenue_growth != null && { label: 'Rev Growth', value: `${(data.revenue_growth * 100).toFixed(1)}%` },
    (data.profit_margin ?? data.net_margin) != null && {
      label: 'Net Margin',
      value: `${((data.profit_margin ?? data.net_margin) * 100).toFixed(1)}%`,
    },
    (data.health_score ?? data.fundamental_health_score) != null && {
      label: 'Health Score',
      value: `${data.health_score ?? data.fundamental_health_score}/100`,
    },
    data.market_cap != null && {
      label: 'Market Cap',
      value: formatMarketCap(data.market_cap),
    },
    data.eps != null && { label: 'EPS', value: `$${Number(data.eps).toFixed(2)}` },
    data.dividend_yield != null && {
      label: 'Div Yield',
      value: `${(data.dividend_yield * 100).toFixed(2)}%`,
    },
  ].filter(Boolean);

  const summary = data.analysis || data.summary || null;

  return (
    <div className="glass-card rounded-xl" style={{ padding: 'var(--space-card-padding, 20px)' }}>
      <div className="text-sm font-semibold mb-4 flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
        <span style={{ color: 'var(--accent-green)' }}>◆</span> Fundamentals
      </div>

      {metrics.length > 0 ? (
        <div
          className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4"
          style={{ gap: 'var(--space-metrics-gap, 16px)', marginBottom: summary ? '20px' : '0' }}
        >
          {metrics.map((m, i) => (
            <MetricCard key={i} label={m.label} value={m.value} />
          ))}
        </div>
      ) : null}

      {summary && (
        <div className="text-[0.88rem] leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
          {formatParagraphs(summary)}
        </div>
      )}
    </div>
  );
};

// ─── Helpers ────────────────────────────────────────────────────────────────

function formatMarketCap(value) {
  if (value == null) return 'N/A';
  const num = Number(value);
  if (num >= 1e12) return `$${(num / 1e12).toFixed(2)}T`;
  if (num >= 1e9) return `$${(num / 1e9).toFixed(2)}B`;
  if (num >= 1e6) return `$${(num / 1e6).toFixed(0)}M`;
  return `$${num.toLocaleString()}`;
}

function formatParagraphs(text) {
  if (!text) return null;
  const paragraphs = text.split(/\n\n+/).filter(Boolean);
  if (paragraphs.length <= 1) return text;
  return paragraphs.map((p, i) => (
    <p key={i} className={i > 0 ? 'mt-3' : ''}>{p}</p>
  ));
}

// ─── Main Component ─────────────────────────────────────────────────────────

const CompanyOverview = ({ analysis }) => {
  const fundamentalsData = analysis?.agent_results?.fundamentals?.data || null;
  const hasNarrative = !!(analysis?.analysis?.narrative);

  return (
    <Motion.div
      variants={fadeUp}
      initial="hidden"
      animate="visible"
      className="flex flex-col"
      style={{ gap: 'var(--space-card-gap, 20px)' }}
    >
      <DescriptionCard data={fundamentalsData} />

      {hasNarrative && <NarrativePanel analysis={analysis} />}

      <FundamentalsCard data={fundamentalsData} />
    </Motion.div>
  );
};

export default CompanyOverview;
