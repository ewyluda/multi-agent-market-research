/**
 * ContentHeader - Header strip above the tabbed content area
 * Shows ticker info, price, change %, data source badges, search input, and progress bar
 */

import React from 'react';
import { LoadingSpinner, TrendingUpIcon, TrendingDownIcon } from './Icons';

/* ──────────────────────────────────────────────
   Source badge (AV / YF)
   ────────────────────────────────────────────── */

const SourceBadge = ({ source }) => {
  if (!source) return null;
  const isAV = source === 'alpha_vantage';
  return (
    <span
      className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
        isAV
          ? 'bg-accent-blue/10 text-accent-blue/70'
          : 'bg-gray-500/10 text-gray-500'
      }`}
    >
      {isAV ? 'AV' : 'YF'}
    </span>
  );
};

/* ──────────────────────────────────────────────
   Stage text mapping for progress bar
   ────────────────────────────────────────────── */

const getStageText = (stage) => {
  const stages = {
    starting: 'Initializing analysis pipeline...',
    gathering_data: 'Gathering data from multiple sources...',
    running_market: 'Analyzing market data...',
    running_fundamentals: 'Analyzing company fundamentals...',
    running_news: 'Fetching recent news...',
    running_technical: 'Running technical analysis...',
    running_options: 'Analyzing options flow...',
    running_macro: 'Analyzing macroeconomic environment...',
    analyzing_sentiment: 'Analyzing market sentiment...',
    synthesizing: 'AI synthesizing all insights...',
    saving: 'Saving results...',
    complete: 'Analysis complete',
    error: 'Analysis failed',
  };
  return stages[stage] || stage;
};

/* ──────────────────────────────────────────────
   ContentHeader component
   ────────────────────────────────────────────── */

const ContentHeader = ({
  tickerInput,
  setTickerInput,
  onAnalyze,
  loading,
  analysis,
  progress,
  stage,
}) => {
  /* Extract market data from analysis */
  const marketData = analysis?.agent_results?.market?.data || {};
  const currentPrice = marketData.current_price;
  const priceChange = marketData.price_change_1m?.change_pct;
  const isPositive = priceChange > 0;
  const marketSource = analysis?.agent_results?.market?.data?.data_source;
  const technicalSource = analysis?.agent_results?.technical?.data?.data_source;

  const ticker = analysis?.ticker;
  const hasAnalysis = !!analysis;

  return (
    <div className="w-full">
      {/* ── Main header row ── */}
      <div className="flex items-center justify-between gap-4 px-6 py-3">
        {/* Left side: ticker info */}
        {hasAnalysis ? (
          <div className="flex items-center gap-3 min-w-0">
            {/* Ticker symbol */}
            <span className="text-2xl font-bold tracking-tight text-white shrink-0">
              {ticker}
            </span>

            {/* Current price */}
            {currentPrice != null && (
              <span className="text-3xl font-mono tabular-nums font-semibold text-white shrink-0">
                ${currentPrice.toLocaleString(undefined, {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2,
                })}
              </span>
            )}

            {/* Change % badge */}
            {priceChange != null && (
              <span
                className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-sm font-semibold tabular-nums shrink-0 ${
                  isPositive
                    ? 'bg-accent-green/15 text-accent-green'
                    : 'bg-accent-red/15 text-accent-red'
                }`}
              >
                {isPositive ? (
                  <TrendingUpIcon className="w-3.5 h-3.5" />
                ) : (
                  <TrendingDownIcon className="w-3.5 h-3.5" />
                )}
                {isPositive ? '+' : ''}
                {priceChange.toFixed(2)}%
              </span>
            )}

            {/* Data source badges */}
            <div className="flex items-center gap-1 shrink-0">
              <SourceBadge source={marketSource} />
              <SourceBadge source={technicalSource} />
            </div>
          </div>
        ) : (
          /* When no analysis, empty spacer on left */
          <div className="flex-1" />
        )}

        {/* Right side: search + run button */}
        <form onSubmit={onAnalyze} className="flex items-center gap-2 shrink-0">
          <input
            type="text"
            value={tickerInput}
            onChange={(e) => setTickerInput(e.target.value.toUpperCase())}
            placeholder="TICKER"
            className="w-28 px-3 py-1.5 bg-dark-inset border border-dark-border rounded-lg text-sm font-mono uppercase text-white placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-accent-blue/30 focus:border-accent-blue/50 focus:shadow-[0_0_15px_rgba(0,111,238,0.15)] transition-all"
            maxLength={5}
            disabled={loading}
          />
          <button
            type="submit"
            disabled={loading || !tickerInput.trim()}
            className="px-4 py-1.5 bg-gradient-to-r from-primary-600 to-primary hover:from-primary hover:to-primary-400 disabled:from-zinc-700 disabled:to-zinc-700 disabled:cursor-not-allowed rounded-lg font-medium text-sm transition-all flex items-center gap-2 whitespace-nowrap"
          >
            {loading ? (
              <>
                <LoadingSpinner size={14} />
                <span>Analyzing</span>
              </>
            ) : (
              <span>Run Analysis</span>
            )}
          </button>
        </form>
      </div>

      {/* ── Progress bar (shown only when loading) ── */}
      {loading && (
        <div className="px-6 pb-3">
          <div className="flex justify-between items-center mb-1">
            <span className="text-[11px] text-gray-400 font-medium tracking-wide">
              {getStageText(stage)}
            </span>
            <span className="text-[11px] text-accent-blue font-semibold tabular-nums">
              {progress}%
            </span>
          </div>
          <div className="w-full h-1 bg-dark-inset rounded-full overflow-hidden shadow-inner">
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
    </div>
  );
};

export default ContentHeader;
