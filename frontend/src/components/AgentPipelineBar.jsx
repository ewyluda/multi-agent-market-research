/**
 * AgentPipelineBar - Compact horizontal bar showing agent pipeline status
 *
 * Replaces the full-sidebar AgentStatus with a single-row horizontal layout.
 * Each agent is represented by a small icon, 3-letter label, and status indicator.
 * Includes duration tooltips, total completion time, and collapse toggle.
 */

import React, { useState } from 'react';
import { motion as Motion, AnimatePresence } from 'framer-motion';
import { useAnalysisContext } from '../context/AnalysisContext';
import {
  ChartBarIcon,
  BuildingIcon,
  NewspaperIcon,
  ChartLineIcon,
  OptionsIcon,
  GlobeIcon,
  BrainIcon,
  SparklesIcon,
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
} from './Icons';

const stageToAgent = {
  running_market: 'market',
  running_fundamentals: 'fundamentals',
  running_news: 'news',
  running_technical: 'technical',
  running_options: 'options',
  running_macro: 'macro',
  analyzing_sentiment: 'sentiment',
  synthesizing: 'solution',
};

const agentOrder = [
  'market',
  'fundamentals',
  'news',
  'technical',
  'options',
  'macro',
  'sentiment',
  'solution',
];

const agents = [
  { id: 'market', label: 'Mkt', icon: ChartBarIcon },
  { id: 'fundamentals', label: 'Fun', icon: BuildingIcon },
  { id: 'news', label: 'News', icon: NewspaperIcon },
  { id: 'technical', label: 'Tech', icon: ChartLineIcon },
  { id: 'options', label: 'Opts', icon: OptionsIcon },
  { id: 'macro', label: 'Mac', icon: GlobeIcon },
  { id: 'sentiment', label: 'Sent', icon: BrainIcon },
  { id: 'solution', label: 'Syn', icon: SparklesIcon },
];

const containerVariants = {
  hidden: {},
  visible: {
    transition: { staggerChildren: 0.06 },
  },
};

const itemVariants = {
  hidden: { opacity: 0, y: 8, scale: 0.9 },
  visible: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: { duration: 0.3, ease: 'easeOut' },
  },
};

