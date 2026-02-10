/**
 * Recommendation - BUY/HOLD/SELL gauge with score, confidence, and agent consensus
 */

import React from 'react';
import { BuildingIcon, ChartBarIcon, BrainIcon, ChartLineIcon, GlobeIcon } from './Icons';

/**
 * AgentConsensus — shows per-agent signal direction as colored dots.
 */
const AgentConsensus = ({ agentResults }) => {
  const getSignal = (agentName) => {
    const data = agentResults?.[agentName]?.data;
    if (!data) return null;

    switch (agentName) {
      case 'fundamentals': {
        const health = data.health_score;
        if (health == null) return null;
        if (health > 60) return 'bullish';
        if (health < 40) return 'bearish';
        return 'neutral';
      }
      case 'technical': {
        return data.signals?.overall || null;
      }
      case 'sentiment': {
        const score = data.overall_sentiment;
        if (score == null) return null;
        if (score > 0.3) return 'bullish';
        if (score < -0.3) return 'bearish';
        return 'neutral';
      }
      case 'market': {
        const trend = data.trend;
        if (!trend) return null;
        if (trend.includes('up') || trend.includes('bullish')) return 'bullish';
        if (trend.includes('down') || trend.includes('bearish')) return 'bearish';
        return 'neutral';
      }
      case 'macro': {
        const risk = data.risk_environment;
        if (risk === 'dovish') return 'bullish';
        if (risk === 'hawkish') return 'bearish';
        return 'neutral';
      }
      default:
        return null;
    }
  };

  const agents = [
    { id: 'fundamentals', label: 'Fund', icon: BuildingIcon },
    { id: 'technical', label: 'Tech', icon: ChartLineIcon },
    { id: 'sentiment', label: 'Sent', icon: BrainIcon },
    { id: 'market', label: 'Mkt', icon: ChartBarIcon },
    { id: 'macro', label: 'Macro', icon: GlobeIcon },
  ];

  const signals = agents.map(a => ({ ...a, signal: getSignal(a.id) })).filter(a => a.signal);
  if (signals.length === 0) return null;

  const signalColor = (signal) => {
    if (signal === 'bullish') return 'bg-success border-success/40';
    if (signal === 'bearish') return 'bg-danger border-danger/40';
    return 'bg-warning border-warning/40';
  };

  return (
    <div className="mt-5 pt-4 border-t border-white/5">
      <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-2.5">Agent Signals</div>
      <div className="flex justify-between">
        {signals.map(({ id, label, icon: Icon, signal }) => (
          <div key={id} className="flex flex-col items-center space-y-1">
            <div className={`w-3 h-3 rounded-full border ${signalColor(signal)}`} style={{ opacity: 0.8 }} />
            <span className="text-[9px] text-gray-500">{label}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

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
    if (recommendation === 'BUY') return { text: 'text-success-400', bg: 'bg-success', border: 'border-t-success', glow: '0 0 20px rgba(23, 201, 100, 0.2)' };
    if (recommendation === 'SELL') return { text: 'text-danger-400', bg: 'bg-danger', border: 'border-t-danger', glow: '0 0 20px rgba(243, 18, 96, 0.2)' };
    return { text: 'text-warning-400', bg: 'bg-warning', border: 'border-t-warning', glow: '0 0 20px rgba(245, 165, 36, 0.2)' };
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
              <stop offset="0%" stopColor="#860825" />
              <stop offset="100%" stopColor="#f31260" />
            </linearGradient>
            <linearGradient id="holdGradient" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#6b3a07" />
              <stop offset="100%" stopColor="#f5a524" />
            </linearGradient>
            <linearGradient id="buyGradient" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#17c964" />
              <stop offset="100%" stopColor="#095c30" />
            </linearGradient>
            <filter id="needleShadow">
              <feDropShadow dx="0" dy="1" stdDeviation="2" floodOpacity="0.5" />
            </filter>
          </defs>

          {/* Background track */}
          <path d="M 15 90 A 75 75 0 0 1 185 90" fill="none" stroke="#27272a" strokeWidth="16" strokeLinecap="round" />

          {/* Colored zones */}
          <path d="M 15 90 A 75 75 0 0 1 60 22" fill="none" stroke="url(#sellGradient)" strokeWidth="16" strokeLinecap="round" opacity="0.6" />
          <path d="M 60 22 A 75 75 0 0 1 140 22" fill="none" stroke="url(#holdGradient)" strokeWidth="16" strokeLinecap="round" opacity="0.6" />
          <path d="M 140 22 A 75 75 0 0 1 185 90" fill="none" stroke="url(#buyGradient)" strokeWidth="16" strokeLinecap="round" opacity="0.6" />

          {/* Tick marks */}
          {[-75, -50, -25, 0, 25, 50, 75].map((deg) => (
            <line
              key={deg}
              x1="100" y1="90" x2="100" y2="24"
              stroke="#3f3f46" strokeWidth="0.5"
              transform={`rotate(${deg} 100 90)`}
            />
          ))}

          {/* Needle */}
          <g transform={`rotate(${rotation} 100 90)`} filter="url(#needleShadow)">
            <line x1="100" y1="90" x2="100" y2="28" stroke="white" strokeWidth="2.5" strokeLinecap="round" />
            <circle cx="100" cy="90" r="5" fill="#27272a" stroke="white" strokeWidth="2" />
          </g>

          {/* Labels */}
          <text x="22" y="98" fill="#f31260" fontSize="10" fontWeight="600" opacity="0.7">SELL</text>
          <text x="86" y="16" fill="#f5a524" fontSize="10" fontWeight="600" opacity="0.7">HOLD</text>
          <text x="160" y="98" fill="#17c964" fontSize="10" fontWeight="600" opacity="0.7">BUY</text>
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
              analysis.analysis.position_size === 'LARGE' ? 'bg-success/15 text-success-400' :
              analysis.analysis.position_size === 'MEDIUM' ? 'bg-primary/15 text-primary-400' :
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

      {/* Agent Consensus */}
      {analysis.agent_results && (
        <AgentConsensus agentResults={analysis.agent_results} />
      )}
    </div>
  );
};

export default Recommendation;
