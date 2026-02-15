/**
 * Recommendation - BUY/HOLD/SELL gauge with score, confidence, and agent consensus
 */

import React from 'react';
import { motion } from 'framer-motion';
import {
  BuildingIcon,
  ChartBarIcon,
  BrainIcon,
  ChartLineIcon,
  GlobeIcon,
  OptionsIcon,
  NewspaperIcon,
} from './Icons';

/**
 * AgentConsensus — shows per-agent signal direction as labeled signal bars.
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
      case 'options': {
        const optSignal = data.overall_signal;
        if (!optSignal) return null;
        return optSignal;
      }
      case 'news': {
        const articles = data.articles;
        if (!articles || articles.length === 0) return null;
        const avgSentiment = articles.reduce((sum, a) => {
          const s = a.overall_sentiment_score ?? a.sentiment_score ?? 0;
          return sum + s;
        }, 0) / articles.length;
        if (avgSentiment > 0.15) return 'bullish';
        if (avgSentiment < -0.15) return 'bearish';
        return 'neutral';
      }
      default:
        return null;
    }
  };

  const signalMap = [
    { id: 'market', label: 'Market', icon: ChartBarIcon },
    { id: 'fundamentals', label: 'Fund', icon: BuildingIcon },
    { id: 'technical', label: 'Tech', icon: ChartLineIcon },
    { id: 'sentiment', label: 'Sent', icon: BrainIcon },
    { id: 'news', label: 'News', icon: NewspaperIcon },
    { id: 'options', label: 'Opts', icon: OptionsIcon },
    { id: 'macro', label: 'Macro', icon: GlobeIcon },
  ];

  const signals = signalMap
    .map((a) => ({ ...a, signal: getSignal(a.id) }))
    .filter((a) => a.signal);

  if (signals.length === 0) return null;

  const signalStyle = (signal) => {
    if (signal === 'bullish')
      return { bg: 'bg-success/10', border: 'border-success/20', text: 'text-success', label: 'BULL' };
    if (signal === 'bearish')
      return { bg: 'bg-danger/10', border: 'border-danger/20', text: 'text-danger', label: 'BEAR' };
    return { bg: 'bg-warning/10', border: 'border-warning/20', text: 'text-warning', label: 'NEUT' };
  };

  return (
    <div className="mt-4 pt-3 border-t border-white/5">
      <div className="text-[11px] text-gray-500 uppercase tracking-wider mb-2">
        Agent Signals
      </div>
      <div className="space-y-1">
        {signals.map(({ id, label, icon: Icon, signal }) => {
          const style = signalStyle(signal);
          return (
            <div
              key={id}
              className={`flex items-center justify-between px-2.5 py-1.5 rounded border ${style.bg} ${style.border}`}
            >
              <div className="flex items-center gap-1.5">
                <Icon className={`w-3 h-3 ${style.text}`} />
                <span className="text-[11px] text-gray-300 leading-tight">{label}</span>
              </div>
              <span className={`text-[11px] font-mono font-semibold ${style.text}`}>
                {style.label}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
};

const Recommendation = ({ analysis }) => {
  if (!analysis) {
    return (
      <div className="glass-card-elevated rounded-xl p-6">
        <div className="skeleton h-4 w-36 mb-6" />
        <div className="skeleton h-32 w-full mx-auto rounded-lg mb-4" />
        <div className="skeleton h-8 w-24 mx-auto mb-2" />
        <div className="skeleton h-4 w-32 mx-auto" />
      </div>
    );
  }

  const { recommendation, score, confidence } = analysis.analysis || {};

  // Needle rotation: -90 for strong SELL, 0 for HOLD, +90 for strong BUY
  const needleAngle = (score / 100) * 90;

  const centerX = 120;
  const centerY = 115;

  const getColor = () => {
    if (recommendation === 'BUY')
      return {
        text: 'text-success-400',
        bg: 'bg-success',
        raw: '#17c964',
        glow: '0 0 20px rgba(23, 201, 100, 0.2)',
        barGlow: '0 0 6px rgba(23, 201, 100, 0.4)',
        leftGlow: 'rgba(23, 201, 100, 0.5)',
      };
    if (recommendation === 'SELL')
      return {
        text: 'text-danger-400',
        bg: 'bg-danger',
        raw: '#f31260',
        glow: '0 0 20px rgba(243, 18, 96, 0.2)',
        barGlow: '0 0 6px rgba(243, 18, 96, 0.4)',
        leftGlow: 'rgba(243, 18, 96, 0.5)',
      };
    return {
      text: 'text-warning-400',
      bg: 'bg-warning',
      raw: '#f5a524',
      glow: '0 0 20px rgba(245, 165, 36, 0.2)',
      barGlow: '0 0 6px rgba(245, 165, 36, 0.4)',
      leftGlow: 'rgba(245, 165, 36, 0.5)',
    };
  };

  const colors = getColor();

  return (
    <motion.div
      initial={{ opacity: 0, x: 16 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.4, ease: 'easeOut' }}
      className="glass-card-elevated rounded-xl p-6 relative overflow-hidden"
      style={{ boxShadow: colors.glow }}
    >
      {/* Left glow line */}
      <div
        className="absolute left-0 top-3 bottom-3 w-[2px] rounded-full"
        style={{
          background: colors.leftGlow,
          boxShadow: `0 0 8px ${colors.leftGlow}, 0 0 20px ${colors.leftGlow}`,
        }}
      />
      <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider mb-5">
        Recommendation
      </h3>

      {/* Gauge */}
      <div className="relative w-full mx-auto mb-5">
        <svg className="w-full h-auto" viewBox="0 0 240 135">
          <defs>
            <linearGradient id="sellGradient" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#5c0618" />
              <stop offset="40%" stopColor="#a30d3a" />
              <stop offset="100%" stopColor="#f31260" />
            </linearGradient>
            <linearGradient id="holdGradient" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#8b5a10" />
              <stop offset="50%" stopColor="#d4901a" />
              <stop offset="100%" stopColor="#f5a524" />
            </linearGradient>
            <linearGradient id="buyGradient" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#17c964" />
              <stop offset="60%" stopColor="#10a04f" />
              <stop offset="100%" stopColor="#06753a" />
            </linearGradient>
            <filter id="needleShadow">
              <feDropShadow dx="0" dy="1" stdDeviation="2" floodOpacity="0.5" />
            </filter>
            <filter id="gaugeGlow">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
            <filter id="needleDotGlow">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {/* Background track */}
          <path
            d="M 12 115 A 98 98 0 0 1 228 115"
            fill="none"
            stroke="#27272a"
            strokeWidth="16"
            strokeLinecap="round"
          />

          {/* Colored zones with glow */}
          <g filter="url(#gaugeGlow)">
            <path
              d="M 12 115 A 98 98 0 0 1 66 22"
              fill="none"
              stroke="url(#sellGradient)"
              strokeWidth="16"
              strokeLinecap="round"
              opacity="0.55"
            />
            <path
              d="M 66 22 A 98 98 0 0 1 174 22"
              fill="none"
              stroke="url(#holdGradient)"
              strokeWidth="16"
              strokeLinecap="round"
              opacity="0.55"
            />
            <path
              d="M 174 22 A 98 98 0 0 1 228 115"
              fill="none"
              stroke="url(#buyGradient)"
              strokeWidth="16"
              strokeLinecap="round"
              opacity="0.55"
            />
          </g>

          {/* Tick marks */}
          {[-75, -50, -25, 0, 25, 50, 75].map((deg) => (
            <line
              key={deg}
              x1={centerX}
              y1={centerY}
              x2={centerX}
              y2="24"
              stroke="#3f3f46"
              strokeWidth="0.5"
              transform={`rotate(${deg} ${centerX} ${centerY})`}
            />
          ))}

          {/* Needle with spring animation */}
          <motion.g
            initial={{ rotate: -90 }}
            animate={{ rotate: needleAngle }}
            transition={{ type: 'spring', stiffness: 50, damping: 12 }}
            style={{ transformOrigin: `${centerX}px ${centerY}px` }}
            filter="url(#needleShadow)"
          >
            <line
              x1={centerX}
              y1={centerY}
              x2={centerX}
              y2="28"
              stroke="white"
              strokeWidth="2.5"
              strokeLinecap="round"
            />
            {/* Animated glow ring behind needle dot */}
            <circle
              cx={centerX}
              cy={centerY}
              r="9"
              fill="none"
              stroke={colors.raw}
              strokeWidth="1.5"
              opacity="0.3"
              filter="url(#needleDotGlow)"
            >
              <animate
                attributeName="opacity"
                values="0.15;0.4;0.15"
                dur="2.5s"
                repeatCount="indefinite"
              />
              <animate
                attributeName="r"
                values="8;10;8"
                dur="2.5s"
                repeatCount="indefinite"
              />
            </circle>
            <circle
              cx={centerX}
              cy={centerY}
              r="6"
              fill="#27272a"
              stroke="white"
              strokeWidth="2"
            />
          </motion.g>

          {/* Labels */}
          <text x="20" y="126" fill="#f31260" fontSize="10" fontWeight="600" opacity="0.6">
            SELL
          </text>
          <text x="104" y="16" fill="#f5a524" fontSize="10" fontWeight="600" opacity="0.6">
            HOLD
          </text>
          <text x="199" y="126" fill="#17c964" fontSize="10" fontWeight="600" opacity="0.6">
            BUY
          </text>
        </svg>
      </div>

      {/* Score */}
      <div className="text-center space-y-1.5">
        <div className={`text-4xl font-bold font-mono ${colors.text}`}>
          {score > 0 ? '+' : ''}
          {score}
        </div>
        <div className={`text-xl font-bold tracking-wide ${colors.text}`}>
          {recommendation}
        </div>

        {/* Confidence bar */}
        <div className="mt-3">
          <div className="flex justify-between items-center mb-1">
            <span className="text-[10px] text-gray-500 uppercase tracking-wider">
              Confidence
            </span>
            <span className="text-xs font-semibold font-mono">
              {(confidence * 100).toFixed(0)}%
            </span>
          </div>
          <div className="h-[2px] bg-dark-inset rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full ${colors.bg} transition-all duration-500`}
              style={{
                width: `${confidence * 100}%`,
                opacity: 0.8,
                boxShadow: colors.barGlow,
              }}
            />
          </div>
        </div>
      </div>

      {/* Additional info */}
      {analysis.analysis?.position_size && (
        <div className="mt-5 pt-4 border-t border-white/5 space-y-3">
          <div className="flex justify-between items-center">
            <span className="text-xs text-gray-500">Position Size</span>
            <span
              className={`text-xs font-semibold font-mono px-2 py-0.5 rounded ${
                analysis.analysis.position_size === 'LARGE'
                  ? 'bg-success/15 text-success-400'
                  : analysis.analysis.position_size === 'MEDIUM'
                    ? 'bg-primary/15 text-primary-400'
                    : 'bg-gray-500/15 text-gray-400'
              }`}
            >
              {analysis.analysis.position_size}
            </span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-xs text-gray-500">Time Horizon</span>
            <span className="text-xs font-semibold font-mono px-2 py-0.5 rounded bg-accent-purple/15 text-accent-purple">
              {analysis.analysis.time_horizon?.replace(/_/g, ' ')}
            </span>
          </div>
        </div>
      )}

      {/* Agent Consensus */}
      {analysis.agent_results && (
        <AgentConsensus agentResults={analysis.agent_results} />
      )}
    </motion.div>
  );
};

export default Recommendation;
