/**
 * MacroPage - Standalone macro environment page
 * Shows macro economic indicators and summary.
 */

import React, { useState, useEffect } from 'react';
import { motion as Motion } from 'framer-motion';

const fadeUp = {
  hidden: { opacity: 0, y: 12 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.22, 1, 0.36, 1] } },
};

const MetricCard = ({ label, value }) => (
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
  </div>
);

const MacroPage = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchMacro = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch('/api/macro-events');
        if (!res.ok) throw new Error(`Failed to fetch macro data (${res.status})`);
        const json = await res.json();
        setData(json);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    fetchMacro();
  }, []);

  if (loading) {
    return (
      <div className="px-6 py-8">
        <div className="skeleton h-8 w-48 mb-6 rounded-lg" />
        <div className="grid grid-cols-3 gap-4">
          <div className="skeleton h-24 rounded-lg" />
          <div className="skeleton h-24 rounded-lg" />
          <div className="skeleton h-24 rounded-lg" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="px-6 py-8">
        <div className="glass-card rounded-xl p-6 text-center">
          <p className="text-sm" style={{ color: 'var(--accent-red)' }}>{error}</p>
        </div>
      </div>
    );
  }

  const indicators = data?.indicators || data || {};
  const summary = data?.summary || data?.analysis || null;
  const lastUpdated = data?.last_updated || data?.timestamp || null;

  return (
    <div className="px-6 py-8">
      <Motion.div variants={fadeUp} initial="hidden" animate="visible">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
            Macro Environment
          </h1>
          {lastUpdated && (
            <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
              Updated: {new Date(lastUpdated).toLocaleString()}
            </span>
          )}
        </div>

        <div
          className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4"
          style={{ gap: 'var(--space-card-gap, 20px)', marginBottom: 'var(--space-section-gap, 32px)' }}
        >
          {indicators.fed_funds_rate != null && (
            <MetricCard label="Fed Funds Rate" value={`${indicators.fed_funds_rate}%`} />
          )}
          {indicators.cpi != null && (
            <MetricCard label="CPI" value={`${indicators.cpi}%`} />
          )}
          {indicators.gdp_growth != null && (
            <MetricCard label="GDP Growth" value={`${indicators.gdp_growth}%`} />
          )}
          {indicators.unemployment_rate != null && (
            <MetricCard label="Unemployment" value={`${indicators.unemployment_rate}%`} />
          )}
          {indicators.treasury_10y != null && (
            <MetricCard label="10Y Treasury" value={`${indicators.treasury_10y}%`} />
          )}
          {indicators.treasury_2y != null && (
            <MetricCard label="2Y Treasury" value={`${indicators.treasury_2y}%`} />
          )}
        </div>

        {summary && (
          <div className="glass-card rounded-xl" style={{ padding: 'var(--space-card-padding, 20px)' }}>
            <div className="text-sm font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>
              Analysis
            </div>
            <div className="text-[0.88rem] leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              {summary}
            </div>
          </div>
        )}
      </Motion.div>
    </div>
  );
};

export default MacroPage;
