/**
 * MacroSnapshot - Compact macroeconomic indicators widget for the sidebar
 */

import React from 'react';
import { GlobeIcon, TrendingUpIcon, TrendingDownIcon, ArrowUpIcon, ArrowDownIcon } from './Icons';

const TrendBadge = ({ trend }) => {
  if (!trend) return null;
  const isUp = trend === 'rising';
  const isDown = trend === 'falling';
  return (
    <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
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
    <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium capitalize ${colorMap[status] || 'bg-gray-500/15 text-gray-400'}`}>
      {label || status}
    </span>
  );
};

const MacroSnapshot = ({ analysis }) => {
  const macroData = analysis?.agent_results?.macro?.data;

  // Don't render if no macro data
  if (!macroData || macroData.data_source === 'none') return null;

  const indicators = macroData.indicators || {};
  const yieldCurve = macroData.yield_curve || {};
  const economicCycle = macroData.economic_cycle;
  const riskEnvironment = macroData.risk_environment;

  const fedFunds = indicators.federal_funds_rate || {};
  const inflation = indicators.inflation || {};
  const gdp = indicators.real_gdp || {};
  const yield10y = indicators.treasury_yield_10y || {};
  const unemployment = indicators.unemployment || {};

  // If all empty, don't render
  const hasData = fedFunds.current != null || inflation.current != null || gdp.current != null;
  if (!hasData) return null;

  return (
    <div className="glass-card-elevated rounded-xl p-5 animate-fade-in">
      <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider mb-4 flex items-center space-x-2">
        <GlobeIcon className="w-4 h-4 text-accent-cyan" />
        <span>Macro Environment</span>
      </h3>

      <div className="space-y-3">
        {/* Fed Funds Rate */}
        {fedFunds.current != null && (
          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-400">Fed Funds Rate</span>
            <div className="flex items-center space-x-2">
              <span className="text-xs font-semibold tabular-nums">{fedFunds.current.toFixed(2)}%</span>
              <TrendBadge trend={fedFunds.trend} />
            </div>
          </div>
        )}

        {/* 10Y Treasury */}
        {yield10y.current != null && (
          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-400">10Y Treasury</span>
            <div className="flex items-center space-x-2">
              <span className="text-xs font-semibold tabular-nums">{yield10y.current.toFixed(2)}%</span>
              <TrendBadge trend={yield10y.trend} />
            </div>
          </div>
        )}

        {/* Yield Curve */}
        {yieldCurve.spread != null && (
          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-400">Yield Curve</span>
            <div className="flex items-center space-x-2">
              <span className="text-xs font-semibold tabular-nums">{yieldCurve.spread > 0 ? '+' : ''}{yieldCurve.spread.toFixed(2)}%</span>
              <StatusBadge status={yieldCurve.status} />
            </div>
          </div>
        )}

        {/* Inflation */}
        {inflation.current != null && (
          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-400">Inflation</span>
            <div className="flex items-center space-x-2">
              <span className="text-xs font-semibold tabular-nums">{inflation.current.toFixed(1)}%</span>
              <TrendBadge trend={inflation.trend} />
            </div>
          </div>
        )}

        {/* Unemployment */}
        {unemployment.current != null && (
          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-400">Unemployment</span>
            <div className="flex items-center space-x-2">
              <span className="text-xs font-semibold tabular-nums">{unemployment.current.toFixed(1)}%</span>
              <TrendBadge trend={unemployment.trend} />
            </div>
          </div>
        )}

        {/* GDP */}
        {gdp.current != null && (
          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-400">Real GDP</span>
            <div className="flex items-center space-x-2">
              <span className="text-xs font-semibold tabular-nums">${(gdp.current / 1000).toFixed(1)}T</span>
              <TrendBadge trend={gdp.trend} />
            </div>
          </div>
        )}

        {/* Divider */}
        <div className="border-t border-white/5 pt-3 space-y-2.5">
          {/* Economic Cycle */}
          {economicCycle && economicCycle !== 'unknown' && (
            <div className="flex items-center justify-between">
              <span className="text-xs text-gray-400">Economic Cycle</span>
              <StatusBadge status={economicCycle} />
            </div>
          )}

          {/* Risk Environment */}
          {riskEnvironment && riskEnvironment !== 'unknown' && (
            <div className="flex items-center justify-between">
              <span className="text-xs text-gray-400">Risk Environment</span>
              <StatusBadge status={riskEnvironment} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default MacroSnapshot;
