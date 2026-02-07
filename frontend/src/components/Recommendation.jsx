/**
 * Recommendation - BUY/HOLD/SELL gauge with score and confidence
 */

import React from 'react';

const Recommendation = ({ analysis }) => {
  if (!analysis) {
    return (
      <div className="glass-card-elevated rounded-xl p-6">
        <div className="skeleton h-4 w-36 mb-6" />
        <div className="skeleton h-32 w-48 mx-auto rounded-lg mb-4" />
        <div className="skeleton h-8 w-24 mx-auto mb-2" />
        <div className="skeleton h-4 w-32 mx-auto" />
      </div>
    );
  }

  const { recommendation, score, confidence } = analysis.analysis || {};

  // Needle rotation: -90 for strong SELL, 0 for HOLD, +90 for strong BUY
  const rotation = (score / 100) * 90;

  const getColor = () => {
    if (recommendation === 'BUY') return { text: 'text-emerald-400', bg: 'bg-emerald-500', border: 'border-t-emerald-500', glow: '0 0 20px rgba(16, 185, 129, 0.2)' };
    if (recommendation === 'SELL') return { text: 'text-red-400', bg: 'bg-red-500', border: 'border-t-red-500', glow: '0 0 20px rgba(239, 68, 68, 0.2)' };
    return { text: 'text-amber-400', bg: 'bg-amber-500', border: 'border-t-amber-500', glow: '0 0 20px rgba(245, 158, 11, 0.2)' };
  };

  const colors = getColor();

  return (
    <div
      className={`glass-card-elevated rounded-xl p-6 border-t-2 ${colors.border}`}
      style={{ boxShadow: colors.glow }}
    >
      <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider mb-5">Recommendation</h3>

      {/* Gauge */}
      <div className="relative w-56 h-28 mx-auto mb-5">
        <svg className="w-full h-full" viewBox="0 0 200 100">
          <defs>
            <linearGradient id="sellGradient" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#991b1b" />
              <stop offset="100%" stopColor="#ef4444" />
            </linearGradient>
            <linearGradient id="holdGradient" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#92400e" />
              <stop offset="100%" stopColor="#f59e0b" />
            </linearGradient>
            <linearGradient id="buyGradient" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#10b981" />
              <stop offset="100%" stopColor="#065f46" />
            </linearGradient>
            <filter id="needleShadow">
              <feDropShadow dx="0" dy="1" stdDeviation="2" floodOpacity="0.5" />
            </filter>
          </defs>

          {/* Background track */}
          <path d="M 15 90 A 75 75 0 0 1 185 90" fill="none" stroke="#1f2937" strokeWidth="16" strokeLinecap="round" />

          {/* Colored zones */}
          <path d="M 15 90 A 75 75 0 0 1 60 22" fill="none" stroke="url(#sellGradient)" strokeWidth="16" strokeLinecap="round" opacity="0.6" />
          <path d="M 60 22 A 75 75 0 0 1 140 22" fill="none" stroke="url(#holdGradient)" strokeWidth="16" strokeLinecap="round" opacity="0.6" />
          <path d="M 140 22 A 75 75 0 0 1 185 90" fill="none" stroke="url(#buyGradient)" strokeWidth="16" strokeLinecap="round" opacity="0.6" />

          {/* Tick marks */}
          {[-75, -50, -25, 0, 25, 50, 75].map((deg) => (
            <line
              key={deg}
              x1="100" y1="90" x2="100" y2="24"
              stroke="#374151" strokeWidth="0.5"
              transform={`rotate(${deg} 100 90)`}
            />
          ))}

          {/* Needle */}
          <g transform={`rotate(${rotation} 100 90)`} filter="url(#needleShadow)">
            <line x1="100" y1="90" x2="100" y2="28" stroke="white" strokeWidth="2.5" strokeLinecap="round" />
            <circle cx="100" cy="90" r="5" fill="#1f2937" stroke="white" strokeWidth="2" />
          </g>

          {/* Labels */}
          <text x="22" y="98" fill="#ef4444" fontSize="10" fontWeight="600" opacity="0.7">SELL</text>
          <text x="86" y="16" fill="#f59e0b" fontSize="10" fontWeight="600" opacity="0.7">HOLD</text>
          <text x="160" y="98" fill="#10b981" fontSize="10" fontWeight="600" opacity="0.7">BUY</text>
        </svg>
      </div>

      {/* Score */}
      <div className="text-center space-y-1.5">
        <div className={`text-4xl font-bold tabular-nums ${colors.text}`}>
          {score > 0 ? '+' : ''}{score}
        </div>
        <div className={`text-xl font-bold tracking-wide ${colors.text}`}>
          {recommendation}
        </div>

        {/* Confidence bar */}
        <div className="mt-3">
          <div className="flex justify-between items-center mb-1">
            <span className="text-[10px] text-gray-500 uppercase tracking-wider">Confidence</span>
            <span className="text-xs font-semibold tabular-nums">{(confidence * 100).toFixed(0)}%</span>
          </div>
          <div className="h-1.5 bg-dark-inset rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full ${colors.bg} transition-all duration-500`}
              style={{ width: `${confidence * 100}%`, opacity: 0.7 }}
            />
          </div>
        </div>
      </div>

      {/* Additional info */}
      {analysis.analysis?.position_size && (
        <div className="mt-5 pt-4 border-t border-white/5 space-y-2.5">
          <div className="flex justify-between items-center">
            <span className="text-xs text-gray-500">Position Size</span>
            <span className={`text-xs font-semibold px-2 py-0.5 rounded ${
              analysis.analysis.position_size === 'LARGE' ? 'bg-emerald-500/15 text-emerald-400' :
              analysis.analysis.position_size === 'MEDIUM' ? 'bg-blue-500/15 text-blue-400' :
              'bg-gray-500/15 text-gray-400'
            }`}>
              {analysis.analysis.position_size}
            </span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-xs text-gray-500">Time Horizon</span>
            <span className="text-xs font-semibold px-2 py-0.5 rounded bg-accent-purple/15 text-accent-purple">
              {analysis.analysis.time_horizon?.replace(/_/g, ' ')}
            </span>
          </div>
        </div>
      )}
    </div>
  );
};

export default Recommendation;
