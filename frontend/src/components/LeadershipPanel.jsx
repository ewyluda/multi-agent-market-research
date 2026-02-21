/**
 * LeadershipPanel - Four Capitals leadership assessment display
 * Shows overall leadership grade, red flags, four capitals scores, and key metrics
 */

import React, { useState } from 'react';
import { motion as Motion, AnimatePresence } from 'framer-motion';
import { ChevronDownIcon, CheckCircleIcon } from './Icons';

// Helper to extract leadership data from analysis payload
const getLeadershipData = (analysis) => {
  return analysis?.agent_results?.leadership?.data || null;
};

// Grade color mapping
const getGradeColor = (grade) => {
  if (!grade) return { text: 'text-gray-400', bg: 'bg-gray-400/10', border: 'border-gray-400/25' };
  const normalized = grade.toUpperCase();
  if (normalized.startsWith('A')) return { text: 'text-success-400', bg: 'bg-success/10', border: 'border-success/25' };
  if (normalized.startsWith('B')) return { text: 'text-accent-blue', bg: 'bg-accent-blue/10', border: 'border-accent-blue/25' };
  if (normalized.startsWith('C')) return { text: 'text-warning-400', bg: 'bg-warning/10', border: 'border-warning/25' };
  return { text: 'text-danger-400', bg: 'bg-danger/10', border: 'border-danger/25' };
};

// Severity color mapping
const getSeverityColor = (severity) => {
  switch (severity?.toLowerCase()) {
    case 'critical': return { text: 'text-danger-400', bg: 'bg-danger/10', border: 'border-danger/25', dot: 'bg-danger-400' };
    case 'high': return { text: 'text-orange-400', bg: 'bg-orange-400/10', border: 'border-orange-400/25', dot: 'bg-orange-400' };
    case 'medium': return { text: 'text-warning-400', bg: 'bg-warning/10', border: 'border-warning/25', dot: 'bg-warning-400' };
    default: return { text: 'text-accent-blue', bg: 'bg-accent-blue/10', border: 'border-accent-blue/25', dot: 'bg-accent-blue' };
  }
};

// Four capitals configuration
const CAPITALS_CONFIG = [
  { key: 'individual', label: 'Individual', icon: '👤' },
  { key: 'relational', label: 'Relational', icon: '🤝' },
  { key: 'organizational', label: 'Organizational', icon: '🏢' },
  { key: 'reputational', label: 'Reputational', icon: '⭐' },
];

// Format date string
const formatDate = (dateStr) => {
  if (!dateStr) return 'N/A';
  try {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  } catch {
    return dateStr;
  }
};

// Icon components for leadership panel
const UsersGroupIcon = (props) => (
  <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" {...props}>
    <path d="M14 7a2 2 0 100-4 2 2 0 000 4z" />
    <path d="M6 7a2 2 0 100-4 2 2 0 000 4z" />
    <path d="M14 11c2.5 0 4 1.5 4 3v1H10v-1c0-1.5 1.5-3 4-3z" />
    <path d="M6 11c2.5 0 4 1.5 4 3v1H2v-1c0-1.5 1.5-3 4-3z" />
  </svg>
);

const FlagAlertIcon = (props) => (
  <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" {...props}>
    <path d="M4 3v14" />
    <path d="M4 3h10a2 2 0 012 2v6a2 2 0 01-2 2H4" />
  </svg>
);

const AlertTriangleIcon = (props) => (
  <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" {...props}>
    <path d="M10 3l7 13H3L10 3z" />
    <path d="M10 8v4M10 14v.5" />
  </svg>
);

