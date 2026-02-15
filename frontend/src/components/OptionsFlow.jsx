/**
 * OptionsFlow - Displays options chain analysis: P/C ratios, unusual activity, max pain
 */

import React from 'react';
import { motion } from 'framer-motion';
import { OptionsIcon, ArrowUpIcon, ArrowDownIcon } from './Icons';

/**
 * Bidirectional bar for P/C ratio visualization.
 * Center = 1.0 (neutral). Left = bullish (green, ratio < 0.7). Right = bearish (red, ratio > 1.2).
 */
const PcRatioBar = ({ ratio }) => {
  if (ratio == null) return null;

  // Determine direction and fill percentage
  // Neutral zone: 0.7 - 1.2
  // Bullish: ratio < 0.7 => bar extends left from center
  // Bearish: ratio > 1.2 => bar extends right from center
  let direction = 'neutral'; // no bar fill
  let fillPercent = 0;

  if (ratio < 0.7) {
    direction = 'bullish';
    // Map 0.7 -> 0% to 0.0 -> 100% (clamped)
    fillPercent = Math.min(((0.7 - ratio) / 0.7) * 100, 100);
  } else if (ratio > 1.2) {
    direction = 'bearish';
    // Map 1.2 -> 0% to 2.0+ -> 100% (clamped)
    fillPercent = Math.min(((ratio - 1.2) / 0.8) * 100, 100);
  }

  return (
    <div className="mt-1.5 relative h-1.5 w-full rounded-full bg-white/5 overflow-hidden">
      {/* Center tick mark */}
      <div className="absolute left-1/2 top-0 bottom-0 w-px bg-white/20 z-10" />

      {/* Bullish fill - extends left from center */}
      {direction === 'bullish' && (
        <motion.div
          className="absolute right-1/2 top-0 bottom-0 rounded-l-full bg-success/60"
          initial={{ width: 0 }}
          animate={{ width: `${fillPercent / 2}%` }}
          transition={{ duration: 0.6, ease: 'easeOut' }}
        />
      )}

      {/* Bearish fill - extends right from center */}
      {direction === 'bearish' && (
        <motion.div
          className="absolute left-1/2 top-0 bottom-0 rounded-r-full bg-danger/60"
          initial={{ width: 0 }}
          animate={{ width: `${fillPercent / 2}%` }}
          transition={{ duration: 0.6, ease: 'easeOut' }}
        />
      )}
    </div>
  );
};

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
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: 'easeOut' }}
      className="space-y-0"
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-4 pb-4 border-b border-white/5">
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
      <div className="grid grid-cols-3 gap-4 mb-5">
        {/* P/C Volume Ratio */}
        <div className="bg-dark-inset rounded-lg p-4 border border-white/5">
          <div className="text-[11px] text-gray-500 uppercase tracking-wider mb-1.5">P/C Vol Ratio</div>
          <div className="text-lg font-bold font-mono tabular-nums">
            {pcRatio != null ? pcRatio.toFixed(2) : 'N/A'}
          </div>
          <div className={`text-[11px] ${pcRatio > 1 ? 'text-danger-400' : pcRatio < 0.7 ? 'text-success-400' : 'text-warning-400'}`}>
            {getPcLabel(pcRatio)}
          </div>
          <PcRatioBar ratio={pcRatio} />
        </div>

        {/* P/C OI Ratio */}
        <div className="bg-dark-inset rounded-lg p-4 border border-white/5">
          <div className="text-[11px] text-gray-500 uppercase tracking-wider mb-1.5">P/C OI Ratio</div>
          <div className="text-lg font-bold font-mono tabular-nums">
            {pcOiRatio != null ? pcOiRatio.toFixed(2) : 'N/A'}
          </div>
          <div className={`text-[11px] ${pcOiRatio > 1 ? 'text-danger-400' : pcOiRatio < 0.7 ? 'text-success-400' : 'text-warning-400'}`}>
            {getPcLabel(pcOiRatio)}
          </div>
          <PcRatioBar ratio={pcOiRatio} />
        </div>

        {/* Max Pain */}
        <div className="bg-dark-inset rounded-lg p-4 border border-white/5">
          <div className="text-[11px] text-gray-500 uppercase tracking-wider mb-1.5">Max Pain</div>
          <div className="text-lg font-bold font-mono tabular-nums">
            {maxPain != null ? `$${maxPain.toFixed(2)}` : 'N/A'}
          </div>
          <div className="text-[11px] text-gray-500 font-mono">
            {optionsData.total_contracts?.toLocaleString()} contracts
          </div>
        </div>
      </div>

      {/* Unusual Activity */}
      {unusualActivity.length > 0 && (
        <div className="mb-4 pt-4 border-t border-white/5">
          <div className="text-[11px] text-gray-500 uppercase tracking-wider mb-2.5">Unusual Activity</div>
          <div className="space-y-2.5">
            {unusualActivity.slice(0, 5).map((item, i) => (
              <div
                key={i}
                className="flex items-center justify-between px-3.5 py-2.5 bg-dark-inset rounded-lg border border-white/5 text-xs"
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
                  <span className="text-gray-300 font-mono">${item.strike}</span>
                  <span className="text-gray-500">{item.expiration}</span>
                </div>
                <div className="flex items-center space-x-4 font-mono tabular-nums">
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
        <div className="pt-4 border-t border-white/5">
          <div className="text-[11px] text-gray-500 uppercase tracking-wider mb-2.5">Highest Implied Volatility</div>
          <div className="flex flex-wrap gap-2.5">
            {highestIv.slice(0, 5).map((c, i) => (
              <div key={i} className="px-3 py-2 bg-dark-inset rounded-md border border-white/5 text-xs">
                <span className={`font-semibold ${c.type === 'call' ? 'text-success-400' : 'text-danger-400'}`}>
                  {c.type?.toUpperCase()}
                </span>
                <span className="text-gray-400 ml-1.5 font-mono">${c.strike}</span>
                <span className="text-accent-purple ml-1.5 font-semibold font-mono">{(c.implied_volatility * 100).toFixed(1)}%</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </motion.div>
  );
};

export default OptionsFlow;
