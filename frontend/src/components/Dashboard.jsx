/**
 * Dashboard - Main application layout with sidebar navigation and tabbed content
 * Layout: Fixed 64px sidebar | Main content (flex-1) with ContentHeader + tabs + right sidebar
 */

import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAnalysis } from '../hooks/useAnalysis';
import { useAnalysisContext } from '../context/AnalysisContext';
import Sidebar from './Sidebar';
import ContentHeader from './ContentHeader';
import AnalysisTabs from './AnalysisTabs';
import AgentPipelineBar from './AgentPipelineBar';
import Recommendation from './Recommendation';
import SentimentReport from './SentimentReport';
import PriceChart from './PriceChart';
import { OverviewMetrics, ResearchContent, ChangeSummaryPanel } from './Summary';
import ScenarioPanel from './ScenarioPanel';
import DiagnosticsPanel from './DiagnosticsPanel';
import NewsFeed from './NewsFeed';
import SocialBuzz from './SocialBuzz';
import OptionsFlow from './OptionsFlow';
import MacroSnapshot from './MacroSnapshot';
import HistoryDashboard from './HistoryDashboard';
import WatchlistPanel from './WatchlistPanel';
import SchedulePanel from './SchedulePanel';
import AlertPanel from './AlertPanel';
import PortfolioPanel from './PortfolioPanel';
import { PulseIcon, SparklesIcon, ChartBarIcon, LoadingSpinner } from './Icons';
import { getUnacknowledgedCount } from '../utils/api';

const VIEW_MODES = {
  ANALYSIS: 'analysis',
  HISTORY: 'history',
  WATCHLIST: 'watchlist',
  PORTFOLIO: 'portfolio',
  SCHEDULES: 'schedules',
  ALERTS: 'alerts',
};

/* ─── framer-motion variants ─── */

const containerVariants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { staggerChildren: 0.12, delayChildren: 0.15 } },
};

const fadeUp = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: [0.22, 1, 0.36, 1] } },
};