const AgentPipelineBar = () => {
  const { analysis, loading, stage } = useAnalysisContext();
  const [expanded, setExpanded] = useState(true);
  const shouldExpand = loading || expanded;

  const getAgentStatus = (agentId) => {
    if (!loading && !analysis) return 'idle';

    if (loading) {
      const currentAgentId = stageToAgent[stage];
      const currentIndex = agentOrder.indexOf(currentAgentId);
      const agentIndex = agentOrder.indexOf(agentId);

      if (analysis?.agent_results?.[agentId]) {
        return analysis.agent_results[agentId].success ? 'success' : 'error';
      }

      if (agentId === currentAgentId) return 'running';
      if (currentIndex >= 0 && agentIndex < currentIndex) return 'success';
      if (stage === 'saving' || stage === 'complete') return 'success';

      return 'pending';
    }

    if (analysis?.agent_results?.[agentId]) {
      return analysis.agent_results[agentId].success ? 'success' : 'error';
    }
    if (agentId === 'solution' && analysis?.analysis) return 'success';

    return 'idle';
  };

  const getDuration = (agentId) => {
    if (agentId === 'solution') return null;
    const result = analysis?.agent_results?.[agentId];
    if (!result?.duration_seconds) return null;
    return result.duration_seconds.toFixed(1);
  };

  const getStatusIndicator = (status) => {
    switch (status) {
      case 'success':
        return <CheckCircleIcon className="w-3.5 h-3.5 text-success-400" />;
      case 'error':
        return <XCircleIcon className="w-3.5 h-3.5 text-danger-400" />;
      case 'running':
        return (
          <div className="w-2.5 h-2.5 rounded-full bg-primary ring-3 ring-primary/20 animate-pulse" />
        );
      case 'pending':
        return <div className="w-2.5 h-2.5 rounded-full bg-gray-600" />;
      default:
        return (
          <div className="w-2.5 h-2.5 rounded-full bg-gray-700 ring-1 ring-gray-600" />
        );
    }
  };

  const getIconColorClass = (status) => {
    switch (status) {
      case 'success':
        return 'text-gray-300';
      case 'running':
        return 'text-primary-400';
      case 'error':
        return 'text-danger-400';
      default:
        return 'text-gray-500';
    }
  };

  const isComplete = !loading && analysis;

  return (
    <div className="glass-card rounded-xl px-4 py-3">
      {/* Header row with title and toggle */}
      <div className="flex items-center justify-between mb-0">
        <div className="flex items-center gap-2">
          <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
            Pipeline
          </h3>
          {loading && (
            <div className="flex items-center gap-1.5">
              <div className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
              <span className="text-[10px] text-gray-500">Processing</span>
            </div>
          )}
        </div>

        <div className="flex items-center gap-3">
          {/* Total completion time */}
          {isComplete && analysis.duration_seconds && (
            <div className="flex items-center gap-1 text-[10px] text-gray-500">
              <ClockIcon className="w-3 h-3" />
              <span className="font-mono tabular-nums">
                {analysis.duration_seconds.toFixed(1)}s
              </span>
            </div>
          )}

          {/* Collapse toggle - only show after completion */}
        {isComplete && (
          <button
            onClick={() => setExpanded((prev) => !prev)}
            className="text-[10px] text-gray-500 hover:text-gray-300 transition-colors flex items-center gap-0.5"
          >
            Pipeline
            <span
              className={`inline-block transition-transform duration-200 ${
                  shouldExpand ? '' : '-rotate-90'
                }`}
            >
              &#9662;
            </span>
          </button>
          )}
        </div>
      </div>

      {/* Agent items row */}
      <AnimatePresence>
        {shouldExpand && (
          <Motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: 'easeInOut' }}
            className="overflow-hidden"
          >
            <Motion.div
              className="flex items-center justify-between gap-2 pt-3"
              variants={containerVariants}
              initial="hidden"
              animate="visible"
            >
              {agents.map((agent) => {
                const status = getAgentStatus(agent.id);
                const Icon = agent.icon;
                const duration = getDuration(agent.id);

                return (
                  <Motion.div
                    key={agent.id}
                    variants={itemVariants}
                    className="group relative flex flex-col items-center gap-1 flex-1 min-w-0"
                  >
                    {/* Icon + status */}
                    <div
                      className={`relative flex items-center justify-center w-9 h-9 rounded-lg transition-all ${
                        status === 'running'
                          ? 'bg-primary/10 ring-1 ring-primary/20'
                          : 'hover:bg-white/[0.03]'
                      }`}
                    >
                      <Icon
                        className={`w-4 h-4 ${getIconColorClass(status)}`}
                      />

                      {/* Status indicator badge */}
                      <div className="absolute -bottom-0.5 -right-0.5">
                        {getStatusIndicator(status)}
                      </div>
                    </div>

                    {/* Label */}
                    <span
                      className={`text-[10px] font-medium tracking-wide ${
                        status === 'running'
                          ? 'text-primary-400'
                          : status === 'success'
                          ? 'text-gray-400'
                          : status === 'error'
                          ? 'text-danger-400'
                          : 'text-gray-600'
                      }`}
                    >
                      {agent.label}
                    </span>

                    {/* Duration tooltip on hover */}
                    {duration && (
                      <span className="absolute -top-7 left-1/2 -translate-x-1/2 px-1.5 py-0.5 rounded bg-gray-800 text-[9px] font-mono text-gray-300 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap border border-white/10 shadow-lg z-10">
                        {duration}s
                      </span>
                    )}
                  </Motion.div>
                );
              })}
            </Motion.div>
          </Motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default AgentPipelineBar;
