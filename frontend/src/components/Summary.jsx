/**
 * Summary - Structured executive overview with sectioned analysis,
 * verdict banner, at-a-glance metrics, and price targets.
 */

import React, { useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { exportAnalysisPDF } from '../utils/api';
import {
  DocumentIcon,
  ShieldExclamationIcon,
  LightbulbIcon,
  ArrowUpIcon,
  ArrowDownIcon,
  BuildingIcon,
  ChartBarIcon,
  BrainIcon,
  ChartLineIcon,
  GlobeIcon,
  TrendingUpIcon,
  SparklesIcon,
  ChevronDownIcon,
  TargetIcon,
  OptionsIcon,
} from './Icons';

/* ─── Section metadata ──────────────────────────────────────────── */

const SECTION_META = [
  { id: 1, label: 'Fundamentals & Company Health', icon: BuildingIcon, color: 'accent-blue' },
  { id: 2, label: 'Equity Research Thesis', icon: DocumentIcon, color: 'accent-purple' },
  { id: 3, label: 'Market Conditions', icon: ChartBarIcon, color: 'accent-cyan' },
  { id: 4, label: 'Sentiment & News', icon: BrainIcon, color: 'accent-green' },
  { id: 5, label: 'Technical Signals', icon: ChartLineIcon, color: 'accent-amber' },
  { id: 6, label: 'Options Flow', icon: OptionsIcon, color: 'accent-purple' },
  { id: 7, label: 'Macro Environment', icon: GlobeIcon, color: 'accent-cyan' },
  { id: 8, label: 'Earnings Trends', icon: TrendingUpIcon, color: 'accent-blue' },
  { id: 9, label: 'Risk Factors', icon: ShieldExclamationIcon, color: 'accent-red' },
  { id: 10, label: 'Risk/Reward Assessment', icon: ChartBarIcon, color: 'accent-amber' },
  { id: 11, label: 'Final Recommendation', icon: SparklesIcon, color: 'accent-green' },
];

/* Color map for Tailwind dynamic classes */
const COLOR_CLASSES = {
  'accent-blue':   { border: 'border-l-accent-blue',   bg: 'bg-accent-blue/15',   text: 'text-accent-blue' },
  'accent-purple': { border: 'border-l-accent-purple', bg: 'bg-accent-purple/15', text: 'text-accent-purple' },
  'accent-cyan':   { border: 'border-l-accent-cyan',   bg: 'bg-accent-cyan/15',   text: 'text-accent-cyan' },
  'accent-green':  { border: 'border-l-accent-green',  bg: 'bg-accent-green/15',  text: 'text-accent-green' },
  'accent-amber':  { border: 'border-l-accent-amber',  bg: 'bg-accent-amber/15',  text: 'text-accent-amber' },
  'accent-red':    { border: 'border-l-accent-red',    bg: 'bg-accent-red/15',    text: 'text-accent-red' },
};

/* ─── Helpers ───────────────────────────────────────────────────── */

const getAnalysisPayload = (analysis) => {
  if (!analysis) return {};
  return analysis.analysis || analysis.analysis_payload || analysis;
};

const getRecommendationColor = (recommendation) => {
  if (recommendation === 'BUY') return { text: 'text-success-400', bg: 'bg-success', bgLight: 'bg-success/15', border: 'border-success/30', glow: '0 0 20px rgba(23, 201, 100, 0.12)' };
  if (recommendation === 'SELL') return { text: 'text-danger-400', bg: 'bg-danger', bgLight: 'bg-danger/15', border: 'border-danger/30', glow: '0 0 20px rgba(243, 18, 96, 0.12)' };
  return { text: 'text-warning-400', bg: 'bg-warning', bgLight: 'bg-warning/15', border: 'border-warning/30', glow: '0 0 20px rgba(245, 165, 36, 0.12)' };
};

/**
 * Parse LLM chain-of-thought reasoning into sections.
 * Expects numbered format: "1. Text 2. Text ..." following the 10-step template.
 */
const parseReasoning = (text) => {
  if (!text) return [];

  const sections = text.split(/(?=\d+\.\s)/).filter(s => s.trim());
  return sections.map((section) => {
    const match = section.match(/^(\d+)\.\s*(.*)/s);
    if (!match) return null;

    const num = parseInt(match[1], 10);
    const content = match[2].trim();

    // Extract first sentence as headline
    const colonIdx = content.indexOf(':');
    let headline, detail;

    if (colonIdx > 0 && colonIdx < 80) {
      headline = content.substring(0, colonIdx).trim();
      detail = content.substring(colonIdx + 1).trim();
    } else {
      const periodIdx = content.indexOf('. ');
      if (periodIdx > 0 && periodIdx < 150) {
        headline = content.substring(0, periodIdx + 1).trim();
        detail = content.substring(periodIdx + 2).trim();
      } else {
        headline = content.substring(0, 120);
        detail = content.length > 120 ? content.substring(120).trim() : '';
      }
    }

    const meta = SECTION_META.find(m => m.id === num) || {
      id: num, label: `Step ${num}`, icon: DocumentIcon, color: 'accent-blue'
    };

    return { num, headline, detail, meta };
  }).filter(Boolean);
};

/* ─── Sub-components ────────────────────────────────────────────── */

/**
 * AnalysisSection — a single expandable analysis card.
 */
const AnalysisSection = ({ section, defaultExpanded = false }) => {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const { meta, headline, detail } = section;
  const Icon = meta.icon;
  const colors = COLOR_CLASSES[meta.color] || COLOR_CLASSES['accent-blue'];

  return (
    <div
      className={`p-4 bg-dark-inset rounded-lg border-l-2 ${colors.border} transition-all duration-200 hover:bg-dark-card-hover cursor-pointer`}
      onClick={() => setExpanded(!expanded)}
    >
      <div className="flex items-start space-x-3">
        <div className={`flex-shrink-0 w-7 h-7 rounded-lg ${colors.bg} flex items-center justify-center mt-0.5`}>
          <Icon className={`w-4 h-4 ${colors.text}`} />
        </div>
        <div className="flex-1 min-w-0">
          <div className={`text-xs font-semibold uppercase tracking-wider mb-1 ${colors.text} opacity-70`}>
            {meta.label}
          </div>
          <div className="text-sm font-medium text-gray-200 leading-snug">{headline}</div>
        </div>
        {detail && (
          <ChevronDownIcon
            className={`w-4 h-4 text-gray-500 flex-shrink-0 mt-1 transition-transform duration-200 ${expanded ? 'rotate-180' : ''}`}
          />
        )}
      </div>
      <AnimatePresence>
        {expanded && detail && (
          <motion.div
            key="detail"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: 'easeInOut' }}
            className="overflow-hidden"
          >
            <div className="mt-2.5 ml-10 text-sm text-gray-300 leading-relaxed pb-1">
              {detail}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

/**
 * VerdictBanner — top-level recommendation summary.
 */
export const VerdictBanner = ({ analysis }) => {
  const payload = getAnalysisPayload(analysis);
  const { recommendation, score, confidence, reasoning } = payload;
  const colors = getRecommendationColor(recommendation);

  // Extract first sentence of reasoning as summary
  const firstSentenceEnd = reasoning?.indexOf('. ');
  const summary = firstSentenceEnd > 0 ? reasoning.substring(0, firstSentenceEnd + 1) : (reasoning?.substring(0, 120) || '');

  return (
    <div
      className={`glass-card-elevated rounded-xl p-5 border ${colors.border} animate-fade-in`}
      style={{ boxShadow: colors.glow }}
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center space-x-3">
          <div className={`w-10 h-10 rounded-xl ${colors.bgLight} flex items-center justify-center`}>
            <span className={`text-lg font-bold ${colors.text}`}>
              {recommendation === 'BUY' ? '↑' : recommendation === 'SELL' ? '↓' : '→'}
            </span>
          </div>
          <div>
            <div className={`text-xl font-bold tracking-tight ${colors.text}`}>{recommendation}</div>
            <div className="text-[11px] text-gray-500 uppercase tracking-wider">Recommendation</div>
          </div>
        </div>
        <div className="text-right">
          <div className={`text-2xl font-bold tabular-nums ${colors.text}`}>
            {score > 0 ? '+' : ''}{score}
          </div>
          <div className="text-[11px] text-gray-500 uppercase tracking-wider">Score</div>
        </div>
      </div>
      <p className="text-sm text-gray-300 leading-relaxed">{summary}</p>
      {confidence != null && (
        <div className="mt-3">
          <div className="flex justify-between items-center mb-1">
            <span className="text-[10px] text-gray-500 uppercase tracking-wider">Confidence</span>
            <span className="text-xs font-semibold tabular-nums">{(confidence * 100).toFixed(0)}%</span>
          </div>
          <div className="h-1 bg-dark-card-hover rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full ${colors.bg} transition-all duration-500`}
              style={{ width: `${confidence * 100}%`, opacity: 0.8 }}
            />
          </div>
        </div>
      )}
    </div>
  );
};

/**
 * AtAGlance — horizontal strip of key metrics.
 */
export const AtAGlance = ({ analysis }) => {
  const payload = getAnalysisPayload(analysis);
  const { score, confidence, position_size, time_horizon } = payload;

  const pills = [
    { label: 'Score', value: score != null ? (score > 0 ? `+${score}` : `${score}`) : 'N/A', color: score > 0 ? 'text-success-400' : score < 0 ? 'text-danger-400' : 'text-warning-400' },
    { label: 'Confidence', value: confidence != null ? `${(confidence * 100).toFixed(0)}%` : 'N/A', color: 'text-primary-400' },
    { label: 'Position', value: position_size || 'N/A', color: position_size === 'LARGE' ? 'text-success-400' : position_size === 'SMALL' ? 'text-gray-400' : 'text-primary-400' },
    { label: 'Horizon', value: time_horizon?.replace(/_/g, ' ') || 'N/A', color: 'text-accent-purple' },
  ];

  return (
    <div className="grid grid-cols-4 gap-3 animate-fade-in" style={{ animationDelay: '0.05s' }}>
      {pills.map(({ label, value, color }) => (
        <div key={label} className="p-3 bg-dark-inset rounded-lg text-center">
          <div className="text-[11px] text-gray-500 uppercase tracking-wider mb-1">{label}</div>
          <div className={`text-sm font-bold tabular-nums ${color}`}>{value}</div>
        </div>
      ))}
    </div>
  );
};

/**
 * DecisionCardPanel — explicit, machine-readable trade plan.
 */
export const DecisionCardPanel = ({ analysis }) => {
  const payload = getAnalysisPayload(analysis);
  const card = payload.decision_card;
  if (!card) return null;

  const formatPrice = (value) => {
    const numeric = Number(value);
    return Number.isFinite(numeric) ? `$${numeric.toFixed(2)}` : 'N/A';
  };

  const low = Number(card.entry_zone?.low);
  const high = Number(card.entry_zone?.high);
  const entryZone = Number.isFinite(low) && Number.isFinite(high)
    ? `${formatPrice(low)} - ${formatPrice(high)}`
    : 'N/A';

  const targets = Array.isArray(card.targets) && card.targets.length > 0
    ? card.targets
      .map((t) => Number(t))
      .filter((t) => Number.isFinite(t))
      .map((t) => formatPrice(t))
      .join(', ')
    : 'N/A';

  const confidence = card.confidence != null ? `${Math.round(card.confidence * 100)}%` : 'N/A';
  const horizon = card.time_horizon ? String(card.time_horizon).replace(/_/g, ' ') : 'N/A';
  const action = card.action ? String(card.action).toUpperCase() : 'N/A';
  const stopLoss = card.stop_loss != null ? formatPrice(card.stop_loss) : 'N/A';

  return (
    <div className="glass-card-elevated rounded-xl p-5 animate-fade-in">
      <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider mb-3 flex items-center space-x-2">
        <TargetIcon className="w-4 h-4 text-accent-green" />
        <span>Decision Card</span>
      </h3>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-3">
        <div className="p-3 bg-dark-inset rounded-lg">
          <div className="text-[11px] text-gray-500 uppercase tracking-wider mb-1">Action</div>
          <div className="text-sm font-bold text-accent-green">{action}</div>
        </div>
        <div className="p-3 bg-dark-inset rounded-lg">
          <div className="text-[11px] text-gray-500 uppercase tracking-wider mb-1">Entry Zone</div>
          <div className="text-sm font-mono tabular-nums text-gray-200">{entryZone}</div>
        </div>
        <div className="p-3 bg-dark-inset rounded-lg">
          <div className="text-[11px] text-gray-500 uppercase tracking-wider mb-1">Stop Loss</div>
          <div className="text-sm font-mono tabular-nums text-danger-400">{stopLoss}</div>
        </div>
        <div className="p-3 bg-dark-inset rounded-lg">
          <div className="text-[11px] text-gray-500 uppercase tracking-wider mb-1">Targets</div>
          <div className="text-sm font-mono tabular-nums text-success-400">{targets}</div>
        </div>
        <div className="p-3 bg-dark-inset rounded-lg">
          <div className="text-[11px] text-gray-500 uppercase tracking-wider mb-1">Confidence</div>
          <div className="text-sm font-semibold text-primary-400">{confidence}</div>
        </div>
        <div className="p-3 bg-dark-inset rounded-lg">
          <div className="text-[11px] text-gray-500 uppercase tracking-wider mb-1">Horizon</div>
          <div className="text-sm font-semibold text-accent-purple">{horizon}</div>
        </div>
      </div>

      {card.position_sizing_hint && (
        <div className="text-xs text-gray-400 mb-2">
          <span className="text-gray-500 uppercase tracking-wider mr-2">Sizing</span>
          {card.position_sizing_hint}
        </div>
      )}

      {Array.isArray(card.invalidation_conditions) && card.invalidation_conditions.length > 0 && (
        <div className="pt-2 border-t border-white/5">
          <div className="text-[11px] text-gray-500 uppercase tracking-wider mb-1.5">Invalidation Conditions</div>
          <ul className="space-y-1.5">
            {card.invalidation_conditions.map((item, idx) => (
              <li key={idx} className="text-sm text-gray-300 flex items-start">
                <span className="text-[10px] text-danger-400/70 font-mono mr-2 mt-0.5">{String(idx + 1).padStart(2, '0')}</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};

/**
 * ChangeSummaryPanel — highlights what materially changed vs last run.
 */
export const ChangeSummaryPanel = ({ analysis, showFallbackWhenEmpty = false }) => {
  const payload = getAnalysisPayload(analysis);
  const changes = payload.changes_since_last_run || payload.change_summary || analysis?.change_summary;
  if (!changes && !showFallbackWhenEmpty) return null;

  const materialChanges = changes?.material_changes || [];
  const hasPrevious = changes?.has_previous !== false;
  const summary = changes?.summary
    || (hasPrevious ? 'No major changes detected.' : 'No prior run to compare yet.');

  return (
    <div className="glass-card-elevated rounded-xl p-5 animate-fade-in">
      <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider mb-2">
        What Changed Since Last Run
      </h3>

      <p className="text-sm text-gray-300 mb-3">
        {summary}
      </p>

      {materialChanges.length > 0 && (
        <div className="space-y-2">
          {materialChanges.map((item, idx) => (
            <div key={`${item.type}-${idx}`} className="p-2.5 bg-dark-inset rounded-lg border border-white/5">
              <div className="text-xs text-gray-200">{item.label}</div>
              <div className="text-[11px] text-gray-500 mt-0.5">
                Impact: <span className="uppercase">{item.impact || 'medium'}</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {materialChanges.length === 0 && (
        <div className="text-xs text-gray-500">No material deltas available for this run.</div>
      )}
    </div>
  );
};

/**
 * PriceTargetsRangeBar — visual bar showing stop_loss → entry → target range.
 */
const PriceTargetsRangeBar = ({ price_targets }) => {
  if (!price_targets?.entry || !price_targets?.target || !price_targets?.stop_loss) return null;

  const { entry, target, stop_loss } = price_targets;
  const totalRange = target - stop_loss;
  if (totalRange <= 0) return null;

  const entryPct = ((entry - stop_loss) / totalRange) * 100;

  return (
    <div className="mb-4">
      {/* Range bar */}
      <div className="relative h-2 rounded-full overflow-hidden bg-dark-card-hover">
        {/* Downside (red) */}
        <div
          className="absolute top-0 left-0 h-full bg-danger/40 rounded-l-full"
          style={{ width: `${entryPct}%` }}
        />
        {/* Upside (green) */}
        <div
          className="absolute top-0 h-full bg-success/40 rounded-r-full"
          style={{ left: `${entryPct}%`, width: `${100 - entryPct}%` }}
        />
        {/* Entry marker */}
        <div
          className="absolute top-1/2 -translate-y-1/2 w-3 h-3 rounded-full bg-white border-2 border-primary shadow-lg"
          style={{ left: `${entryPct}%`, transform: `translate(-50%, -50%)` }}
        />
      </div>
      {/* Labels */}
      <div className="flex justify-between mt-1.5">
        <span className="text-[10px] text-danger-400 font-mono tabular-nums">${stop_loss.toFixed(2)}</span>
        <span className="text-[10px] text-gray-300 font-medium font-mono tabular-nums">${entry.toFixed(2)}</span>
        <span className="text-[10px] text-success-400 font-mono tabular-nums">${target.toFixed(2)}</span>
      </div>
    </div>
  );
};

/* ─── Skeleton ──────────────────────────────────────────────────── */

const SummarySkeleton = () => (
  <div className="space-y-4 animate-fade-in">
    {/* Verdict banner skeleton */}
    <div className="glass-card-elevated rounded-xl p-5">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center space-x-3">
          <div className="skeleton w-10 h-10 rounded-xl" />
          <div>
            <div className="skeleton h-5 w-16 mb-1" />
            <div className="skeleton h-3 w-28" />
          </div>
        </div>
        <div className="text-right">
          <div className="skeleton h-7 w-12 mb-1" />
          <div className="skeleton h-3 w-10" />
        </div>
      </div>
      <div className="skeleton h-4 w-full mb-2" />
      <div className="skeleton h-4 w-3/4" />
    </div>
    {/* At-a-glance skeleton */}
    <div className="grid grid-cols-4 gap-2">
      {[...Array(4)].map((_, i) => (
        <div key={i} className="p-2.5 bg-dark-inset rounded-lg">
          <div className="skeleton h-3 w-12 mx-auto mb-1" />
          <div className="skeleton h-4 w-10 mx-auto" />
        </div>
      ))}
    </div>
    {/* Section skeletons */}
    <div className="glass-card-elevated rounded-xl p-5 space-y-2">
      {[...Array(5)].map((_, i) => (
        <div key={i} className="p-3.5 bg-dark-inset rounded-lg">
          <div className="flex items-center space-x-3">
            <div className="skeleton w-7 h-7 rounded-lg" />
            <div className="flex-1">
              <div className="skeleton h-3 w-32 mb-1.5" />
              <div className="skeleton h-4 w-full" />
            </div>
          </div>
        </div>
      ))}
    </div>
  </div>
);

/* ─── Exported Sub-components ──────────────────────────────────── */

/**
 * OverviewMetrics — VerdictBanner + AtAGlance together for the Overview tab.
 */
export const OverviewMetrics = ({ analysis }) => {
  if (!analysis) return null;
  return (
    <div className="space-y-4">
      <VerdictBanner analysis={analysis} />
      <AtAGlance analysis={analysis} />
      <DecisionCardPanel analysis={analysis} />
    </div>
  );
};

/**
 * ResearchContent — chain-of-thought sections, price targets, risks/opps, and PDF export.
 * Designed for the Research tab.
 */
export const ResearchContent = ({ analysis }) => {
  const [pdfLoading, setPdfLoading] = useState(false);

  const handleExportPDF = useCallback(async () => {
    if (!analysis?.ticker) return;
    setPdfLoading(true);
    try {
      await exportAnalysisPDF(analysis.ticker, analysis.analysis_id);
    } catch (err) {
      console.error('PDF export failed:', err);
    } finally {
      setPdfLoading(false);
    }
  }, [analysis?.ticker, analysis?.analysis_id]);

  if (!analysis) return null;

  const payload = getAnalysisPayload(analysis);
  const { reasoning, risks, opportunities, price_targets } = payload;
  const sections = parseReasoning(reasoning);

  // Calculate upside/downside from entry
  const getPercent = (target, entry) => {
    if (!target || !entry || entry === 0) return null;
    return (((target - entry) / entry) * 100).toFixed(1);
  };

  const upside = getPercent(price_targets?.target, price_targets?.entry);
  const downside = getPercent(price_targets?.stop_loss, price_targets?.entry);

  return (
    <div className="space-y-4">
      {/* Export Bar */}
      <div className="flex justify-end">
        <button
          onClick={handleExportPDF}
          disabled={pdfLoading}
          className="flex items-center space-x-1.5 px-3 py-1.5 text-xs font-medium rounded-lg
            bg-dark-card hover:bg-dark-card-hover border border-white/5 hover:border-white/10
            text-gray-400 hover:text-gray-200 transition-all duration-200 disabled:opacity-50"
        >
          <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="7 10 12 15 17 10" />
            <line x1="12" y1="15" x2="12" y2="3" />
          </svg>
          <span>{pdfLoading ? 'Exporting...' : 'Export PDF'}</span>
        </button>
      </div>

      {/* Analysis Sections */}
      {sections.length > 0 && (
        <div className="glass-card-elevated rounded-xl p-5 animate-fade-in" style={{ animationDelay: '0.1s' }}>
          <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider mb-3 flex items-center space-x-2">
            <DocumentIcon className="w-4 h-4 text-accent-blue" />
            <span>Chain-of-Thought Analysis</span>
          </h3>
          <div className="space-y-3">
            {sections.map((section) => (
              <AnalysisSection
                key={section.num}
                section={section}
                defaultExpanded={section.num === 1 || section.num === 11}
              />
            ))}
          </div>
        </div>
      )}

      {/* Fallback: if reasoning doesn't parse into sections, show as formatted text */}
      {sections.length === 0 && reasoning && (
        <div className="glass-card-elevated rounded-xl p-5 animate-fade-in" style={{ animationDelay: '0.1s' }}>
          <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider mb-3 flex items-center space-x-2">
            <DocumentIcon className="w-4 h-4 text-accent-blue" />
            <span>Executive Summary</span>
          </h3>
          <p className="text-sm leading-relaxed text-gray-300">{reasoning}</p>
        </div>
      )}

      {/* Price Targets */}
      {price_targets && (
        <div className="glass-card-elevated rounded-xl p-5 animate-fade-in" style={{ animationDelay: '0.15s' }}>
          <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider mb-3 flex items-center space-x-2">
            <TargetIcon className="w-4 h-4 text-primary-400" />
            <span>Price Targets</span>
          </h3>

          {/* Range bar visualization */}
          <PriceTargetsRangeBar price_targets={price_targets} />

          {/* Cards */}
          <div className="grid grid-cols-3 gap-4">
            {price_targets.entry != null && (
              <div className="p-4 bg-dark-inset rounded-lg border-t-2 border-t-accent-blue">
                <div className="text-[11px] text-gray-500 uppercase tracking-wider mb-1">Entry</div>
                <div className="text-xl font-bold font-mono text-accent-blue tabular-nums">
                  ${price_targets.entry.toFixed(2)}
                </div>
              </div>
            )}
            {price_targets.target != null && (
              <div className="p-4 bg-dark-inset rounded-lg border-t-2 border-t-success">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[11px] text-gray-500 uppercase tracking-wider">Target</span>
                  {upside && (
                    <span className="text-[10px] text-success-400 font-medium flex items-center">
                      <ArrowUpIcon className="w-2.5 h-2.5 mr-0.5" />+{upside}%
                    </span>
                  )}
                </div>
                <div className="text-xl font-bold font-mono text-success-400 tabular-nums">
                  ${price_targets.target.toFixed(2)}
                </div>
              </div>
            )}
            {price_targets.stop_loss != null && (
              <div className="p-4 bg-dark-inset rounded-lg border-t-2 border-t-danger">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[11px] text-gray-500 uppercase tracking-wider">Stop Loss</span>
                  {downside && (
                    <span className="text-[10px] text-danger-400 font-medium flex items-center">
                      <ArrowDownIcon className="w-2.5 h-2.5 mr-0.5" />{downside}%
                    </span>
                  )}
                </div>
                <div className="text-xl font-bold font-mono text-danger-400 tabular-nums">
                  ${price_targets.stop_loss.toFixed(2)}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Risks & Opportunities */}
      <div className="grid grid-cols-2 gap-4">
        {/* Risks */}
        {risks && risks.length > 0 && (
          <div
            className="glass-card-elevated rounded-xl p-5 border-l-2 border-l-danger bg-gradient-to-r from-danger/[0.03] to-transparent animate-fade-in"
            style={{ animationDelay: '0.2s' }}
          >
            <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider mb-3 flex items-center space-x-2">
              <ShieldExclamationIcon className="w-4 h-4 text-danger-400" />
              <span>Risks</span>
            </h3>
            <ul className="space-y-2.5">
              {risks.map((risk, index) => (
                <li key={index} className="text-sm text-gray-300 flex items-start">
                  <span className="text-[10px] text-danger-400/60 font-mono mr-2 mt-0.5 flex-shrink-0">{String(index + 1).padStart(2, '0')}</span>
                  <span>{risk}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Opportunities */}
        {opportunities && opportunities.length > 0 && (
          <div
            className="glass-card-elevated rounded-xl p-5 border-l-2 border-l-success bg-gradient-to-r from-success/[0.03] to-transparent animate-fade-in"
            style={{ animationDelay: '0.25s' }}
          >
            <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider mb-3 flex items-center space-x-2">
              <LightbulbIcon className="w-4 h-4 text-success-400" />
              <span>Opportunities</span>
            </h3>
            <ul className="space-y-2.5">
              {opportunities.map((opportunity, index) => (
                <li key={index} className="text-sm text-gray-300 flex items-start">
                  <span className="text-[10px] text-success-400/60 font-mono mr-2 mt-0.5 flex-shrink-0">{String(index + 1).padStart(2, '0')}</span>
                  <span>{opportunity}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
};

/* ─── Main Component ────────────────────────────────────────────── */

const Summary = ({ analysis }) => {
  if (!analysis) {
    return <SummarySkeleton />;
  }

  return (
    <motion.div
      className="space-y-4"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <OverviewMetrics analysis={analysis} />
      <ResearchContent analysis={analysis} />
    </motion.div>
  );
};

export default Summary;
