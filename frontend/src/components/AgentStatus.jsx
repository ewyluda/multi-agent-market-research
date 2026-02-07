/**
 * AgentStatus - Displays status of all 6 agents in the analysis pipeline
 */

import React from 'react';
import { useAnalysisContext } from '../context/AnalysisContext';
import { ChartBarIcon, BuildingIcon, NewspaperIcon, ChartLineIcon, BrainIcon, SparklesIcon, CheckCircleIcon, XCircleIcon, ClockIcon } from './Icons';

const AgentStatus = () => {
  const { analysis, loading, stage } = useAnalysisContext();

  const agents = [
    { id: 'market', label: 'Market Data', icon: ChartBarIcon, description: 'Price & volume trends' },
    { id: 'fundamentals', label: 'Fundamentals', icon: BuildingIcon, description: 'Company health metrics' },
    { id: 'news', label: 'News', icon: NewspaperIcon, description: 'Recent articles & headlines' },
    { id: 'technical', label: 'Technical', icon: ChartLineIcon, description: 'RSI, MACD, Bollinger' },
    { id: 'sentiment', label: 'Sentiment', icon: BrainIcon, description: 'Market mood analysis' },
    { id: 'solution', label: 'Synthesis', icon: SparklesIcon, description: 'AI final analysis' },
  ];

  const stageToAgent = {
    running_market: 'market',
    running_fundamentals: 'fundamentals',
    running_news: 'news',
    running_technical: 'technical',
    analyzing_sentiment: 'sentiment',
    synthesizing: 'solution',
  };

  const agentOrder = ['market', 'fundamentals', 'news', 'technical', 'sentiment', 'solution'];

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
        return <CheckCircleIcon className="w-4 h-4 text-emerald-400" />;
      case 'error':
        return <XCircleIcon className="w-4 h-4 text-red-400" />;
      case 'running':
        return (
          <div className="w-3 h-3 rounded-full bg-blue-500 ring-4 ring-blue-500/20 animate-pulse" />
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

  return (
    <div className="glass-card-elevated rounded-xl p-4">
      <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider mb-4">Agent Pipeline</h3>

      <div className="space-y-1.5">
        {agents.map((agent, index) => {
          const status = getAgentStatus(agent.id);
          const Icon = agent.icon;
          const duration = getDuration(agent.id);
          const isLast = index === agents.length - 1;

          return (
            <div key={agent.id}>
              <div
                className={`flex items-center justify-between p-2.5 rounded-lg transition-all ${
                  status === 'running'
                    ? 'bg-blue-500/10 border border-blue-500/20'
                    : 'hover:bg-white/[0.03]'
                }`}
              >
                <div className="flex items-center space-x-3 min-w-0">
                  <div className={`flex-shrink-0 ${
                    status === 'success' ? 'text-gray-300' :
                    status === 'running' ? 'text-blue-400' :
                    status === 'error' ? 'text-red-400' :
                    'text-gray-500'
                  }`}>
                    <Icon className="w-4 h-4" />
                  </div>
                  <div className="min-w-0">
                    <div className="text-xs font-medium truncate">{agent.label}</div>
                    <div className="text-[10px] text-gray-500 truncate">{agent.description}</div>
                  </div>
                </div>

                <div className="flex items-center space-x-2 flex-shrink-0 ml-2">
                  {duration && (
                    <span className="text-[10px] text-gray-500 tabular-nums">{duration}s</span>
                  )}
                  {getStatusIndicator(status)}
                </div>
              </div>

              {/* Connector line between agents */}
              {!isLast && (
                <div className="flex justify-center py-0.5">
                  <div className={`w-px h-2 ${
                    status === 'success' ? 'bg-emerald-500/30' :
                    status === 'running' ? 'bg-blue-500/30' :
                    'bg-gray-700/50'
                  }`} />
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Completion Summary */}
      {!loading && analysis && (
        <div className="mt-4 pt-3 border-t border-white/5">
          <div className="flex items-center space-x-1.5 text-[10px] text-gray-500">
            <ClockIcon className="w-3 h-3" />
            <span>Completed in {analysis.duration_seconds?.toFixed(1)}s</span>
          </div>
        </div>
      )}

      {/* Loading Footer */}
      {loading && stage && (
        <div className="mt-4 pt-3 border-t border-white/5">
          <div className="flex items-center space-x-2">
            <div className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" />
            <span className="text-[10px] text-gray-400">Processing...</span>
          </div>
        </div>
      )}
    </div>
  );
};

export default AgentStatus;
