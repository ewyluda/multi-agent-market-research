/**
 * MacroSnapshot - Compact macroeconomic indicators widget for the sidebar
 * Includes yield curve mini-visualization and graceful empty state
 */

import React from 'react';
import { motion } from 'framer-motion';
import { GlobeIcon } from './Icons';

const TrendBadge = ({ trend }) => {
  if (!trend) return null;
  const isUp = trend === 'rising';
  const isDown = trend === 'falling';
  return (
    <span className={`text-[11px] px-2 py-0.5 rounded font-medium ${
      isUp ? 'bg-success/15 text-success-400' :
      isDown ? 'bg-danger/15 text-danger-400' :
      'bg-gray-500/15 text-gray-400'
    }`}>
      {isUp ? '↑' : isDown ? '↓' : '→'} {trend}
    </span>
  );
};

const StatusBadge = ({ status, label }) => {
  const colorMap = {
    normal: 'bg-success/15 text-success-400',
    flat: 'bg-warning/15 text-warning-400',
    inverted: 'bg-danger/15 text-danger-400',
    expansion: 'bg-success/15 text-success-400',
    peak: 'bg-warning/15 text-warning-400',
    contraction: 'bg-danger/15 text-danger-400',
    trough: 'bg-accent-blue/15 text-accent-blue',
    dovish: 'bg-success/15 text-success-400',
    hawkish: 'bg-danger/15 text-danger-400',
    transitional: 'bg-warning/15 text-warning-400',
  };
  return (
    <span className={`text-[11px] px-2 py-0.5 rounded font-medium capitalize ${colorMap[status] || 'bg-gray-500/15 text-gray-400'}`}>
      {label || status}
    </span>
  );
};

