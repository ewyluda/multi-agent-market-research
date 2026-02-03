/**
 * SentimentReport - Displays sentiment breakdown by factors
 */

import React, { useState } from 'react';

const SentimentReport = ({ analysis }) => {
  const [activeTab, setActiveTab] = useState('summary');

  if (!analysis || !analysis.agent_results?.sentiment) {
    return (
      <div className="bg-dark-card border border-dark-border rounded-lg p-6">
        <h3 className="text-lg font-semibold mb-4">Sentiment Report</h3>
        <div className="text-gray-500 text-center py-8">
          No sentiment data available
        </div>
      </div>
    );
  }

  const sentimentData = analysis.agent_results.sentiment.data || {};
  const overallSentiment = sentimentData.overall_sentiment || 0;
  const confidence = sentimentData.confidence || 0;
  const factors = sentimentData.factors || {};

  const getSentimentLabel = (score) => {
    if (score > 0.3) return 'Positive';
    if (score < -0.3) return 'Negative';
    return 'Neutral';
  };

  const getSentimentColor = (score) => {
    if (score > 0.3) return 'text-green-500';
    if (score < -0.3) return 'text-red-500';
    return 'text-yellow-500';
  };

  const getBarColor = (score) => {
    if (score > 0) return 'bg-green-500';
    if (score < 0) return 'bg-red-500';
    return 'bg-gray-500';
  };

  return (
    <div className="bg-dark-card border border-dark-border rounded-lg p-6">
      <h3 className="text-lg font-semibold mb-4">Sentiment Report</h3>

      {/* Tabs */}
      <div className="flex space-x-4 mb-4 border-b border-dark-border">
        <button
          className={`pb-2 px-1 ${
            activeTab === 'summary'
              ? 'border-b-2 border-accent-blue text-white'
              : 'text-gray-400 hover:text-white'
          }`}
          onClick={() => setActiveTab('summary')}
        >
          Summary
        </button>
        <button
          className={`pb-2 px-1 ${
            activeTab === 'factors'
              ? 'border-b-2 border-accent-blue text-white'
              : 'text-gray-400 hover:text-white'
          }`}
          onClick={() => setActiveTab('factors')}
        >
          Factors
        </button>
      </div>

      {/* Summary Tab */}
      {activeTab === 'summary' && (
        <div className="space-y-4">
          <div className="flex justify-between items-center p-4 bg-dark-bg rounded-md">
            <div>
              <div className="text-sm text-gray-400">Overall Sentiment</div>
              <div className={`text-2xl font-bold ${getSentimentColor(overallSentiment)}`}>
                {getSentimentLabel(overallSentiment)} ({overallSentiment.toFixed(2)})
              </div>
            </div>
            <div className="text-right">
              <div className="text-sm text-gray-400">Confidence</div>
              <div className="text-2xl font-bold">
                {(confidence * 100).toFixed(0)}%
              </div>
            </div>
          </div>

          {sentimentData.reasoning && (
            <div className="p-4 bg-dark-bg rounded-md">
              <div className="text-sm text-gray-400 mb-2">Analysis</div>
              <div className="text-sm">{sentimentData.reasoning}</div>
            </div>
          )}

          {sentimentData.key_themes && sentimentData.key_themes.length > 0 && (
            <div className="p-4 bg-dark-bg rounded-md">
              <div className="text-sm text-gray-400 mb-2">Key Themes</div>
              <div className="flex flex-wrap gap-2">
                {sentimentData.key_themes.map((theme, index) => (
                  <span
                    key={index}
                    className="px-3 py-1 bg-dark-card border border-dark-border rounded-full text-xs"
                  >
                    {theme}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Factors Tab */}
      {activeTab === 'factors' && (
        <div className="space-y-3">
          <div className="text-xs text-gray-400 mb-2">
            Sentiment breakdown by factor
          </div>

          {Object.entries(factors).map(([factorName, factorData]) => {
            const score = factorData.score || 0;
            const weight = factorData.weight || 0;
            const contribution = factorData.contribution || 0;

            return (
              <div key={factorName} className="p-3 bg-dark-bg rounded-md">
                <div className="flex justify-between items-center mb-2">
                  <div className="font-medium capitalize">
                    {factorName.replace('_', ' ')}
                  </div>
                  <div className="text-sm">
                    <span className={getSentimentColor(score)}>
                      {score > 0 ? '+' : ''}{score.toFixed(2)}
                    </span>
                    <span className="text-gray-400 ml-2">
                      (weight: {(weight * 100).toFixed(0)}%)
                    </span>
                  </div>
                </div>

                {/* Score bar */}
                <div className="relative h-2 bg-gray-700 rounded-full overflow-hidden">
                  <div
                    className={`absolute h-full ${getBarColor(score)} transition-all duration-300`}
                    style={{
                      width: `${Math.abs(score) * 50}%`,
                      left: score < 0 ? `${50 - Math.abs(score) * 50}%` : '50%',
                    }}
                  />
                  {/* Center marker */}
                  <div className="absolute left-1/2 top-0 w-px h-full bg-gray-500" />
                </div>

                <div className="mt-1 text-xs text-gray-400">
                  Contribution: {contribution > 0 ? '+' : ''}{contribution.toFixed(2)}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default SentimentReport;
