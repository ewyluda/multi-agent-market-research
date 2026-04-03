/**
 * Dashboard - Main application layout with sidebar navigation and scrollable narrative content.
 * Layout: 220px sidebar | Main content (flex-1) with SearchBar + narrative sections
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { motion as Motion, AnimatePresence } from 'framer-motion';
import { useAnalysis } from '../hooks/useAnalysis';
import { useAnalysisContext } from '../context/AnalysisContext';
import { getUnacknowledgedCount } from '../utils/api';
import Sidebar from './Sidebar';
import SearchBar from './SearchBar';
import ThesisCard from './ThesisCard';
import PriceChart from './PriceChart';
import SectionNav from './SectionNav';
import AnalysisSection from './AnalysisSection';
import MetaFooter from './MetaFooter';
import LeadershipPanel from './LeadershipPanel';
import CouncilPanel from './CouncilPanel';
import NewsFeed from './NewsFeed';
import OptionsFlow from './OptionsFlow';
import EarningsPanel from './EarningsPanel';
import ThesisPanel from './ThesisPanel';
import EarningsReviewPanel from './EarningsReviewPanel';
import NarrativePanel from './NarrativePanel';
import RiskDiffPanel from './RiskDiffPanel';
import CompanyOverview from './CompanyOverview';
import TechnicalsOptionsSection from './TechnicalsOptionsSection';
import HistoryView from './HistoryView';
import WatchlistView from './WatchlistView';
import PortfolioView from './PortfolioView';
import SchedulesView from './SchedulesView';
import AlertsView from './AlertsView';
import InflectionView from './InflectionView';
import { PulseIcon, SparklesIcon, ChartBarIcon, LoadingSpinner } from './Icons';

/* ─── View modes ─── */
const VIEW_MODES = {
  ANALYSIS: 'analysis',
  HISTORY: 'history',
  WATCHLIST: 'watchlist',
  INFLECTIONS: 'inflections',
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

/* ─── Agent stance helpers ─── */
function getAgentStance(agentKey, result) {
  if (!result?.success || !result?.data) return 'neutral';
  const d = result.data;

  switch (agentKey) {
    case 'fundamentals': {
      const score = d.health_score ?? d.fundamental_health_score;
      if (score > 60) return 'bullish';
      if (score < 40) return 'bearish';
      return 'neutral';
    }
    case 'technical': {
      const sig = d.signals?.overall || d.overall_signal || '';
      if (/bull/i.test(sig)) return 'bullish';
      if (/bear/i.test(sig)) return 'bearish';
      return 'neutral';
    }
    case 'sentiment': {
      const s = d.overall_sentiment ?? d.sentiment_score;
      if (s > 0.3) return 'bullish';
      if (s < -0.3) return 'bearish';
      return 'neutral';
    }
    case 'market': {
      const trend = d.trend || d.market_trend || '';
      if (/up|bull/i.test(trend)) return 'bullish';
      if (/down|bear/i.test(trend)) return 'bearish';
      return 'neutral';
    }
    case 'macro': {
      const env = d.risk_environment || d.monetary_policy_stance || '';
      if (/dovish/i.test(env)) return 'bullish';
      if (/hawkish/i.test(env)) return 'bearish';
      return 'neutral';
    }
    case 'earnings': {
      const stance = d.stance || '';
      if (/bull/i.test(stance)) return 'bullish';
      if (/bear/i.test(stance)) return 'bearish';
      return 'neutral';
    }
    case 'options': {
      const sig = d.overall_signal || '';
      if (/bull/i.test(sig)) return 'bullish';
      if (/bear/i.test(sig)) return 'bearish';
      return 'neutral';
    }
    case 'news': {
      const articles = d.articles || d.news_items || [];
      if (articles.length === 0) return 'neutral';
      const avg = articles.reduce((sum, a) => sum + (a.sentiment_score ?? a.sentiment ?? 0), 0) / articles.length;
      if (avg > 0.15) return 'bullish';
      if (avg < -0.15) return 'bearish';
      return 'neutral';
    }
    case 'thesis': return 'neutral';
    case 'earnings_review': {
      const verdict = d?.beat_miss?.[0]?.verdict;
      if (verdict === 'beat') return 'bullish';
      if (verdict === 'miss') return 'bearish';
      return 'neutral';
    }
    case 'narrative': return 'neutral';
    case 'risk_diff': {
      const delta = d?.risk_score_delta ?? 0;
      if (delta > 5) return 'bearish';
      if (delta < -5) return 'bullish';
      return 'neutral';
    }
    default:
      return 'neutral';
  }
}

const STANCE_COLORS = { bullish: '#17c964', bearish: '#f31260', neutral: '#f5a524' };

/* ─── Agent summary extractor ─── */
function getAgentSummary(result) {
  if (!result?.success || !result?.data) return null;
  const d = result.data;
  return d.analysis || d.summary || d.executive_summary || d.thesis_summary || d.company_arc || d.assessment || null;
}

/* ─── Agent metrics extractors ─── */
function getAgentMetrics(agentKey, result) {
  if (!result?.success || !result?.data) return [];
  const d = result.data;

  switch (agentKey) {
    case 'fundamentals':
      return [
        d.pe_ratio != null && { label: 'P/E', value: Number(d.pe_ratio).toFixed(1) },
        d.revenue_growth != null && { label: 'Rev Growth', value: `${(d.revenue_growth * 100).toFixed(1)}%` },
        (d.profit_margin ?? d.net_margin) != null && { label: 'Margin', value: `${((d.profit_margin ?? d.net_margin) * 100).toFixed(1)}%` },
        (d.health_score ?? d.fundamental_health_score) != null && { label: 'Health', value: `${d.health_score ?? d.fundamental_health_score}/100` },
      ].filter(Boolean);
    case 'technical':
      return [
        d.rsi != null && { label: 'RSI', value: Number(d.rsi).toFixed(1) },
        d.macd_interpretation && { label: 'MACD', value: d.macd_interpretation },
        d.signal_strength && { label: 'Strength', value: d.signal_strength },
      ].filter(Boolean);
    case 'sentiment':
      return [
        d.overall_sentiment != null && { label: 'Score', value: Number(d.overall_sentiment).toFixed(2) },
      ].filter(Boolean);
    case 'macro':
      return [
        d.fed_funds_rate != null && { label: 'Fed Rate', value: `${d.fed_funds_rate}%` },
        d.cpi != null && { label: 'CPI', value: `${d.cpi}%` },
        d.gdp_growth != null && { label: 'GDP', value: `${d.gdp_growth}%` },
      ].filter(Boolean);
    case 'options':
      return [
        d.put_call_ratio != null && { label: 'P/C Ratio', value: Number(d.put_call_ratio).toFixed(2) },
        d.overall_signal && { label: 'Signal', value: d.overall_signal },
        d.max_pain != null && { label: 'Max Pain', value: `$${d.max_pain}` },
      ].filter(Boolean);
    default:
      return [];
  }
}

/* ─── Section config ─── */
const SECTION_ORDER = [
  { key: 'company_overview', name: 'Company Overview', special: 'company_overview' },
  { key: 'earnings', name: 'Earnings', special: 'earnings' },
  { key: 'earnings_review', name: 'Earnings Review', special: 'earnings_review' },
  { key: 'thesis', name: 'Thesis', special: 'thesis' },
  { key: 'risk_diff', name: 'Risk Analysis', special: 'risk_diff' },
  { key: 'technicals_options', name: 'Technicals & Options', special: 'technicals_options' },
  { key: 'sentiment', name: 'Sentiment', special: false },
  { key: 'news', name: 'News', special: 'news' },
  { key: 'leadership', name: 'Leadership', special: 'leadership' },
  { key: 'council', name: 'Council', special: 'council' },
];

/* ═══════════════════════════════════════════
   Dashboard Component
   ═══════════════════════════════════════════ */

const Dashboard = () => {
  const [tickerInput, setTickerInput] = useState('');
  const [viewMode, setViewMode] = useState(VIEW_MODES.ANALYSIS);
  const [unacknowledgedCount, setUnacknowledgedCount] = useState(0);
  const [recentAnalyses, setRecentAnalyses] = useState([]);
  const recentAnalysesRef = useRef([]);
  const [hasStartedAnalysis, setHasStartedAnalysis] = useState(false);

  const { runAnalysis, loading, error } = useAnalysis();
  const { analysis, progress, stage, currentTicker } = useAnalysisContext();

  /* ─── Poll alert count every 30s ─── */
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

  /* ─── Track recent analyses (max 5, deduplicated) ─── */
  useEffect(() => {
    if (!analysis?.ticker) return;
    const rec = analysis?.analysis?.signal_contract_v2?.recommendation
      || analysis?.analysis?.recommendation
      || null;
    const entry = { ticker: analysis.ticker, recommendation: rec };
    const filtered = recentAnalysesRef.current.filter((r) => r.ticker !== analysis.ticker);
    const updated = [entry, ...filtered].slice(0, 5);
    recentAnalysesRef.current = updated;
    setRecentAnalyses(updated);
  }, [analysis?.ticker]);

  /* ─── Handlers ─── */
  const handleAnalyze = useCallback(async (e) => {
    e?.preventDefault?.();
    if (!tickerInput.trim()) return;
    setViewMode(VIEW_MODES.ANALYSIS);
    setHasStartedAnalysis(true);
    try {
      await runAnalysis(tickerInput.trim().toUpperCase());
    } catch (err) {
      console.error('Analysis failed:', err);
    }
  }, [tickerInput, runAnalysis]);

  const handleQuickTicker = useCallback((ticker) => {
    setTickerInput(ticker);
    setViewMode(VIEW_MODES.ANALYSIS);
    setHasStartedAnalysis(true);
    runAnalysis(ticker).catch((err) => console.error('Analysis failed:', err));
  }, [runAnalysis]);

  const handleSelectFromHistory = useCallback((ticker) => {
    setTickerInput(ticker);
    setViewMode(VIEW_MODES.ANALYSIS);
    setHasStartedAnalysis(true);
    runAnalysis(ticker).catch((err) => console.error('Analysis failed:', err));
  }, [runAnalysis]);

  const handleSelectTicker = useCallback((ticker) => {
    setTickerInput(ticker);
    setViewMode(VIEW_MODES.ANALYSIS);
    setHasStartedAnalysis(true);
    runAnalysis(ticker).catch((err) => console.error('Analysis failed:', err));
  }, [runAnalysis]);

  /* ─── Derived ─── */
  // Once an analysis has been started, never revert to the welcome screen.
  // Show analysis content if we have data, are loading, have an error, or have ever started.
  const showAnalysisContent = analysis || loading || error || hasStartedAnalysis;
  const agentResults = analysis?.agent_results || {};

  /* Add onSelect callbacks to recentAnalyses for Sidebar */
  const recentWithCallbacks = recentAnalyses.map((r) => ({
    ...r,
    onSelect: () => handleQuickTicker(r.ticker),
  }));

  /* ─── Render special section children ─── */
  function renderSpecialChildren(key) {
    switch (key) {
      case 'earnings':
        return <EarningsPanel analysis={analysis} />;
      case 'news':
        return <NewsFeed analysis={analysis} />;
      case 'options':
        return <OptionsFlow analysis={analysis} />;
      case 'leadership':
        return <LeadershipPanel analysis={analysis} />;
      case 'council':
        return <CouncilPanel analysis={analysis} ticker={currentTicker} />;
      case 'earnings_review':
        return <EarningsReviewPanel analysis={analysis} />;
      case 'thesis':
        return <ThesisPanel analysis={analysis} />;
      case 'narrative':
        return <NarrativePanel analysis={analysis} />;
      case 'risk_diff':
        return <RiskDiffPanel analysis={analysis} />;
      case 'company_overview':
        return <CompanyOverview analysis={analysis} />;
      case 'technicals_options':
        return <TechnicalsOptionsSection analysis={analysis} />;
      default:
        return null;
    }
  }

  return (
    <div className="flex min-h-screen" style={{ background: 'var(--bg-primary)' }}>
      {/* ═══ Sidebar ═══ */}
      <Sidebar
        activeView={viewMode}
        onViewChange={setViewMode}
        unacknowledgedCount={unacknowledgedCount}
        recentAnalyses={recentWithCallbacks}
      />

      {/* ═══ Main Content ═══ */}
      <main className="flex-1 flex flex-col" style={{ marginLeft: 'var(--sidebar-width, 220px)' }}>
        {/* Search bar — sticky top */}
        <SearchBar
          tickerInput={tickerInput}
          setTickerInput={setTickerInput}
          onAnalyze={handleAnalyze}
          loading={loading}
          analysis={analysis}
          stage={stage}
          progress={progress}
        />

        {/* Error banner */}
        {error && (
          <div className="px-6 pt-2">
            <Motion.div
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              className="p-3 bg-danger/10 border border-danger/30 rounded-lg text-danger-400 text-sm flex items-center space-x-2"
            >
              <svg width="16" height="16" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
                <circle cx="10" cy="10" r="7" />
                <path d="M10 7v3M10 12.5v.5" />
              </svg>
              <span>{error}</span>
            </Motion.div>
          </div>
        )}

        {/* ─── Non-analysis views ─── */}
        {viewMode === VIEW_MODES.HISTORY && (
          <HistoryView onSelectAnalysis={handleSelectFromHistory} />
        )}
        {viewMode === VIEW_MODES.INFLECTIONS && <InflectionView />}
        {viewMode === VIEW_MODES.WATCHLIST && (
          <WatchlistView onSelectTicker={handleSelectTicker} />
        )}
        {viewMode === VIEW_MODES.PORTFOLIO && (
          <PortfolioView onSelectTicker={handleSelectTicker} />
        )}
        {viewMode === VIEW_MODES.SCHEDULES && <SchedulesView />}
        {viewMode === VIEW_MODES.ALERTS && <AlertsView />}

        {/* ─── Analysis View ─── */}
        {viewMode === VIEW_MODES.ANALYSIS && (
          <>
            {/* Welcome state */}
            {!showAnalysisContent && (
              <Motion.div
                key="welcome-screen"
                initial="hidden"
                animate="visible"
                exit={{ opacity: 0 }}
                variants={containerVariants}
                className="flex flex-col items-center justify-center min-h-[calc(100vh-80px)] px-6 relative"
              >
                {/* Dot grid background */}
                <div
                  className="absolute inset-0 opacity-[0.03] pointer-events-none"
                  style={{
                    backgroundImage: 'radial-gradient(circle, rgba(255,255,255,0.8) 1px, transparent 1px)',
                    backgroundSize: '24px 24px',
                  }}
                />

                <Motion.div variants={fadeUp} className="flex justify-center relative z-10">
                  <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-primary/20 to-primary-300/20 border border-primary/20 flex items-center justify-center">
                    <PulseIcon className="w-10 h-10 text-primary-400" />
                  </div>
                </Motion.div>

                <Motion.h2
                  variants={fadeUp}
                  className="text-4xl sm:text-5xl font-bold mt-6 mb-3 tracking-tight bg-gradient-to-r from-white via-white to-gray-400 bg-clip-text text-transparent relative z-10"
                >
                  AI Trading Analyst
                </Motion.h2>

                <Motion.p variants={fadeUp} className="text-gray-400 text-lg max-w-md mx-auto text-center relative z-10">
                  Multi-agent research platform
                </Motion.p>

                {/* Hero search */}
                <Motion.form
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
                </Motion.form>

                {/* Quick tickers */}
                <Motion.div variants={fadeUp} className="mt-5 flex items-center justify-center flex-wrap gap-2 relative z-10">
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
                </Motion.div>

                {/* Feature cards */}
                <Motion.div
                  variants={containerVariants}
                  className="mt-12 grid grid-cols-1 sm:grid-cols-3 gap-5 max-w-2xl mx-auto relative z-10"
                >
                  <Motion.div variants={fadeUp} className="glass-card-elevated rounded-xl p-5 text-left border-t-2 border-t-accent-blue">
                    <div className="w-9 h-9 rounded-lg bg-accent-blue/15 flex items-center justify-center mb-3">
                      <ChartBarIcon className="w-5 h-5 text-accent-blue" />
                    </div>
                    <div className="font-semibold text-sm mb-1">8 Specialized Agents</div>
                    <div className="text-xs text-gray-400 leading-relaxed">Market, Fundamentals, News, Technical, Macro, Options, Leadership, Sentiment</div>
                  </Motion.div>

                  <Motion.div variants={fadeUp} className="glass-card-elevated rounded-xl p-5 text-left border-t-2 border-t-accent-green">
                    <div className="w-9 h-9 rounded-lg bg-accent-green/15 flex items-center justify-center mb-3">
                      <PulseIcon className="w-5 h-5 text-accent-green" />
                    </div>
                    <div className="font-semibold text-sm mb-1">Real-time Analysis</div>
                    <div className="text-xs text-gray-400 leading-relaxed">Live updates as agents complete their work</div>
                  </Motion.div>

                  <Motion.div variants={fadeUp} className="glass-card-elevated rounded-xl p-5 text-left border-t-2 border-t-accent-purple">
                    <div className="w-9 h-9 rounded-lg bg-accent-purple/15 flex items-center justify-center mb-3">
                      <SparklesIcon className="w-5 h-5 text-accent-purple" />
                    </div>
                    <div className="font-semibold text-sm mb-1">PM Workflow</div>
                    <div className="text-xs text-gray-400 leading-relaxed">Action, risk, and evidence surfaced in one view</div>
                  </Motion.div>
                </Motion.div>
              </Motion.div>
            )}

            {/* Analysis content — narrative scroll */}
            {showAnalysisContent && (
              <>
                <ThesisCard analysis={analysis} />

                <div className="mx-6 mt-4">
                  <PriceChart analysis={analysis} />
                </div>

                <SectionNav />

                {/* Narrative agent sections */}
                <div className="px-6 pt-4 pb-8 flex flex-col" style={{ gap: 'var(--space-section-gap, 32px)' }}>
                  {SECTION_ORDER.map(({ key, name, special }) => {
                    let result;
                    let stance;
                    let summary;
                    let metrics;

                    if (key === 'company_overview') {
                      result = agentResults.fundamentals
                        || (analysis?.analysis?.fundamentals ? { success: true, data: analysis.analysis.fundamentals } : null);
                      stance = getAgentStance('fundamentals', result);
                      summary = null;
                      metrics = [];
                    } else if (key === 'technicals_options') {
                      result = agentResults.technical
                        || (analysis?.analysis?.technical ? { success: true, data: analysis.analysis.technical } : null);
                      stance = getAgentStance('technical', result);
                      summary = null;
                      metrics = [];
                    } else {
                      result = agentResults[key]
                        || (analysis?.analysis?.[key] ? { success: true, data: analysis.analysis[key] } : null);
                      stance = getAgentStance(key, result);
                      summary = getAgentSummary(result);
                      metrics = getAgentMetrics(key, result);
                    }

                    return (
                      <AnalysisSection
                        key={key}
                        id={`section-${key}`}
                        name={name}
                        stance={stance}
                        stanceColor={STANCE_COLORS[stance]}
                        summary={summary}
                        metrics={metrics}
                        fullContent={result?.data?.analysis || result?.data?.full_analysis || null}
                        dataSource={result?.data?.data_source || result?.data_source || null}
                        duration={result?.duration_seconds}
                      >
                        {special ? renderSpecialChildren(special) : null}
                      </AnalysisSection>
                    );
                  })}
                </div>

                <MetaFooter analysis={analysis} />
              </>
            )}
          </>
        )}
      </main>
    </div>
  );
};

export default Dashboard;
