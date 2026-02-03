/**
 * AgentStatus - Displays status of each agent (Market, Fundamentals, News, Sentiment)
 */

import React from 'react';
import { useAnalysisContext } from '../context/AnalysisContext';

const AgentStatus = () => {
  const { analysis, loading, stage } = useAnalysisContext();

  const agents = [
    { id: 'market', label: 'Market', icon: '📊' },
    { id: 'fundamentals', label: 'Fundamentals', icon: '💼' },
    { id: 'news', label: 'News', icon: '📰' },
    { id: 'sentiment', label: 'Sentiment', icon: '🧠' },
  ];

  const getAgentStatus = (agentId) => {
    if (!loading && !analysis) {
      return 'idle';
    }

    if (loading) {
      // Check if this agent is currently running based on stage
      if (stage === `running_${agentId}`) {
        return 'running';
      }

      // Check if agent has completed (if we have results)
      if (analysis?.agent_results?.[agentId]) {
        return analysis.agent_results[agentId].success ? 'success' : 'error';
      }

      // Determine if agent should be pending or running
      const agentOrder = ['market', 'fundamentals', 'news', 'technical'];
      const currentIndex = agentOrder.indexOf(stage.replace('running_', ''));
      const agentIndex = agentOrder.indexOf(agentId);

      if (agentIndex < currentIndex) {
        return 'success'; // Already completed
      } else if (agentIndex === currentIndex) {
        return 'running';
      } else {
        return 'pending';
      }
    }

    // If not loading and we have analysis, check results
    if (analysis?.agent_results?.[agentId]) {
      return analysis.agent_results[agentId].success ? 'success' : 'error';
    }

    return 'idle';
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'success':
        return 'bg-green-500';
      case 'error':
        return 'bg-red-500';
      case 'running':
        return 'bg-blue-500 animate-pulse';
      case 'pending':
        return 'bg-gray-600';
      default:
        return 'bg-gray-700';
    }
  };

  return (
    <div className="bg-dark-card border border-dark-border rounded-lg p-4">
      <h3 className="text-lg font-semibold mb-4">Agents</h3>

      <div className="space-y-3">
        {agents.map((agent) => {
          const status = getAgentStatus(agent.id);

          return (
            <div
              key={agent.id}
              className="flex items-center justify-between p-3 bg-dark-bg rounded-md hover:bg-gray-800 transition-colors cursor-pointer"
            >
              <div className="flex items-center space-x-3">
                <span className="text-2xl">{agent.icon}</span>
                <span className="text-sm font-medium">{agent.label}</span>
              </div>

              <div className="flex items-center space-x-2">
                <div
                  className={`w-2 h-2 rounded-full ${getStatusColor(status)}`}
                  title={status}
                />
              </div>
            </div>
          );
        })}
      </div>

      {loading && (
        <div className="mt-4 pt-4 border-t border-dark-border">
          <div className="text-xs text-gray-400">
            {stage === 'gathering_data' && 'Gathering data...'}
            {stage === 'running_market' && 'Analyzing market...'}
            {stage === 'running_fundamentals' && 'Analyzing fundamentals...'}
            {stage === 'running_news' && 'Fetching news...'}
            {stage === 'analyzing_sentiment' && 'Analyzing sentiment...'}
            {stage === 'synthesizing' && 'Synthesizing results...'}
          </div>
        </div>
      )}
    </div>
  );
};

export default AgentStatus;
