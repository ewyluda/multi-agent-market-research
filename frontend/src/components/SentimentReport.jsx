/**
 * SentimentReport - Sentiment analysis with factor breakdown
 */

import React, { useState } from 'react';

const SentimentReport = ({ analysis }) => {
  const [activeTab, setActiveTab] = useState('summary');

  if (!analysis || !analysis.agent_results?.sentiment) {
    return (
      <div className="glass-card-elevated rounded-xl p-5">
        <div className="skeleton h-4 w-36 mb-4" />
        <div className="skeleton h-16 w-full mb-3 rounded-lg" />
        <div className="skeleton h-24 w-full rounded-lg" />
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
    if (score > 0.3) return 'text-emerald-400';
    if (score < -0.3) return 'text-red-400';
    return 'text-amber-400';
  };

  // Map sentiment score (-1 to 1) to percentage position (0% to 100%)
  const sentimentPosition = ((overallSentiment + 1) / 2) * 100;

  return (
    <div className="glass-card-elevated rounded-xl p-5">
      <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider mb-4">Sentiment Report</h3>

      {/* Inner Tabs */}
      <div className="flex space-x-2 mb-4">
        {['summary', 'factors'].map((tab) => (
          <button
            key={tab}
            className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all capitalize ${
              activeTab === tab
                ? 'bg-accent-purple/15 text-accent-purple border border-accent-purple/30'
                : 'text-gray-400 hover:text-gray-200 hover:bg-white/5 border border-transparent'
            }`}
            onClick={() => setActiveTab(tab)}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Summary Tab */}
      {activeTab === 'summary' && (
        <div className="space-y-4 animate-fade-in">
          {/* Sentiment Meter */}
          <div className="p-4 bg-dark-inset rounded-lg">
            <div className="flex justify-between items-center mb-3">
              <div>
                <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Overall Sentiment</div>
                <div className={`text-2xl font-bold ${getSentimentColor(overallSentiment)}`}>
                  {getSentimentLabel(overallSentiment)}
                  <span className="text-sm ml-1.5 opacity-60">{overallSentiment.toFixed(2)}</span>
                </div>
              </div>
              <div className="text-right">
                <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Confidence</div>
                <div className="text-2xl font-bold tabular-nums">{(confidence * 100).toFixed(0)}%</div>
              </div>
            </div>

            {/* Sentiment bar: red to green */}
            <div className="relative h-2 bg-gradient-to-r from-red-500/40 via-amber-500/40 to-emerald-500/40 rounded-full">
              {/* Center marker */}
              <div className="absolute left-1/2 top-0 w-px h-full bg-gray-500/50" />
              {/* Position marker */}
              <div
                className="absolute top-1/2 -translate-y-1/2 w-3 h-3 rounded-full bg-white border-2 border-gray-800 shadow-lg transition-all duration-500"
                style={{ left: `${sentimentPosition}%`, transform: 'translate(-50%, -50%)' }}
              />
            </div>
            <div className="flex justify-between mt-1.5 text-[9px] text-gray-500">
              <span>Bearish</span>
              <span>Neutral</span>
              <span>Bullish</span>
            </div>
          </div>

          {/* Reasoning */}
          {sentimentData.reasoning && (
            <div className="p-4 bg-dark-inset rounded-lg">
              <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Analysis</div>
              <div className="text-sm text-gray-300 leading-relaxed">{sentimentData.reasoning}</div>
            </div>
          )}

          {/* Key Themes */}
          {sentimentData.key_themes && sentimentData.key_themes.length > 0 && (
            <div className="p-4 bg-dark-inset rounded-lg">
              <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Key Themes</div>
              <div className="flex flex-wrap gap-1.5">
                {sentimentData.key_themes.map((theme, index) => (
                  <span
                    key={index}
                    className="px-2.5 py-1 bg-accent-purple/10 border border-accent-purple/20 rounded-md text-[10px] text-accent-purple font-medium"
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
        <div className="space-y-2.5 animate-fade-in">
          <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-3">
            Sentiment by Factor
          </div>

          {Object.entries(factors).map(([factorName, factorData]) => {
            const score = factorData.score || 0;
            const weight = factorData.weight || 0;
            const contribution = factorData.contribution || 0;

            // Bar width: score maps from -1..1, bar goes from center
            const barWidth = Math.abs(score) * 50;
            const barLeft = score < 0 ? 50 - barWidth : 50;

            return (
              <div key={factorName} className="p-3 bg-dark-inset rounded-lg">
                <div className="flex justify-between items-center mb-2">
                  <div className="font-medium text-xs capitalize">
                    {factorName.replace(/_/g, ' ')}
                  </div>
                  <div className="flex items-center space-x-2">
                    <span className={`text-xs font-semibold tabular-nums ${getSentimentColor(score)}`}>
                      {score > 0 ? '+' : ''}{score.toFixed(2)}
                    </span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-accent-purple/15 text-accent-purple font-medium">
                      {(weight * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>

                {/* Centered bar chart */}
                <div className="relative h-1.5 bg-gray-700/50 rounded-full overflow-hidden">
                  <div
                    className={`absolute h-full rounded-full transition-all duration-500 ${
                      score > 0 ? 'bg-emerald-500' : 'bg-red-500'
                    }`}
                    style={{
                      width: `${barWidth}%`,
                      left: `${barLeft}%`,
                      opacity: 0.7,
                    }}
                  />
                  <div className="absolute left-1/2 top-0 w-px h-full bg-gray-500/50" />
                </div>

                <div className="mt-1.5 text-[10px] text-gray-500 tabular-nums">
                  Contribution: <span className={getSentimentColor(contribution)}>{contribution > 0 ? '+' : ''}{contribution.toFixed(3)}</span>
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