const MacroSnapshot = ({ analysis }) => {
  const macroData = analysis?.agent_results?.macro?.data;

  // Graceful empty state instead of null
  if (!macroData || macroData.data_source === 'none') {
    return (
      <div className="glass-card-elevated rounded-xl p-5">
        <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3 flex items-center space-x-2">
          <GlobeIcon className="w-4 h-4 text-gray-600" />
          <span>Macro Environment</span>
        </h3>
        <p className="text-xs text-gray-600 leading-relaxed">
          Macro data unavailable. Enable the macro agent to see US economic indicators.
        </p>
      </div>
    );
  }

  const indicators = macroData.indicators || {};
  const yieldCurve = macroData.yield_curve || {};
  const economicCycle = macroData.economic_cycle;
  const riskEnvironment = macroData.risk_environment;

  const fedFunds = indicators.federal_funds_rate || {};
  const inflation = indicators.inflation || {};
  const gdp = indicators.real_gdp || {};
  const yield10y = indicators.treasury_yield_10y || {};
  const yield2y = indicators.treasury_yield_2y || {};
  const unemployment = indicators.unemployment || {};

  const hasData = fedFunds.current != null || inflation.current != null || gdp.current != null;
  if (!hasData) {
    return (
      <div className="glass-card-elevated rounded-xl p-5">
        <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3 flex items-center space-x-2">
          <GlobeIcon className="w-4 h-4 text-gray-600" />
          <span>Macro Environment</span>
        </h3>
        <p className="text-xs text-gray-600 leading-relaxed">
          No macro indicator data returned for this analysis.
        </p>
      </div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, x: 12 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.4, delay: 0.2 }}
      className="glass-card-elevated rounded-xl p-5"
    >
      <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider mb-4 flex items-center space-x-2">
        <GlobeIcon className="w-4 h-4 text-accent-cyan" />
        <span>Macro Environment</span>
      </h3>

      <div className="space-y-2.5">
        {/* Fed Funds Rate */}
        {fedFunds.current != null && (
          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-400">Fed Funds Rate</span>
            <div className="flex items-center space-x-2">
              <span className="text-xs font-semibold font-mono">{fedFunds.current.toFixed(2)}%</span>
              <TrendBadge trend={fedFunds.trend} />
            </div>
          </div>
        )}

        {/* Yield Curve Mini-Visualization */}
        {(yield2y.current != null || yield10y.current != null) && (
          <div className="p-3 bg-dark-inset rounded-lg">
            <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Yield Curve</div>
            <div className="flex items-end space-x-4 h-20">
              {/* 2Y bar */}
              {yield2y.current != null && (
                <div className="flex flex-col items-center flex-1">
                  <div
                    className="w-full rounded-t transition-all min-h-[6px]"
                    style={{
                      height: `${Math.min(100, Math.max(15, yield2y.current * 10))}%`,
                      background: 'linear-gradient(to top, rgba(51, 142, 247, 0.15), rgba(51, 142, 247, 0.45))',
                      borderTop: '2px solid rgba(51, 142, 247, 0.7)',
                    }}
                  />
                  <span className="text-[10px] text-gray-500 mt-1 font-mono">2Y</span>
                </div>
              )}
              {/* 10Y bar */}
              {yield10y.current != null && (
                <div className="flex flex-col items-center flex-1">
                  <div
                    className="w-full rounded-t transition-all min-h-[6px]"
                    style={{
                      height: `${Math.min(100, Math.max(15, yield10y.current * 10))}%`,
                      background: 'linear-gradient(to top, rgba(0, 111, 238, 0.15), rgba(0, 111, 238, 0.45))',
                      borderTop: '2px solid rgba(0, 111, 238, 0.7)',
                    }}
                  />
                  <span className="text-[10px] text-gray-500 mt-1 font-mono">10Y</span>
                </div>
              )}
            </div>
            <div className="flex justify-between mt-1.5">
              <span className="text-[10px] font-mono text-gray-400">
                {yield2y.current != null ? `${yield2y.current.toFixed(2)}%` : '—'}
              </span>
              {yieldCurve.status && <StatusBadge status={yieldCurve.status} />}
              <span className="text-[10px] font-mono text-gray-400">
                {yield10y.current != null ? `${yield10y.current.toFixed(2)}%` : '—'}
              </span>
            </div>
            {yieldCurve.spread != null && (
              <div className="text-center mt-1">
                <span className="text-[10px] font-mono text-gray-500">
                  Spread: {yieldCurve.spread > 0 ? '+' : ''}{yieldCurve.spread.toFixed(2)}%
                </span>
              </div>
            )}
          </div>
        )}

        {/* Divider between rates and economy indicators */}
        <div className="border-t border-white/[0.04] my-0.5" />

        {/* Inflation */}
        {inflation.current != null && (
          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-400">Inflation</span>
            <div className="flex items-center space-x-2">
              <span className="text-xs font-semibold font-mono">{inflation.current.toFixed(1)}%</span>
              <TrendBadge trend={inflation.trend} />
            </div>
          </div>
        )}

        {/* Unemployment */}
        {unemployment.current != null && (
          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-400">Unemployment</span>
            <div className="flex items-center space-x-2">
              <span className="text-xs font-semibold font-mono">{unemployment.current.toFixed(1)}%</span>
              <TrendBadge trend={unemployment.trend} />
            </div>
          </div>
        )}

        {/* GDP */}
        {gdp.current != null && (
          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-400">Real GDP</span>
            <div className="flex items-center space-x-2">
              <span className="text-xs font-semibold font-mono">${(gdp.current / 1000).toFixed(1)}T</span>
              <TrendBadge trend={gdp.trend} />
            </div>
          </div>
        )}

        {/* Divider + Status */}
        <div className="border-t border-white/[0.04] pt-2 space-y-2">
          {economicCycle && economicCycle !== 'unknown' && (
            <div className="flex items-center justify-between">
              <span className="text-xs text-gray-400">Economic Cycle</span>
              <StatusBadge status={economicCycle} />
            </div>
          )}
          {riskEnvironment && riskEnvironment !== 'unknown' && (
            <div className="flex items-center justify-between">
              <span className="text-xs text-gray-400">Risk Environment</span>
              <StatusBadge status={riskEnvironment} />
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
};

export default MacroSnapshot;