const CapitalCard = ({ capital, config, isExpanded, onToggle }) => {
  const colors = getGradeColor(capital?.grade);
  const hasRedFlags = capital?.red_flags?.length > 0;
  const firstInsight = capital?.insights?.[0];

  return (
    <Motion.div
      layout
      onClick={onToggle}
      className={`glass-card-elevated rounded-xl p-3 cursor-pointer transition-all duration-200 hover:bg-white/[0.03] ${
        isExpanded ? 'col-span-2 row-span-2' : ''
      }`}
    >
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center space-x-2">
          <span className="text-lg">{config.icon}</span>
          <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">{config.label}</span>
        </div>
        <div className={`text-[11px] font-semibold px-2 py-0.5 rounded border ${colors.bg} ${colors.text} ${colors.border}`}>
          {capital?.grade || 'N/A'} {capital?.score ?? '-'}
        </div>
      </div>

      <div className="flex items-center space-x-1.5">
        {hasRedFlags ? (
          <AlertTriangleIcon className="w-3.5 h-3.5 text-warning-400" />
        ) : (
          <CheckCircleIcon className="w-3.5 h-3.5 text-success-400" />
        )}
        <span className="text-xs text-gray-300 truncate">
          {firstInsight || (hasRedFlags ? 'Issues detected' : 'Assessment complete')}
        </span>
      </div>

      <AnimatePresence>
        {isExpanded && (
          <Motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2 }}
            className="mt-3 pt-3 border-t border-white/5"
          >
            {capital?.insights?.length > 1 && (
              <div className="space-y-1.5 mb-3">
                <div className="text-[10px] text-gray-500 uppercase tracking-wider">Insights</div>
                {capital.insights.slice(1).map((insight, idx) => (
                  <div key={idx} className="text-xs text-gray-300 flex items-start">
                    <span className="text-accent-blue mr-1.5">•</span>
                    {insight}
                  </div>
                ))}
              </div>
            )}

            {hasRedFlags && (
              <div className="space-y-1.5">
                <div className="text-[10px] text-warning-400 uppercase tracking-wider">Red Flags</div>
                {capital.red_flags.map((flag, idx) => (
                  <div key={idx} className="text-xs text-warning-400 flex items-start">
                    <AlertTriangleIcon className="w-3 h-3 mr-1.5 mt-0.5 flex-shrink-0" />
                    {flag}
                  </div>
                ))}
              </div>
            )}
          </Motion.div>
        )}
      </AnimatePresence>
    </Motion.div>
  );
};

