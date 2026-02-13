/**
 * AgentStatus - Displays status of all 7 agents in the analysis pipeline
 */

import React from 'react';
import { motion } from 'framer-motion';
import { useAnalysisContext } from '../context/AnalysisContext';
import { ChartBarIcon, BuildingIcon, NewspaperIcon, ChartLineIcon, GlobeIcon, BrainIcon, SparklesIcon, OptionsIcon, CheckCircleIcon, XCircleIcon, ClockIcon } from './Icons';

const containerVariants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.04 } }
};

const rowVariants = {
  hidden: { opacity: 0, x: -8 },
  visible: { opacity: 1, x: 0, transition: { duration: 0.3 } }
};

const AgentStatus = () => {
  const { analysis, loading, stage } = useAnalysisContext();

  const agents = [
    { id: 'market', label: 'Market Data', icon: ChartBarIcon },
    { id: 'fundamentals', label: 'Fundamentals', icon: BuildingIcon },
    { id: 'news', label: 'News', icon: NewspaperIcon },
    { id: 'technical', label: 'Technical', icon: ChartLineIcon },
    { id: 'options', label: 'Options', icon: OptionsIcon },
    { id: 'macro', label: 'Macro', icon: GlobeIcon },
    { id: 'sentiment', label: 'Sentiment', icon: BrainIcon },
    { id: 'solution', label: 'Synthesis', icon: SparklesIcon },
  ];

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

  const agentOrder = ['market', 'fundamentals', 'news', 'technical', 'options', 'macro', 'sentiment', 'solution'];

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

  const getStatusIndicator = (status) => {
    switch (status) {
      case 'success':
        return <CheckCircleIcon className="w-4 h-4 text-success-400" />;
      case 'error':
        return <XCircleIcon className="w-4 h-4 text-danger-400" />;
      case 'running':
        return (
          <div className="w-3 h-3 rounded-full bg-primary ring-4 ring-primary/20 animate-pulse" />
        );
      case 'pending':
        return <div className="w-3 h-3 rounded-full bg-gray-600" />;
      default:
        return <div className="w-3 h-3 rounded-full bg-gray-700 ring-1 ring-gray-600" />;
    }
  };

  const getDuration = (agentId) => {
    if (agentId === 'solution') return null;
    const result = analysis?.agent_results?.[agentId];
    if (!result?.duration_seconds) return null;
    return result.duration_seconds.toFixed(1);
  };

  const getDurationColorClass = (durationStr) => {
    if (!durationStr) return '';
    const seconds = parseFloat(durationStr);
    if (seconds < 2) return 'text-success-400';
    if (seconds <= 5) return 'text-warning-400';
    return 'text-danger-400';
  };

  const completedCount = agents.filter(a => getAgentStatus(a.id) === 'success').length;
  const totalCount = agents.length;
  const percentage = totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0;

  return (
    <div className="glass-card-elevated rounded-xl p-4">
      <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider mb-4">Agent Pipeline</h3>

      <motion.div
        className="space-y-1.5"
        variants={containerVariants}
        initial="hidden"
        animate="visible"
      >
        {agents.map((agent, index) => {
          const status = getAgentStatus(agent.id);
          const Icon = agent.icon;
          const duration = getDuration(agent.id);
          const isLast = index === agents.length - 1;

          return (
            <motion.div key={agent.id} variants={rowVariants}>
              <div
                className={`flex items-center justify-between p-2.5 rounded-lg transition-all ${
                  status === 'running'
                    ? 'bg-primary/10 border border-primary/20'
                    : 'hover:bg-white/[0.03]'
                }`}
              >
                <div className="flex items-center space-x-3 min-w-0">
                  <div className={`flex-shrink-0 ${
                    status === 'success' ? 'text-gray-300' :
                    status === 'running' ? 'text-primary-400' :
                    status === 'error' ? 'text-danger-400' :
                    'text-gray-500'
                  }`}>
                    <Icon className="w-4 h-4" />
                  </div>
                  <div className="text-xs font-medium truncate">{agent.label}</div>
                </div>

                <div className="flex items-center space-x-2 flex-shrink-0 ml-2">
                  {duration && (
                    <span className={`text-[10px] font-mono tabular-nums ${getDurationColorClass(duration)}`}>{duration}s</span>
                  )}
                  {getStatusIndicator(status)}
                </div>
              </div>

              {/* Connector line between agents */}
              {!isLast && (
                <div className="flex justify-center py-0.5">
                  <div className={`w-px h-2 ${
                    status === 'success' ? 'bg-success/30' :
                    status === 'running' ? 'bg-primary/30' :
                    'bg-gray-700/50'
                  }`} />
                </div>
              )}
            </motion.div>
          );
        })}
      </motion.div>

      {/* Completion Summary */}
      {!loading && analysis && (
        <div className="mt-4 pt-3 border-t border-white/5">
          <div className="flex items-center space-x-1.5 text-[10px] text-gray-500">
            <ClockIcon className="w-3 h-3" />
            <span>Completed in <span className="font-mono">{analysis.duration_seconds?.toFixed(1)}s</span></span>
          </div>
        </div>
      )}

      {/* Loading Footer */}
      {loading && stage && (
        <div className="mt-4 pt-3 border-t border-white/5">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <div className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
              <span className="text-[10px] text-gray-400">Processing...</span>
            </div>
            <span className="text-[10px] font-mono text-gray-500">{percentage}%</span>
          </div>
        </div>
      )}
    </div>
  );
};

export default AgentStatus;
