/**
 * PriceChart - TradingView interactive chart with metric cards and technical indicators
 */

import React, { useMemo } from 'react';
import { AdvancedRealTimeChart } from 'react-ts-tradingview-widgets';
import { TrendingUpIcon, TrendingDownIcon } from './Icons';

const PriceChart = ({ analysis }) => {
  if (!analysis) {
    return (
      <div className="glass-card-elevated rounded-xl p-6 h-80">
        <div className="skeleton h-4 w-32 mb-6" />
        <div className="skeleton h-44 w-full mb-4 rounded-lg" />
        <div className="grid grid-cols-4 gap-3">
          <div className="skeleton h-14 rounded-lg" />
          <div className="skeleton h-14 rounded-lg" />
          <div className="skeleton h-14 rounded-lg" />
          <div className="skeleton h-14 rounded-lg" />
        </div>
      </div>
    );
  }

  const marketData = analysis.agent_results?.market?.data || {};
  const technicalData = analysis.agent_results?.technical?.data || {};
  const marketSource = analysis.agent_results?.market?.data?.data_source;
  const technicalSource = analysis.agent_results?.technical?.data?.data_source;

  const priceChange = marketData.price_change_1m?.change_pct;
  const isPositive = priceChange > 0;

  // TradingView symbol — bare ticker works for US equities
  const tvSymbol = analysis.ticker || 'AAPL';

  // Data source badge helper
  const SourceBadge = ({ source }) => {
    if (!source) return null;
    const isAV = source === 'alpha_vantage';
    return (
      <span className={`text-[9px] px-1.5 py-0.5 rounded font-medium ml-2 ${
        isAV ? 'bg-accent-blue/10 text-accent-blue/70' : 'bg-gray-500/10 text-gray-500'
      }`}>
        {isAV ? 'AV' : 'YF'}
      </span>
    );
  };

  return (
    <div className="glass-card-elevated rounded-xl p-5">
      {/* Header */}
      <div className="flex justify-between items-center mb-4">
        <div>
          <div className="flex items-center">
            <h3 className="text-lg font-bold tracking-tight">
              {analysis.ticker || 'Chart'}
            </h3>
            <SourceBadge source={marketSource} />
          </div>
          {marketData.current_price && (
            <div className="flex items-center space-x-2 mt-0.5">
              <span className="text-2xl font-bold tabular-nums">${marketData.current_price.toFixed(2)}</span>
              {priceChange !== undefined && (
                <span className={`flex items-center text-sm font-semibold ${isPositive ? 'text-success-400' : 'text-danger-400'}`}>
                  {isPositive ? <TrendingUpIcon className="w-4 h-4 mr-0.5" /> : <TrendingDownIcon className="w-4 h-4 mr-0.5" />}
                  {isPositive ? '+' : ''}{priceChange?.toFixed(2)}%
                </span>
              )}
            </div>
          )}
        </div>
      </div>

      {/* TradingView Chart */}
      <div className="h-[400px] mt-2 mb-4 rounded-lg overflow-hidden border border-dark-border">
        <AdvancedRealTimeChart
          symbol={tvSymbol}
          theme="dark"
          autosize
          interval="D"
          timezone="America/New_York"
          style="1"
          locale="en"
          enable_publishing={false}
          hide_legend={false}
          save_image={false}
          allow_symbol_change={false}
          container_id={`tradingview_${tvSymbol}`}
        />
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-4 gap-3">
        {marketData.current_price && (
          <div className="p-3 bg-dark-inset rounded-lg border-l-2 border-l-accent-blue">
            <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Price</div>
            <div className="text-sm font-bold tabular-nums">${marketData.current_price.toFixed(2)}</div>
          </div>
        )}
        <div className="p-3 bg-dark-inset rounded-lg border-l-2" style={{ borderLeftColor: isPositive ? '#17c964' : '#f31260' }}>
          <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">1M Change</div>
          <div className={`text-sm font-bold tabular-nums ${isPositive ? 'text-success-400' : 'text-danger-400'}`}>
            {priceChange !== undefined ? `${isPositive ? '+' : ''}${priceChange?.toFixed(2)}%` : 'N/A'}
          </div>
        </div>
        <div className="p-3 bg-dark-inset rounded-lg border-l-2 border-l-accent-purple">
          <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Volume</div>
          <div className="text-sm font-bold tabular-nums">
            {marketData.volume ? (marketData.volume / 1000000).toFixed(1) + 'M' : 'N/A'}
          </div>
        </div>
        <div className="p-3 bg-dark-inset rounded-lg border-l-2 border-l-accent-amber">
          <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Trend</div>
          <div className="text-sm font-bold capitalize">
            {marketData.trend?.replace('_', ' ') || 'N/A'}
          </div>
        </div>
      </div>

      {/* Technical Indicators */}
      {technicalData.indicators && (
        <div className="mt-4 grid grid-cols-3 gap-3">
          {technicalData.indicators.rsi && (
            <div className="p-3 bg-dark-inset rounded-lg">
              <div className="flex justify-between items-center mb-1">
                <span className="text-[10px] text-gray-500 uppercase tracking-wider">RSI</span>
                <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
                  technicalData.indicators.rsi.value > 70 ? 'bg-danger/15 text-danger-400' :
                  technicalData.indicators.rsi.value < 30 ? 'bg-success/15 text-success-400' :
                  'bg-gray-500/15 text-gray-400'
                }`}>
                  {technicalData.indicators.rsi.interpretation}
                </span>
              </div>
              <div className="text-lg font-bold tabular-nums">
                {technicalData.indicators.rsi.value?.toFixed(1) || 'N/A'}
              </div>
            </div>
          )}
          {technicalData.indicators.macd && (
            <div className="p-3 bg-dark-inset rounded-lg">
              <div className="flex justify-between items-center mb-1">
                <span className="text-[10px] text-gray-500 uppercase tracking-wider">MACD</span>
                <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
                  technicalData.indicators.macd.interpretation?.includes('bullish')
                    ? 'bg-success/15 text-success-400'
                    : 'bg-danger/15 text-danger-400'
                }`}>
                  {technicalData.indicators.macd.interpretation || 'N/A'}
                </span>
              </div>
              <div className="text-lg font-bold tabular-nums capitalize">
                {technicalData.indicators.macd.value?.toFixed(2) || 'N/A'}
              </div>
            </div>
          )}
          {technicalData.signals && (
            <div className="p-3 bg-dark-inset rounded-lg">
              <div className="flex justify-between items-center mb-1">
                <span className="text-[10px] text-gray-500 uppercase tracking-wider">Signal</span>
                <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
                  technicalData.signals.overall === 'bullish' ? 'bg-success/15 text-success-400' :
                  technicalData.signals.overall === 'bearish' ? 'bg-danger/15 text-danger-400' :
                  'bg-warning/15 text-warning-400'
                }`}>
                  {technicalData.signals.overall}
                </span>
              </div>
              <div className="text-lg font-bold tabular-nums">
                {((technicalData.signals.strength || 0) * 100).toFixed(0)}%
              </div>
              <div className="mt-1 h-1 bg-gray-700 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${
                    technicalData.signals.overall === 'bullish' ? 'bg-success' :
                    technicalData.signals.overall === 'bearish' ? 'bg-danger' :
                    'bg-warning'
                  }`}
                  style={{ width: `${(technicalData.signals.strength || 0) * 100}%` }}
                />
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default PriceChart;
