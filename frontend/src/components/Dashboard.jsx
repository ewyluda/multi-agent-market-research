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
import { DocumentIcon, NewspaperIcon, BrainIcon, PulseIcon, SparklesIcon, ChartBarIcon, LoadingSpinner } from './Icons';

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

  const handleQuickTicker = (ticker) => {
    setTickerInput(ticker);
    runAnalysis(ticker).catch((err) => console.error('Analysis failed:', err));
  };

  const getStageText = (stage) => {
    const stages = {
      starting: 'Initializing analysis pipeline...',
      gathering_data: 'Gathering data from multiple sources...',
      running_market: 'Analyzing market data...',
      running_fundamentals: 'Analyzing company fundamentals...',
      running_news: 'Fetching recent news...',
      running_technical: 'Running technical analysis...',
      analyzing_sentiment: 'Analyzing market sentiment...',
      synthesizing: 'AI synthesizing all insights...',
      saving: 'Saving results...',
      complete: 'Analysis complete',
      error: 'Analysis failed',
    };
    return stages[stage] || stage;
  };

  const tabs = [
    { id: 'summary', label: 'Summary', icon: DocumentIcon },
    { id: 'news', label: 'News', icon: NewspaperIcon },
    { id: 'sentiment', label: 'Sentiment', icon: BrainIcon },
  ];

  return (
    <div className="min-h-screen bg-dark-bg text-white">
      {/* Header */}
      <div className="sticky top-0 z-50 glass-card-elevated border-b border-white/5">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            {/* Brand */}
            <div className="flex items-center space-x-3">
              <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-primary to-primary-300 flex items-center justify-center">
                <PulseIcon className="w-5 h-5 text-white" />
              </div>
              <div>
                <h1 className="text-lg font-bold tracking-tight">AI Trading Analyst</h1>
                <p className="text-xs text-gray-500">Multi-agent research platform</p>
              </div>
            </div>

            {/* Ticker Search */}
            <form onSubmit={handleAnalyze} className="flex space-x-2">
              <div className="relative">
                <input
                  type="text"
                  value={tickerInput}
                  onChange={(e) => setTickerInput(e.target.value.toUpperCase())}
                  placeholder="Enter ticker (e.g., NVDA)"
                  className="pl-4 pr-4 py-2 bg-dark-inset border border-dark-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-accent-blue/30 focus:border-accent-blue/50 focus:shadow-[0_0_15px_rgba(0,111,238,0.15)] transition-all uppercase w-56"
                  maxLength={5}
                  disabled={loading}
                />
              </div>
              <button
                type="submit"
                disabled={loading || !tickerInput.trim()}
                className="px-5 py-2 bg-gradient-to-r from-primary-600 to-primary hover:from-primary hover:to-primary-400 disabled:from-zinc-700 disabled:to-zinc-700 disabled:cursor-not-allowed rounded-lg font-medium text-sm transition-all flex items-center space-x-2"
              >
                {loading ? (
                  <>
                    <LoadingSpinner size={16} />
                    <span>Analyzing</span>
                  </>
                ) : (
                  <span>Run Analysis</span>
                )}
              </button>
            </form>
          </div>

          {/* Progress Bar */}
          {loading && (
            <div className="mt-4 animate-fade-in">
              <div className="flex justify-between items-center mb-1.5">
                <span className="text-xs text-gray-400 font-medium tracking-wide">{getStageText(stage)}</span>
                <span className="text-xs text-accent-blue font-semibold tabular-nums">{progress}%</span>
              </div>
              <div className="w-full h-1.5 bg-dark-inset rounded-full overflow-hidden shadow-inner">
                <div
                  className="h-full bg-gradient-to-r from-primary-600 via-primary to-primary-300 rounded-full transition-all duration-500 ease-out relative"
                  style={{ width: `${progress}%` }}
                >
                  <div
                    className="absolute inset-0 w-1/2 bg-gradient-to-r from-transparent via-white/20 to-transparent"
                    style={{ animation: 'progressShine 1.5s ease-in-out infinite' }}
                  />
                </div>
              </div>
            </div>
          )}

          {/* Error Display */}
          {error && (
            <div className="mt-4 p-3 bg-danger/10 border border-danger/30 rounded-lg text-danger-400 text-sm flex items-center space-x-2 animate-fade-in">
              <svg width="16" height="16" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
                <circle cx="10" cy="10" r="7" />
                <path d="M10 7v3M10 12.5v.5" />
              </svg>
              <span>{error}</span>
            </div>
          )}
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {analysis || loading ? (
          <div className="grid grid-cols-12 gap-6 animate-fade-in">
            {/* Left Sidebar - Agents */}
            <div className="col-span-3 animate-slide-left">
              <AgentStatus />
            </div>

            {/* Center - Chart & Tabs */}
            <div className="col-span-6">
              <PriceChart analysis={analysis} />

              {/* Tabs */}
              <div className="mt-6">
                <div className="flex space-x-2 mb-5">
                  {tabs.map((tab) => {
                    const Icon = tab.icon;
                    const isActive = activeTab === tab.id;
                    return (
                      <button
                        key={tab.id}
                        className={`flex items-center space-x-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                          isActive
                            ? 'bg-accent-blue/15 text-accent-blue border border-accent-blue/30'
                            : 'text-gray-400 hover:text-gray-200 hover:bg-white/5 border border-transparent'
                        }`}
                        onClick={() => setActiveTab(tab.id)}
                      >
                        <Icon className="w-4 h-4" />
                        <span>{tab.label}</span>
                      </button>
                    );
                  })}
                </div>

                {/* Tab Content */}
                <div className="animate-fade-in">
                  {activeTab === 'summary' && <Summary analysis={analysis} />}
                  {activeTab === 'news' && <NewsFeed analysis={analysis} />}
                  {activeTab === 'sentiment' && <SentimentReport analysis={analysis} />}
                </div>
              </div>
            </div>

            {/* Right Sidebar - Recommendation */}
            <div className="col-span-3 animate-slide-right">
              <Recommendation analysis={analysis} />
            </div>
          </div>
        ) : (
          /* Welcome Screen */
          <div className="mt-16 text-center animate-fade-in">
            {/* Animated Chart Icon */}
            <div className="w-20 h-20 mx-auto mb-6 rounded-2xl bg-gradient-to-br from-primary/20 to-primary-300/20 border border-primary/20 flex items-center justify-center">
              <PulseIcon className="w-10 h-10 text-primary-400" />
            </div>

            <h2 className="text-3xl font-bold mb-2 tracking-tight">AI Trading Analyst</h2>
            <p className="text-gray-400 text-lg max-w-md mx-auto">
              Enter a stock ticker to get multi-agent AI analysis with real-time insights
            </p>

            {/* Quick Start Tickers */}
            <div className="mt-6 flex items-center justify-center space-x-2">
              <span className="text-xs text-gray-500 mr-1">Quick start:</span>
              {['AAPL', 'NVDA', 'TSLA', 'MSFT'].map((ticker) => (
                <button
                  key={ticker}
                  onClick={() => handleQuickTicker(ticker)}
                  className="px-3 py-1 text-xs font-mono font-medium text-accent-blue bg-accent-blue/10 border border-accent-blue/20 rounded-md hover:bg-accent-blue/20 hover:border-accent-blue/40 transition-all"
                >
                  {ticker}
                </button>
              ))}
            </div>

            {/* Feature Cards */}
            <div className="mt-12 grid grid-cols-3 gap-5 max-w-2xl mx-auto">
              <div
                className="glass-card rounded-xl p-5 text-left border-t-2 border-t-accent-blue animate-fade-in"
                style={{ animationDelay: '0.1s', opacity: 0 }}
              >
                <div className="w-9 h-9 rounded-lg bg-accent-blue/15 flex items-center justify-center mb-3">
                  <ChartBarIcon className="w-5 h-5 text-accent-blue" />
                </div>
                <div className="font-semibold text-sm mb-1">5 Specialized Agents</div>
                <div className="text-xs text-gray-400 leading-relaxed">Market, Fundamentals, News, Sentiment, Technical</div>
              </div>
              <div
                className="glass-card rounded-xl p-5 text-left border-t-2 border-t-accent-green animate-fade-in"
                style={{ animationDelay: '0.2s', opacity: 0 }}
              >
                <div className="w-9 h-9 rounded-lg bg-accent-green/15 flex items-center justify-center mb-3">
                  <PulseIcon className="w-5 h-5 text-accent-green" />
                </div>
                <div className="font-semibold text-sm mb-1">Real-time Analysis</div>
                <div className="text-xs text-gray-400 leading-relaxed">Live updates as agents complete their work</div>
              </div>
              <div
                className="glass-card rounded-xl p-5 text-left border-t-2 border-t-accent-purple animate-fade-in"
                style={{ animationDelay: '0.3s', opacity: 0 }}
              >
                <div className="w-9 h-9 rounded-lg bg-accent-purple/15 flex items-center justify-center mb-3">
                  <SparklesIcon className="w-5 h-5 text-accent-purple" />
                </div>
                <div className="font-semibold text-sm mb-1">AI-Powered Insights</div>
                <div className="text-xs text-gray-400 leading-relaxed">LLM reasoning for final recommendations</div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default Dashboard;
