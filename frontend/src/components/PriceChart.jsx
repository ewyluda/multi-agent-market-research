/**
 * PriceChart - Price visualization with recharts and technical indicators
 */

import React from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, ResponsiveContainer } from 'recharts';
import { TrendingUpIcon, TrendingDownIcon } from './Icons';

const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    return (
      <div className="glass-card-elevated rounded-lg px-3 py-2 text-xs">
        <div className="text-gray-400 mb-1">{label}</div>
        <div className="font-semibold text-white">${payload[0].value?.toFixed(2)}</div>
      </div>
    );
  }
  return null;
};

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

  // Build synthetic price trajectory from available data points
  const chartData = [
    marketData.price_change_3m?.start_price && { name: '3M Ago', price: marketData.price_change_3m.start_price },
    marketData.price_change_1m?.start_price && { name: '1M Ago', price: marketData.price_change_1m.start_price },
    marketData.previous_close && { name: 'Prev Close', price: marketData.previous_close },
    marketData.open && { name: 'Open', price: marketData.open },
    marketData.current_price && { name: 'Current', price: marketData.current_price },
  ].filter(Boolean);

  const hasChart = chartData.length >= 2;
  const priceChange = marketData.price_change_1m?.change_pct;
  const isPositive = priceChange > 0;

  return (
    <div className="glass-card-elevated rounded-xl p-5">
      {/* Header */}
      <div className="flex justify-between items-center mb-4">
        <div>
          <h3 className="text-lg font-bold tracking-tight">
            {analysis.ticker || 'Chart'}
          </h3>
          {marketData.current_price && (
            <div className="flex items-center space-x-2 mt-0.5">
              <span className="text-2xl font-bold tabular-nums">${marketData.current_price.toFixed(2)}</span>
              {priceChange !== undefined && (
                <span className={`flex items-center text-sm font-semibold ${isPositive ? 'text-emerald-400' : 'text-red-400'}`}>
                  {isPositive ? <TrendingUpIcon className="w-4 h-4 mr-0.5" /> : <TrendingDownIcon className="w-4 h-4 mr-0.5" />}
                  {isPositive ? '+' : ''}{priceChange?.toFixed(2)}%
                </span>
              )}
            </div>
          )}
        </div>
        <div className="flex space-x-1 text-xs">
          {['1D', '1W', '1M', '3M', '1Y'].map((period) => (
            <button
              key={period}
              className={`px-2.5 py-1 rounded-md transition-all ${
                period === '1M'
                  ? 'bg-accent-blue/15 text-accent-blue border border-accent-blue/30'
                  : 'text-gray-500 hover:text-gray-300 hover:bg-white/5'
              }`}
            >
              {period}
            </button>
          ))}
        </div>
      </div>

      {/* Chart */}
      {hasChart ? (
        <div className="h-48 mt-2 mb-4">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="priceGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={isPositive ? '#10b981' : '#ef4444'} stopOpacity={0.3} />
                  <stop offset="100%" stopColor={isPositive ? '#10b981' : '#ef4444'} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="#1f2937" strokeDasharray="3 3" vertical={false} />
              <XAxis
                dataKey="name"
                tick={{ fill: '#64748b', fontSize: 10 }}
                axisLine={{ stroke: '#1f2937' }}
                tickLine={false}
              />
              <YAxis
                tick={{ fill: '#64748b', fontSize: 10 }}
                axisLine={false}
                tickLine={false}
                domain={['auto', 'auto']}
                tickFormatter={(val) => `$${val.toFixed(0)}`}
              />
              <Tooltip content={<CustomTooltip />} />
              {marketData.support_level && (
                <ReferenceLine
                  y={marketData.support_level}
                  stroke="#10b981"
                  strokeDasharray="4 4"
                  strokeOpacity={0.5}
                />
              )}
              {marketData.resistance_level && (
                <ReferenceLine
                  y={marketData.resistance_level}
                  stroke="#ef4444"
                  strokeDasharray="4 4"
                  strokeOpacity={0.5}
                />
              )}
              <Area
                type="monotone"
                dataKey="price"
                stroke={isPositive ? '#10b981' : '#ef4444'}
                strokeWidth={2}
                fill="url(#priceGradient)"
                dot={{ r: 3, fill: isPositive ? '#10b981' : '#ef4444', strokeWidth: 0 }}
                activeDot={{ r: 5, fill: isPositive ? '#10b981' : '#ef4444', stroke: '#fff', strokeWidth: 1 }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div className="h-48 bg-dark-inset rounded-lg flex items-center justify-center mb-4">
          <span className="text-xs text-gray-500">Insufficient data for chart</span>
        </div>
      )}

      {/* Metric Cards */}
      <div className="grid grid-cols-4 gap-3">
        {marketData.current_price && (
          <div className="p-3 bg-dark-inset rounded-lg border-l-2 border-l-accent-blue">
            <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Price</div>
            <div className="text-sm font-bold tabular-nums">${marketData.current_price.toFixed(2)}</div>
          </div>
        )}
        <div className="p-3 bg-dark-inset rounded-lg border-l-2" style={{ borderLeftColor: isPositive ? '#10b981' : '#ef4444' }}>
          <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">1M Change</div>
          <div className={`text-sm font-bold tabular-nums ${isPositive ? 'text-emerald-400' : 'text-red-400'}`}>
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
                  technicalData.indicators.rsi.value > 70 ? 'bg-red-500/15 text-red-400' :
                  technicalData.indicators.rsi.value < 30 ? 'bg-emerald-500/15 text-emerald-400' :
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
                    ? 'bg-emerald-500/15 text-emerald-400'
                    : 'bg-red-500/15 text-red-400'
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
                  technicalData.signals.overall === 'bullish' ? 'bg-emerald-500/15 text-emerald-400' :
                  technicalData.signals.overall === 'bearish' ? 'bg-red-500/15 text-red-400' :
                  'bg-amber-500/15 text-amber-400'
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
                    technicalData.signals.overall === 'bullish' ? 'bg-emerald-500' :
                    technicalData.signals.overall === 'bearish' ? 'bg-red-500' :
                    'bg-amber-500'
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