const LeadershipPanel = ({ analysis }) => {
  const [expandedCapital, setExpandedCapital] = useState(null);
  const [showFullSummary, setShowFullSummary] = useState(false);

  const leadershipData = getLeadershipData(analysis);

  if (!leadershipData) {
    return (
      <div className="glass-card-elevated rounded-xl p-5">
        <div className="flex items-center space-x-2 mb-2">
          <UsersGroupIcon className="w-4 h-4 text-gray-500" />
          <span className="text-sm text-gray-400">Leadership assessment unavailable</span>
        </div>
        <p className="text-xs text-gray-500">
          Run a fresh analysis to generate leadership quality assessment using the Four Capitals framework.
        </p>
      </div>
    );
  }

  const {
    overall_score = 0,
    grade = 'N/A',
    assessment_date,
    four_capitals = {},
    key_metrics = {},
    red_flags = [],
    executive_summary = '',
  } = leadershipData;

  const gradeColors = getGradeColor(grade);
  const redFlagCount = red_flags.length;

  return (
    <Motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="space-y-4"
    >
      {/* Header Card */}
      <div className="glass-card-elevated rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-2">
            <UsersGroupIcon className="w-4 h-4 text-accent-blue" />
            <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">
              Leadership Assessment
            </h3>
          </div>
          <div className={`text-lg font-bold px-3 py-1 rounded-lg border ${gradeColors.bg} ${gradeColors.text} ${gradeColors.border}`}>
            Grade: {grade}
          </div>
        </div>

        <div className="flex items-center justify-between mb-3">
          <div>
            <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Overall Score</div>
            <div className="text-3xl font-bold text-gray-200">{overall_score}/100</div>
          </div>
          <div className="text-right">
            <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Last Updated</div>
            <div className="text-xs text-gray-400">{formatDate(assessment_date)}</div>
          </div>
        </div>

        {/* Score Progress Bar */}
        <div className="h-2 bg-dark-inset rounded-full overflow-hidden">
          <Motion.div
            initial={{ width: 0 }}
            animate={{ width: `${overall_score}%` }}
            transition={{ duration: 0.5, ease: 'easeOut' }}
            className={`h-full ${gradeColors.text.replace('text-', 'bg-')}`}
          />
        </div>
      </div>

      {/* Red Flags Panel */}
      {redFlagCount > 0 && (
        <Motion.div
          initial={{ opacity: 0, scale: 0.98 }}
          animate={{ opacity: 1, scale: 1 }}
          className="glass-card-elevated rounded-xl p-4 border border-danger/30"
        >
          <div className="flex items-center space-x-2 mb-3">
            <FlagAlertIcon className="w-4 h-4 text-danger-400" />
            <h4 className="text-sm font-semibold text-danger-400">
              {redFlagCount} Red Flag{redFlagCount > 1 ? 's' : ''} Detected
            </h4>
          </div>
          <div className="space-y-2">
            {red_flags.map((flag, idx) => {
              const colors = getSeverityColor(flag.severity);
              return (
                <div key={idx} className="flex items-start space-x-3 p-2 bg-dark-inset rounded border border-white/5">
                  <span className={`w-2 h-2 rounded-full mt-1.5 ${colors.dot}`} />
                  <div className="flex-1">
                    <div className="flex items-center space-x-2 mb-0.5">
                      <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${colors.bg} ${colors.text}`}>
                        {flag.severity?.toUpperCase() || 'MEDIUM'}
                      </span>
                      <span className="text-[10px] text-gray-500">{flag.type}</span>
                    </div>
                    <p className="text-xs text-gray-300">{flag.description}</p>
                    {flag.source && (
                      <p className="text-[10px] text-gray-500 mt-0.5">Source: {flag.source}</p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </Motion.div>
      )}

      {/* Four Capitals Grid */}
      <div className="glass-card-elevated rounded-xl p-5">
        <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-4">
          Four Capitals Framework
        </h4>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {CAPITALS_CONFIG.map((config) => (
            <CapitalCard
              key={config.key}
              capital={four_capitals[config.key]}
              config={config}
              isExpanded={expandedCapital === config.key}
              onToggle={() => setExpandedCapital(expandedCapital === config.key ? null : config.key)}
            />
          ))}
        </div>
      </div>

      {/* Key Metrics */}
      <div className="glass-card-elevated rounded-xl p-5">
        <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-4">Key Metrics</h4>
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
          <div className="p-3 bg-dark-inset rounded border border-white/5">
            <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">CEO Tenure</div>
            <div className="text-lg font-semibold text-gray-200">
              {key_metrics.ceo_tenure_years ? `${key_metrics.ceo_tenure_years.toFixed(1)} years` : 'N/A'}
            </div>
          </div>
          <div className="p-3 bg-dark-inset rounded border border-white/5">
            <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">C-Suite Turnover</div>
            <div className="text-lg font-semibold text-gray-200">
              {key_metrics.c_suite_turnover_12m !== undefined
                ? `${key_metrics.c_suite_turnover_12m} (12m) / ${key_metrics.c_suite_turnover_24m ?? '-'} (24m)`
                : 'N/A'}
            </div>
          </div>
          <div className="p-3 bg-dark-inset rounded border border-white/5">
            <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Board Independence</div>
            <div className="text-lg font-semibold text-gray-200">
              {key_metrics.board_independence_pct ? `${key_metrics.board_independence_pct}%` : 'N/A'}
            </div>
          </div>
          <div className="p-3 bg-dark-inset rounded border border-white/5">
            <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Avg Board Tenure</div>
            <div className="text-lg font-semibold text-gray-200">
              {key_metrics.avg_board_tenure_years ? `${key_metrics.avg_board_tenure_years.toFixed(1)} years` : 'N/A'}
            </div>
          </div>
          <div className="p-3 bg-dark-inset rounded border border-white/5 lg:col-span-2">
            <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Institutional Ownership</div>
            <div className="text-lg font-semibold text-gray-200">
              {key_metrics.institutional_ownership_pct ? `${key_metrics.institutional_ownership_pct}%` : 'N/A'}
            </div>
          </div>
        </div>
      </div>

      {/* Executive Summary */}
      {executive_summary && (
        <div className="glass-card-elevated rounded-xl p-5">
          <button
            onClick={() => setShowFullSummary(!showFullSummary)}
            className="flex items-center justify-between w-full text-left group"
          >
            <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Executive Summary</h4>
            <ChevronDownIcon
              className={`w-4 h-4 text-gray-500 transition-transform duration-200 ${showFullSummary ? 'rotate-180' : ''}`}
            />
          </button>
          <AnimatePresence>
            {showFullSummary && (
              <Motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.2 }}
                className="overflow-hidden"
              >
                <p className="text-sm text-gray-300 leading-relaxed mt-3 pt-3 border-t border-white/5">
                  {executive_summary}
                </p>
              </Motion.div>
            )}
          </AnimatePresence>
          {!showFullSummary && (
            <p className="text-sm text-gray-400 leading-relaxed mt-2 line-clamp-2">
              {executive_summary}
            </p>
          )}
        </div>
      )}
    </Motion.div>
  );
};

export default LeadershipPanel;
