/**
 * PriceChart - Placeholder for price chart (can be enhanced with Chart.js later)
 */

import React from 'react';

const PriceChart = ({ analysis }) => {
  if (!analysis) {
    return (
      <div className="bg-dark-card border border-dark-border rounded-lg p-6 h-64 flex items-center justify-center">
        <div className="text-gray-500">No chart data available</div>
      </div>
    );
  }

  const marketData = analysis.agent_results?.market?.data || {};
  const technicalData = analysis.agent_results?.technical?.data || {};

  return (
    <div className="bg-dark-card border border-dark-border rounded-lg p-6">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-semibold">
          {analysis.ticker || 'Chart'}
        </h3>
        <div className="flex space-x-2 text-sm">
          <button className="px-3 py-1 bg-dark-bg rounded hover:bg-gray-700">1D</button>
          <button className="px-3 py-1 bg-dark-bg rounded hover:bg-gray-700">1W</button>
          <button className="px-3 py-1 bg-accent-blue text-white rounded">1M</button>
          <button className="px-3 py-1 bg-dark-bg rounded hover:bg-gray-700">3M</button>
          <button className="px-3 py-1 bg-dark-bg rounded hover:bg-gray-700">1Y</button>
        </div>
      </div>

      {/* Price Info */}
      {marketData.current_price && (
        <div className="grid grid-cols-4 gap-4 mb-6">
          <div className="p-3 bg-dark-bg rounded-md">
            <div className="text-xs text-gray-400 mb-1">Current Price</div>
            <div className="text-2xl font-bold">${marketData.current_price.toFixed(2)}</div>
          </div>
          <div className="p-3 bg-dark-bg rounded-md">
            <div className="text-xs text-gray-400 mb-1">1M Change</div>
            <div className={`text-xl font-bold ${
              marketData.price_change_1m?.change_pct > 0 ? 'text-green-500' : 'text-red-500'
            }`}>
              {marketData.price_change_1m?.change_pct > 0 ? '+' : ''}
              {marketData.price_change_1m?.change_pct?.toFixed(2)}%
            </div>
          </div>
          <div className="p-3 bg-dark-bg rounded-md">
            <div className="text-xs text-gray-400 mb-1">Volume</div>
            <div className="text-lg font-bold">
              {marketData.volume ? (marketData.volume / 1000000).toFixed(1) + 'M' : 'N/A'}
            </div>
          </div>
          <div className="p-3 bg-dark-bg rounded-md">
            <div className="text-xs text-gray-400 mb-1">Trend</div>
            <div className="text-lg font-bold capitalize">
              {marketData.trend?.replace('_', ' ') || 'N/A'}
            </div>
          </div>
        </div>
      )}

      {/* Chart Placeholder */}
      <div className="h-64 bg-dark-bg rounded-md flex items-center justify-center">
        <div className="text-center text-gray-500">
          <div className="text-6xl mb-4">📈</div>
          <div>Chart visualization coming soon</div>
          <div className="text-sm mt-2">
            Will display candlestick chart with technical indicators
          </div>
        </div>
      </div>

      {/* Technical Indicators Summary */}
      {technicalData.indicators && (
        <div className="mt-6 grid grid-cols-3 gap-4">
          {technicalData.indicators.rsi && (
            <div className="p-3 bg-dark-bg rounded-md">
              <div className="text-xs text-gray-400 mb-1">RSI</div>
              <div className="text-lg font-bold">
                {technicalData.indicators.rsi.value?.toFixed(1) || 'N/A'}
              </div>
              <div className="text-xs text-gray-400">
                {technicalData.indicators.rsi.interpretation}
              </div>
            </div>
          )}
          {technicalData.indicators.macd && (
            <div className="p-3 bg-dark-bg rounded-md">
              <div className="text-xs text-gray-400 mb-1">MACD</div>
              <div className="text-lg font-bold capitalize">
                {technicalData.indicators.macd.interpretation || 'N/A'}
              </div>
            </div>
          )}
          {technicalData.signals && (
            <div className="p-3 bg-dark-bg rounded-md">
              <div className="text-xs text-gray-400 mb-1">Technical Signal</div>
              <div className="text-lg font-bold uppercase">
                {technicalData.signals.overall || 'N/A'}
              </div>
              <div className="text-xs text-gray-400">
                Strength: {technicalData.signals.strength || 0}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default PriceChart;
