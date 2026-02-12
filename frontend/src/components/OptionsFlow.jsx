/**
 * OptionsFlow - Displays options chain analysis: P/C ratios, unusual activity, max pain
 */

import React from 'react';
import { OptionsIcon, ArrowUpIcon, ArrowDownIcon } from './Icons';

const OptionsFlow = ({ analysis }) => {
  const optionsData = analysis?.agent_results?.options?.data;

  if (!optionsData || optionsData.total_contracts === 0) return null;

  const pcRatio = optionsData.put_call_ratio;
  const pcOiRatio = optionsData.put_call_oi_ratio;
  const maxPain = optionsData.max_pain;
  const signal = optionsData.overall_signal || 'neutral';
  const unusualActivity = optionsData.unusual_activity || [];
  const highestIv = optionsData.highest_iv_contracts || [];
  const source = optionsData.data_source || 'unknown';

  const signalColors = {
    bullish: { text: 'text-success-400', bg: 'bg-success/15', border: 'border-success/30' },
    bearish: { text: 'text-danger-400', bg: 'bg-danger/15', border: 'border-danger/30' },
    neutral: { text: 'text-warning-400', bg: 'bg-warning/15', border: 'border-warning/30' },
  };

  const colors = signalColors[signal] || signalColors.neutral;

  const getPcLabel = (ratio) => {
    if (ratio == null) return 'N/A';
    if (ratio > 1.5) return 'Very Bearish';
    if (ratio > 1.2) return 'Bearish';
    if (ratio < 0.5) return 'Very Bullish';
    if (ratio < 0.7) return 'Bullish';
    return 'Neutral';
  };

  return (
    <div className="glass-card rounded-xl p-5">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-2">
          <div className="w-7 h-7 rounded-lg bg-accent-purple/15 flex items-center justify-center">
            <OptionsIcon className="w-4 h-4 text-accent-purple" />
          </div>
          <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">Options Flow</h3>
        </div>
        <div className="flex items-center space-x-2">
          <span className={`text-xs font-semibold px-2 py-0.5 rounded ${colors.bg} ${colors.text} ${colors.border} border`}>
            {signal.toUpperCase()}
          </span>
          <span className="text-[10px] text-gray-600 font-mono uppercase">{source === 'alpha_vantage' ? 'AV' : source === 'yfinance' ? 'YF' : source}</span>
        </div>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-3 gap-3 mb-4">
        {/* P/C Volume Ratio */}
        <div className="bg-dark-inset rounded-lg p-3 border border-white/5">
          <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">P/C Vol Ratio</div>
          <div className="text-lg font-bold tabular-nums">
            {pcRatio != null ? pcRatio.toFixed(2) : 'N/A'}
          </div>
          <div className={`text-[10px] ${pcRatio > 1 ? 'text-danger-400' : pcRatio < 0.7 ? 'text-success-400' : 'text-warning-400'}`}>
            {getPcLabel(pcRatio)}
          </div>
        </div>

        {/* P/C OI Ratio */}
        <div className="bg-dark-inset rounded-lg p-3 border border-white/5">
          <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">P/C OI Ratio</div>
          <div className="text-lg font-bold tabular-nums">
            {pcOiRatio != null ? pcOiRatio.toFixed(2) : 'N/A'}
          </div>
          <div className={`text-[10px] ${pcOiRatio > 1 ? 'text-danger-400' : pcOiRatio < 0.7 ? 'text-success-400' : 'text-warning-400'}`}>
            {getPcLabel(pcOiRatio)}
          </div>
        </div>

        {/* Max Pain */}
        <div className="bg-dark-inset rounded-lg p-3 border border-white/5">
          <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Max Pain</div>
          <div className="text-lg font-bold tabular-nums">
            {maxPain != null ? `$${maxPain.toFixed(2)}` : 'N/A'}
          </div>
          <div className="text-[10px] text-gray-500">
            {optionsData.total_contracts} contracts
          </div>
        </div>
      </div>

      {/* Unusual Activity */}
      {unusualActivity.length > 0 && (
        <div className="mb-4">
          <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Unusual Activity</div>
          <div className="space-y-1.5">
            {unusualActivity.slice(0, 5).map((item, i) => (
              <div
                key={i}
                className="flex items-center justify-between px-3 py-2 bg-dark-inset rounded-lg border border-white/5 text-xs"
              >
                <div className="flex items-center space-x-2">
                  {item.type === 'call' ? (
                    <ArrowUpIcon className="w-3.5 h-3.5 text-success-400" />
                  ) : (
                    <ArrowDownIcon className="w-3.5 h-3.5 text-danger-400" />
                  )}
                  <span className={`font-semibold ${item.type === 'call' ? 'text-success-400' : 'text-danger-400'}`}>
                    {item.type.toUpperCase()}
                  </span>
                  <span className="text-gray-300">${item.strike}</span>
                  <span className="text-gray-500">{item.expiration}</span>
                </div>
                <div className="flex items-center space-x-3 tabular-nums">
                  <span className="text-gray-400">Vol: {item.volume.toLocaleString()}</span>
                  <span className="text-gray-500">OI: {item.open_interest.toLocaleString()}</span>
                  <span className="text-warning-400 font-semibold">{item.vol_oi_ratio}x</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* High IV Contracts */}
      {highestIv.length > 0 && (
        <div>
          <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Highest Implied Volatility</div>
          <div className="flex flex-wrap gap-2">
            {highestIv.slice(0, 5).map((c, i) => (
              <div key={i} className="px-2.5 py-1.5 bg-dark-inset rounded-md border border-white/5 text-[11px]">
                <span className={`font-semibold ${c.type === 'call' ? 'text-success-400' : 'text-danger-400'}`}>
                  {c.type?.toUpperCase()}
                </span>
                <span className="text-gray-400 ml-1.5">${c.strike}</span>
                <span className="text-accent-purple ml-1.5 font-semibold">{(c.implied_volatility * 100).toFixed(1)}%</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default OptionsFlow;