const Dashboard = () => {
  const [tickerInput, setTickerInput] = useState('');
  const [viewMode, setViewMode] = useState(VIEW_MODES.ANALYSIS);
  const [activeTab, setActiveTab] = useState('overview');
  const [unacknowledgedCount, setUnacknowledgedCount] = useState(0);
  const { runAnalysis, loading, error } = useAnalysis();
  const { analysis, progress, stage, currentTicker } = useAnalysisContext();

  // Poll for unacknowledged alert count every 30 seconds
  useEffect(() => {
    const fetchCount = async () => {
      try {
        const data = await getUnacknowledgedCount();
        setUnacknowledgedCount(data.count ?? data ?? 0);
      } catch {
        // silently ignore - badge is non-critical
      }
    };
    fetchCount();
    const interval = setInterval(fetchCount, 30000);
    return () => clearInterval(interval);
  }, []);

  const handleAnalyze = async (e) => {
    e.preventDefault();
    if (!tickerInput.trim()) return;

    setViewMode(VIEW_MODES.ANALYSIS);
    setActiveTab('overview');

    try {
      await runAnalysis(tickerInput.trim().toUpperCase());
    } catch (err) {
      console.error('Analysis failed:', err);
    }
  };

  const handleQuickTicker = (ticker) => {
    setTickerInput(ticker);
    setViewMode(VIEW_MODES.ANALYSIS);
    setActiveTab('overview');
    runAnalysis(ticker).catch((err) => console.error('Analysis failed:', err));
  };

  const showAnalysisContent = analysis || loading;

  return (
    <div className="min-h-screen bg-dark-bg text-white flex">
      {/* ═══════════════════════════════════════════
          Left Sidebar Navigation
          ═══════════════════════════════════════════ */}
      <Sidebar
        activeView={viewMode}
        onViewChange={setViewMode}
        unacknowledgedCount={unacknowledgedCount}
      />

      {/* ═══════════════════════════════════════════
          Main Content Area (offset by sidebar width)
          ═══════════════════════════════════════════ */}
      <div className="flex-1" style={{ marginLeft: 'var(--sidebar-width, 64px)' }}>
        {/* ─── Non-analysis views ─── */}
        {viewMode === VIEW_MODES.HISTORY && (
          <div className="p-6">
            <HistoryDashboard
              onBack={() => setViewMode(VIEW_MODES.ANALYSIS)}
              initialTicker={currentTicker || null}
            />
          </div>
        )}

        {viewMode === VIEW_MODES.WATCHLIST && (
          <div className="p-6">
            <WatchlistPanel
              onBack={() => setViewMode(VIEW_MODES.ANALYSIS)}
            />
          </div>
        )}

        {viewMode === VIEW_MODES.SCHEDULES && (
          <div className="p-6">
            <SchedulePanel
              onBack={() => setViewMode(VIEW_MODES.ANALYSIS)}
            />
          </div>
        )}

        {viewMode === VIEW_MODES.PORTFOLIO && (
          <div className="p-6">
            <PortfolioPanel
              onBack={() => setViewMode(VIEW_MODES.ANALYSIS)}
            />
          </div>
        )}

        {viewMode === VIEW_MODES.ALERTS && (
          <div className="p-6">
            <AlertPanel
              onBack={() => setViewMode(VIEW_MODES.ANALYSIS)}
            />
          </div>
        )}

        {/* ─── Analysis View ─── */}
        {viewMode === VIEW_MODES.ANALYSIS && (
          <div className="flex flex-col h-screen">
            {/* Content Header — sticky at top */}
            <div className="sticky top-0 z-30 bg-dark-bg/80 backdrop-blur-xl border-b border-white/5">
              <ContentHeader
                tickerInput={tickerInput}
                setTickerInput={setTickerInput}
                onAnalyze={handleAnalyze}
                loading={loading}
                analysis={analysis}
                progress={progress}
                stage={stage}
              />

              {/* Agent Pipeline Bar — visible during/after analysis */}
              {showAnalysisContent && (
                <div className="px-6 pb-3">
                  <AgentPipelineBar />
                </div>
              )}

              {/* Error Display */}
              {error && (
                <div className="px-6 pb-3">
                  <motion.div
                    initial={{ opacity: 0, y: -8 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="p-3 bg-danger/10 border border-danger/30 rounded-lg text-danger-400 text-sm flex items-center space-x-2"
                  >
                    <svg width="16" height="16" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <circle cx="10" cy="10" r="7" />
                      <path d="M10 7v3M10 12.5v.5" />
                    </svg>
                    <span>{error}</span>
                  </motion.div>
                </div>
              )}
            </div>

            {/* ─── Content below header ─── */}
            <div className="flex-1 overflow-y-auto">
              <AnimatePresence mode="wait">
                {showAnalysisContent ? (
                  /* ─────── Analysis Content with Tabs ─────── */
                  <motion.div
                    key="analysis-content"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.3 }}
                    className="flex h-full"
                  >
                    {/* Left: Tabbed content area */}
                    <div className="flex-1 min-w-0">
                      {/* Tab bar */}
                      <div className="sticky top-0 z-20 bg-dark-bg/80 backdrop-blur-xl px-6 pt-3">
                        <AnalysisTabs
                          activeTab={activeTab}
                          onTabChange={setActiveTab}
                          analysis={analysis}
                        />
                      </div>

                      {/* Tab content */}
                      <div className="p-6">
                        <AnimatePresence mode="wait">
                          {/* Overview Tab */}
                          {activeTab === 'overview' && (
                            <motion.div
                              key="tab-overview"
                              initial={{ opacity: 0, y: 8 }}
                              animate={{ opacity: 1, y: 0 }}
                              exit={{ opacity: 0, y: -8 }}
                              transition={{ duration: 0.2 }}
                              className="space-y-6"
                            >
                              <PriceChart analysis={analysis} />
                              <OverviewMetrics analysis={analysis} />
                            </motion.div>
                          )}

                          {/* Changes Tab */}
                          {activeTab === 'changes' && (
                            <motion.div
                              key="tab-changes"
                              initial={{ opacity: 0, y: 8 }}
                              animate={{ opacity: 1, y: 0 }}
                              exit={{ opacity: 0, y: -8 }}
                              transition={{ duration: 0.2 }}
                            >
                              <ChangeSummaryPanel
                                analysis={analysis}
                                showFallbackWhenEmpty
                              />
                            </motion.div>
                          )}

                          {/* Scenarios Tab */}
                          {activeTab === 'scenarios' && (
                            <motion.div
                              key="tab-scenarios"
                              initial={{ opacity: 0, y: 8 }}
                              animate={{ opacity: 1, y: 0 }}
                              exit={{ opacity: 0, y: -8 }}
                              transition={{ duration: 0.2 }}
                            >
                              <ScenarioPanel analysis={analysis} />
                            </motion.div>
                          )}

                          {/* Diagnostics Tab */}
                          {activeTab === 'diagnostics' && (
                            <motion.div
                              key="tab-diagnostics"
                              initial={{ opacity: 0, y: 8 }}
                              animate={{ opacity: 1, y: 0 }}
                              exit={{ opacity: 0, y: -8 }}
                              transition={{ duration: 0.2 }}
                            >
                              <DiagnosticsPanel analysis={analysis} />
                            </motion.div>
                          )}

                          {/* Research Tab */}
                          {activeTab === 'research' && (
                            <motion.div
                              key="tab-research"
                              initial={{ opacity: 0, y: 8 }}
                              animate={{ opacity: 1, y: 0 }}
                              exit={{ opacity: 0, y: -8 }}
                              transition={{ duration: 0.2 }}
                            >
                              <ResearchContent analysis={analysis} />
                            </motion.div>
                          )}

                          {/* Sentiment Tab */}
                          {activeTab === 'sentiment' && (
                            <motion.div
                              key="tab-sentiment"
                              initial={{ opacity: 0, y: 8 }}
                              animate={{ opacity: 1, y: 0 }}
                              exit={{ opacity: 0, y: -8 }}
                              transition={{ duration: 0.2 }}
                              className="space-y-6"
                            >
                              <SentimentReport analysis={analysis} />
                              <SocialBuzz analysis={analysis} />
                            </motion.div>
                          )}

                          {/* News Tab */}
                          {activeTab === 'news' && (
                            <motion.div
                              key="tab-news"
                              initial={{ opacity: 0, y: 8 }}
                              animate={{ opacity: 1, y: 0 }}
                              exit={{ opacity: 0, y: -8 }}
                              transition={{ duration: 0.2 }}
                            >
                              <NewsFeed analysis={analysis} />
                            </motion.div>
                          )}

                          {/* Options Tab */}
                          {activeTab === 'options' && (
                            <motion.div
                              key="tab-options"
                              initial={{ opacity: 0, y: 8 }}
                              animate={{ opacity: 1, y: 0 }}
                              exit={{ opacity: 0, y: -8 }}
                              transition={{ duration: 0.2 }}
                            >
                              <OptionsFlow analysis={analysis} />
                            </motion.div>
                          )}
                        </AnimatePresence>
                      </div>
                    </div>

                    {/* Right sidebar — Recommendation + Macro */}
                    <motion.div
                      initial={{ opacity: 0, x: 12 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ duration: 0.4, ease: 'easeOut' }}
                      className="hidden lg:block w-[340px] shrink-0 border-l border-white/5 p-5 space-y-5 overflow-y-auto"
                    >
                      <Recommendation analysis={analysis} />
                      <MacroSnapshot analysis={analysis} />
                    </motion.div>
                  </motion.div>
                ) : (
                  /* ─────── Welcome Screen ─────── */
                  <motion.div
                    key="welcome-screen"
                    initial="hidden"
                    animate="visible"
                    exit={{ opacity: 0 }}
                    variants={containerVariants}
                    className="flex flex-col items-center justify-center min-h-[calc(100vh-80px)] px-6 relative"
                  >
                    {/* Subtle dot grid background */}
                    <div
                      className="absolute inset-0 opacity-[0.03] pointer-events-none"
                      style={{
                        backgroundImage: 'radial-gradient(circle, rgba(255,255,255,0.8) 1px, transparent 1px)',
                        backgroundSize: '24px 24px',
                      }}
                    />

                    {/* Animated Chart Icon */}
                    <motion.div variants={fadeUp} className="flex justify-center relative z-10">
                      <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-primary/20 to-primary-300/20 border border-primary/20 flex items-center justify-center">
                        <PulseIcon className="w-10 h-10 text-primary-400" />
                      </div>
                    </motion.div>

                    <motion.h2
                      variants={fadeUp}
                      className="text-4xl sm:text-5xl font-bold mt-6 mb-3 tracking-tight bg-gradient-to-r from-white via-white to-gray-400 bg-clip-text text-transparent relative z-10"
                    >
                      AI Trading Analyst
                    </motion.h2>

                    <motion.p variants={fadeUp} className="text-gray-400 text-lg max-w-md mx-auto text-center relative z-10">
                      Multi-agent research platform
                    </motion.p>

                    {/* Hero search input */}
                    <motion.form
                      variants={fadeUp}
                      onSubmit={handleAnalyze}
                      className="mt-8 flex items-center gap-3 relative z-10"
                    >
                      <input
                        type="text"
                        value={tickerInput}
                        onChange={(e) => setTickerInput(e.target.value.toUpperCase())}
                        placeholder="Enter ticker symbol"
                        className="w-[320px] sm:w-[400px] px-5 py-4 bg-dark-inset border border-dark-border rounded-xl text-base font-mono uppercase text-white placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-accent-blue/40 focus:border-accent-blue/50 focus:shadow-[0_0_20px_rgba(0,111,238,0.2)] transition-all"
                        maxLength={5}
                        disabled={loading}
                        autoFocus
                      />
                      <button
                        type="submit"
                        disabled={loading || !tickerInput.trim()}
                        className="px-6 py-4 bg-gradient-to-r from-primary-600 to-primary hover:from-primary hover:to-primary-400 disabled:from-zinc-700 disabled:to-zinc-700 disabled:cursor-not-allowed rounded-xl font-medium text-base transition-all flex items-center gap-2 whitespace-nowrap"
                      >
                        {loading ? (
                          <>
                            <LoadingSpinner size={16} />
                            <span>Analyzing</span>
                          </>
                        ) : (
                          <span>Analyze</span>
                        )}
                      </button>
                    </motion.form>

                    {/* Quick Start Tickers */}
                    <motion.div variants={fadeUp} className="mt-5 flex items-center justify-center flex-wrap gap-2 relative z-10">
                      <span className="text-xs text-gray-500 mr-1">Quick start:</span>
                      {['AAPL', 'NVDA', 'TSLA', 'MSFT', 'AMZN', 'GOOGL'].map((ticker) => (
                        <button
                          key={ticker}
                          onClick={() => handleQuickTicker(ticker)}
                          className="px-5 py-2 text-xs font-mono font-medium text-accent-blue bg-accent-blue/10 border border-accent-blue/20 rounded-full hover:bg-accent-blue/20 hover:border-accent-blue/40 transition-all"
                        >
                          {ticker}
                        </button>
                      ))}
                    </motion.div>

                    {/* Feature Cards */}
                    <motion.div
                      variants={containerVariants}
                      className="mt-12 grid grid-cols-1 sm:grid-cols-3 gap-5 max-w-2xl mx-auto relative z-10"
                    >
                      <motion.div
                        variants={fadeUp}
                        className="glass-card-elevated rounded-xl p-5 text-left border-t-2 border-t-accent-blue"
                      >
                        <div className="w-9 h-9 rounded-lg bg-accent-blue/15 flex items-center justify-center mb-3">
                          <ChartBarIcon className="w-5 h-5 text-accent-blue" />
                        </div>
                        <div className="font-semibold text-sm mb-1">7 Specialized Agents</div>
                        <div className="text-xs text-gray-400 leading-relaxed">Market, Fundamentals, News, Technical, Macro, Options, Sentiment</div>
                      </motion.div>

                      <motion.div
                        variants={fadeUp}
                        className="glass-card-elevated rounded-xl p-5 text-left border-t-2 border-t-accent-green"
                      >
                        <div className="w-9 h-9 rounded-lg bg-accent-green/15 flex items-center justify-center mb-3">
                          <PulseIcon className="w-5 h-5 text-accent-green" />
                        </div>
                        <div className="font-semibold text-sm mb-1">Real-time Analysis</div>
                        <div className="text-xs text-gray-400 leading-relaxed">Live updates as agents complete their work</div>
                      </motion.div>

                      <motion.div
                        variants={fadeUp}
                        className="glass-card-elevated rounded-xl p-5 text-left border-t-2 border-t-accent-purple"
                      >
                        <div className="w-9 h-9 rounded-lg bg-accent-purple/15 flex items-center justify-center mb-3">
                          <SparklesIcon className="w-5 h-5 text-accent-purple" />
                        </div>
                        <div className="font-semibold text-sm mb-1">AI-Powered Insights</div>
                        <div className="text-xs text-gray-400 leading-relaxed">Chain-of-thought reasoning for recommendations</div>
                      </motion.div>
                    </motion.div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default Dashboard;
