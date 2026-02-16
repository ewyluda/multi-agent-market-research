/**
 * DiagnosticsPanel - Signal disagreement and data-quality diagnostics.
 */

import React from 'react';
import { motion as Motion } from 'framer-motion';
import { ShieldExclamationIcon, CheckCircleIcon, XCircleIcon } from './Icons';

const getAnalysisPayload = (analysis) => analysis?.analysis || analysis?.analysis_payload || analysis || {};

const directionLabel = (direction) => {
  if (direction === 'bullish') return { text: 'Bullish', className: 'text-success-400 bg-success/10 border-success/25' };
  if (direction === 'bearish') return { text: 'Bearish', className: 'text-danger-400 bg-danger/10 border-danger/25' };
  return { text: 'Neutral', className: 'text-warning-400 bg-warning/10 border-warning/25' };
};

const qualityStyle = (qualityLevel) => {
  if (qualityLevel === 'good') return 'text-success-400 bg-success/10 border-success/25';
  if (qualityLevel === 'poor') return 'text-danger-400 bg-danger/10 border-danger/25';
  return 'text-warning-400 bg-warning/10 border-warning/25';
};

const DiagnosticsPanel = ({ analysis }) => {
  const payload = getAnalysisPayload(analysis);
  const diagnostics = payload?.diagnostics;
  const diagnosticsSummary = payload?.diagnostics_summary;

  if (!diagnostics) {
    return (
      <div className="glass-card-elevated rounded-xl p-5">
        <div className="flex items-center space-x-2 mb-2">
          <ShieldExclamationIcon className="w-4 h-4 text-gray-500" />
          <span className="text-sm text-gray-400">Diagnostics unavailable</span>
        </div>
        <p className="text-xs text-gray-500">
          {diagnosticsSummary || 'Run a fresh analysis to generate disagreement and data-quality diagnostics.'}
        </p>
      </div>
    );
  }

  const disagreement = diagnostics?.disagreement || {};
  const dataQuality = diagnostics?.data_quality || {};
  const directionEntries = Object.entries(disagreement?.agent_directions || {});
  const fallbackSources = Array.isArray(dataQuality?.fallback_source_agents)
    ? dataQuality.fallback_source_agents
    : [];

  return (
    <Motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="space-y-4"
    >
      <div
        className={`glass-card-elevated rounded-xl p-5 border ${
          disagreement?.is_conflicted ? 'border-danger/30' : 'border-success/20'
        }`}
      >
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider flex items-center space-x-2">
            <ShieldExclamationIcon className="w-4 h-4 text-accent-amber" />
            <span>Diagnostics</span>
          </h3>
          <span
            className={`text-[11px] font-semibold px-2 py-0.5 rounded border ${
              disagreement?.is_conflicted
                ? 'text-danger-400 bg-danger/10 border-danger/25'
                : 'text-success-400 bg-success/10 border-success/25'
            }`}
          >
            {disagreement?.is_conflicted ? 'Conflicted' : 'Aligned'}
          </span>
        </div>
        <p className="text-xs text-gray-400">
          {diagnosticsSummary || 'Conflict status and data reliability for this run.'}
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="glass-card-elevated rounded-xl p-4">
          <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">Signal Disagreement</h4>
          <div className="grid grid-cols-3 gap-2 mb-3">
            <div className="p-2 bg-dark-inset rounded border border-white/5 text-center">
              <div className="text-[10px] text-gray-500 uppercase tracking-wider">Bullish</div>
              <div className="text-sm font-semibold text-success-400">{disagreement?.bullish_count ?? 0}</div>
            </div>
            <div className="p-2 bg-dark-inset rounded border border-white/5 text-center">
              <div className="text-[10px] text-gray-500 uppercase tracking-wider">Neutral</div>
              <div className="text-sm font-semibold text-warning-400">{disagreement?.neutral_count ?? 0}</div>
            </div>
            <div className="p-2 bg-dark-inset rounded border border-white/5 text-center">
              <div className="text-[10px] text-gray-500 uppercase tracking-wider">Bearish</div>
              <div className="text-sm font-semibold text-danger-400">{disagreement?.bearish_count ?? 0}</div>
            </div>
          </div>

          {directionEntries.length === 0 ? (
            <p className="text-xs text-gray-500">No directional agent outputs available.</p>
          ) : (
            <div className="space-y-2">
              {directionEntries.map(([agent, direction]) => {
                const style = directionLabel(direction);
                return (
                  <div key={agent} className="flex items-center justify-between p-2 bg-dark-inset rounded border border-white/5">
                    <span className="text-xs text-gray-300 font-mono uppercase">{agent}</span>
                    <span className={`text-[11px] font-semibold px-2 py-0.5 rounded border ${style.className}`}>
                      {style.text}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div className="glass-card-elevated rounded-xl p-4">
          <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">Data Quality</h4>

          <div className="flex items-center justify-between p-2 bg-dark-inset rounded border border-white/5 mb-3">
            <span className="text-xs text-gray-400 uppercase tracking-wider">Quality Level</span>
            <span className={`text-[11px] font-semibold px-2 py-0.5 rounded border ${qualityStyle(dataQuality?.quality_level)}`}>
              {(dataQuality?.quality_level || 'warn').toUpperCase()}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-2 mb-3">
            <div className="p-2 bg-dark-inset rounded border border-white/5">
              <div className="text-[10px] text-gray-500 uppercase tracking-wider">Agent Success</div>
              <div className="text-sm font-semibold text-gray-200">
                {Number.isFinite(Number(dataQuality?.agent_success_rate))
                  ? `${Math.round(Number(dataQuality.agent_success_rate) * 100)}%`
                  : 'n/a'}
              </div>
            </div>
            <div className="p-2 bg-dark-inset rounded border border-white/5">
              <div className="text-[10px] text-gray-500 uppercase tracking-wider">News Freshness</div>
              <div className="text-sm font-semibold text-gray-200">
                {Number.isFinite(Number(dataQuality?.news_freshness_hours))
                  ? `${Number(dataQuality.news_freshness_hours).toFixed(1)}h`
                  : 'n/a'}
              </div>
            </div>
          </div>

          {fallbackSources.length > 0 && (
            <div className="mb-3">
              <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Fallback Sources</div>
              <div className="flex flex-wrap gap-1.5">
                {fallbackSources.map((item, idx) => (
                  <span
                    key={`${item.agent || 'agent'}-${idx}`}
                    className="text-[10px] px-2 py-0.5 rounded border border-accent-blue/25 bg-accent-blue/10 text-accent-blue"
                  >
                    {item.agent || 'agent'} ({item.source || 'unknown'})
                  </span>
                ))}
              </div>
            </div>
          )}

          {Array.isArray(dataQuality?.warnings) && dataQuality.warnings.length > 0 && (
            <div className="space-y-1.5">
              {dataQuality.warnings.map((warning, idx) => (
                <div key={idx} className="text-xs text-gray-300 flex items-start">
                  {warning.toLowerCase().includes('failed') ? (
                    <XCircleIcon className="w-3.5 h-3.5 text-danger-400 mr-1.5 mt-0.5" />
                  ) : (
                    <CheckCircleIcon className="w-3.5 h-3.5 text-warning-400 mr-1.5 mt-0.5" />
                  )}
                  <span>{warning}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </Motion.div>
  );
};

export default DiagnosticsPanel;
