/**
 * Dashboard - Main application layout
 */

import React, { useState } from 'react';
import { useAnalysis } from '../hooks/useAnalysis';
import { useAnalysisContext } from '../context/AnalysisContext';
import AgentStatus from './AgentStatus';
import Recommendation from './Recommendation';
import SentimentReport from './SentimentReport';
import PriceChart from './PriceChart';
import Summary from './Summary';
import NewsFeed from './NewsFeed';

const Dashboard = () => {
  const [tickerInput, setTickerInput] = useState('');
  const [activeTab, setActiveTab] = useState('summary');
  const { runAnalysis, loading, error } = useAnalysis();
  const { analysis, progress, stage } = useAnalysisContext();

  const handleAnalyze = async (e) => {
    e.preventDefault();
    if (!tickerInput.trim()) return;

    try {
      await runAnalysis(tickerInput.trim().toUpperCase());
    } catch (err) {
      console.error('Analysis failed:', err);
    }
  };

  const getStageText = (stage) => {
    const stages = {
      starting: 'Starting analysis...',
      gathering_data: 'Gathering data from multiple sources...',
      running_market: 'Analyzing market data...',
      running_fundamentals: 'Analyzing company fundamentals...',
      running_news: 'Fetching recent news...',
      running_technical: 'Running technical analysis...',
      analyzing_sentiment: 'Analyzing market sentiment...',
      synthesizing: 'Synthesizing all insights...',
      saving: 'Saving results...',
      complete: 'Analysis complete!',
      error: 'Analysis failed',
    };
    return stages[stage] || stage;
  };

  return (
    <div className="min-h-screen bg-dark-bg text-white">
      {/* Header */}
      <div className="border-b border-dark-border">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-bold">AI Trading Analyst</h1>

            {/* Ticker Search */}
            <form onSubmit={handleAnalyze} className="flex space-x-2">
              <input
                type="text"
                value={tickerInput}
                onChange={(e) => setTickerInput(e.target.value.toUpperCase())}
                placeholder="Enter ticker (e.g., NVDA)"
                className="px-4 py-2 bg-dark-card border border-dark-border rounded-md focus:outline-none focus:ring-2 focus:ring-accent-blue uppercase"
                maxLength={5}
                disabled={loading}
              />
              <button
                type="submit"
                disabled={loading || !tickerInput.trim()}
                className="px-6 py-2 bg-accent-blue hover:bg-blue-600 disabled:bg-gray-700 disabled:cursor-not-allowed rounded-md font-medium transition-colors"
              >
                {loading ? 'Analyzing...' : 'Run Analysis'}
              </button>
            </form>
          </div>

          {/* Progress Bar */}
          {loading && (
            <div className="mt-4">
              <div className="flex justify-between items-center mb-1">
                <span className="text-sm text-gray-400">{getStageText(stage)}</span>
                <span className="text-sm text-gray-400">{progress}%</span>
              </div>
              <div className="w-full h-2 bg-gray-700 rounded-full overflow-hidden">
                <div
                  className="h-full bg-accent-blue transition-all duration-300"
                  style={{ width: `${progress}%` }}
                />
              </div>
            </div>
          )}

          {/* Error Display */}
          {error && (
            <div className="mt-4 p-3 bg-red-900/20 border border-red-500 rounded-md text-red-400 text-sm">
              {error}
            </div>
          )}
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div className="grid grid-cols-12 gap-6">
          {/* Left Sidebar - Agents */}
          <div className="col-span-3">
            <AgentStatus />
          </div>

          {/* Center - Chart */}
          <div className="col-span-6">
            <PriceChart analysis={analysis} />

            {/* Tabs */}
            <div className="mt-6">
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
                    activeTab === 'news'
                      ? 'border-b-2 border-accent-blue text-white'
                      : 'text-gray-400 hover:text-white'
                  }`}
                  onClick={() => setActiveTab('news')}
                >
                  News
                </button>
                <button
                  className={`pb-2 px-1 ${
                    activeTab === 'sentiment'
                      ? 'border-b-2 border-accent-blue text-white'
                      : 'text-gray-400 hover:text-white'
                  }`}
                  onClick={() => setActiveTab('sentiment')}
                >
                  Sentiment
                </button>
              </div>

              {/* Tab Content */}
              {activeTab === 'summary' && <Summary analysis={analysis} />}
              {activeTab === 'news' && <NewsFeed analysis={analysis} />}
              {activeTab === 'sentiment' && <SentimentReport analysis={analysis} />}
            </div>
          </div>

          {/* Right Sidebar - Recommendation */}
          <div className="col-span-3">
            <Recommendation analysis={analysis} />
          </div>
        </div>

        {/* Welcome Message */}
        {!analysis && !loading && (
          <div className="mt-12 text-center text-gray-400">
            <div className="text-6xl mb-4">📊</div>
            <h2 className="text-2xl font-bold mb-2">Welcome to AI Trading Analyst</h2>
            <p className="text-lg">
              Enter a stock ticker above to get started with multi-agent analysis
            </p>
            <div className="mt-6 grid grid-cols-3 gap-4 max-w-2xl mx-auto">
              <div className="p-4 bg-dark-card border border-dark-border rounded-lg">
                <div className="text-3xl mb-2">🤖</div>
                <div className="font-semibold">5 Specialized Agents</div>
                <div className="text-sm mt-1">Market, Fundamentals, News, Sentiment, Technical</div>
              </div>
              <div className="p-4 bg-dark-card border border-dark-border rounded-lg">
                <div className="text-3xl mb-2">⚡</div>
                <div className="font-semibold">Real-time Analysis</div>
                <div className="text-sm mt-1">Live updates as agents complete their work</div>
              </div>
              <div className="p-4 bg-dark-card border border-dark-border rounded-lg">
                <div className="text-3xl mb-2">🎯</div>
                <div className="font-semibold">AI-Powered Insights</div>
                <div className="text-sm mt-1">LLM reasoning for final recommendations</div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default Dashboard;
