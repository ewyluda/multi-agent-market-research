/**
 * ScenarioPanel - Bull/base/bear outcome framing with probabilities and return expectations.
 */

import React from 'react';
import { motion } from 'framer-motion';
import { TargetIcon } from './Icons';

const ORDERED_SCENARIOS = [
  { key: 'bull', label: 'Bull', barClass: 'bg-success', textClass: 'text-success-400' },
  { key: 'base', label: 'Base', barClass: 'bg-accent-blue', textClass: 'text-accent-blue' },
  { key: 'bear', label: 'Bear', barClass: 'bg-danger', textClass: 'text-danger-400' },
];

const getAnalysisPayload = (analysis) => analysis?.analysis || analysis?.analysis_payload || analysis || {};

const toProbability = (value) => {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return null;
  return Math.max(0, Math.min(1, numeric));
};

const formatReturn = (value) => {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return 'n/a';
  return `${numeric > 0 ? '+' : ''}${numeric.toFixed(1)}%`;
};

const ScenarioPanel = ({ analysis }) => {
  const payload = getAnalysisPayload(analysis);
  const scenarios = payload?.scenarios && typeof payload.scenarios === 'object' ? payload.scenarios : null;
  const scenarioSummary = payload?.scenario_summary;

  if (!scenarios) {
    return (
      <div className="glass-card-elevated rounded-xl p-5">
        <div className="flex items-center space-x-2 mb-2">
          <TargetIcon className="w-4 h-4 text-gray-500" />
          <span className="text-sm text-gray-400">Scenario framing unavailable</span>
        </div>
        <p className="text-xs text-gray-500">
          {scenarioSummary || 'Run a fresh analysis to generate bull/base/bear scenarios.'}
        </p>
      </div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="space-y-4"
    >
      <div className="glass-card-elevated rounded-xl p-5">
        <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider mb-1 flex items-center space-x-2">
          <TargetIcon className="w-4 h-4 text-accent-green" />
          <span>Scenario Analysis</span>
        </h3>
        <p className="text-xs text-gray-400">
          {scenarioSummary || 'Bull/base/bear probabilities with expected return framing.'}
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {ORDERED_SCENARIOS.map((item) => {
          const block = scenarios?.[item.key] || {};
          const probability = toProbability(block?.probability);
          const thesis = block?.thesis || 'No scenario thesis provided.';

          return (
            <div key={item.key} className="glass-card-elevated rounded-xl p-4">
              <div className="flex items-center justify-between mb-3">
                <span className={`text-sm font-semibold uppercase tracking-wider ${item.textClass}`}>
                  {item.label}
                </span>
                <span className="text-xs text-gray-300 font-mono tabular-nums">
                  {probability == null ? 'n/a' : `${(probability * 100).toFixed(0)}%`}
                </span>
              </div>

              <div className="h-1.5 bg-dark-inset rounded-full overflow-hidden mb-3">
                <div
                  className={`h-full ${item.barClass} transition-all duration-500`}
                  style={{ width: `${probability == null ? 0 : probability * 100}%` }}
                />
              </div>

              <div className="mb-3">
                <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Expected Return</div>
                <div className="text-sm font-semibold tabular-nums text-gray-200">
                  {formatReturn(block?.expected_return_pct)}
                </div>
              </div>

              <p className="text-xs text-gray-400 leading-relaxed">{thesis}</p>
            </div>
          );
        })}
      </div>
    </motion.div>
  );
};

export default ScenarioPanel;
