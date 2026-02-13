/**
 * SentimentReport - Sentiment analysis with arc gauge meter, factor breakdown, and key themes
 */

import React from 'react';
import { motion } from 'framer-motion';

const SentimentReport = ({ analysis }) => {

  if (!analysis || !analysis.agent_results?.sentiment) {
    return (
      <div className="glass-card-elevated rounded-xl p-5">
        <div className="skeleton h-4 w-36 mb-4" />
        <div className="skeleton h-16 w-full mb-3 rounded-lg" />
        <div className="skeleton h-24 w-full rounded-lg" />
      </div>
    );
  }

  const sentimentData = analysis.agent_results.sentiment.data || {};
  const overallSentiment = sentimentData.overall_sentiment || 0;
  const confidence = sentimentData.confidence || 0;
  const factors = sentimentData.factors || {};

  const getSentimentLabel = (score) => {
    if (score > 0.3) return 'Positive';
    if (score < -0.3) return 'Negative';
    return 'Neutral';
  };

  const getSentimentColor = (score) => {
    if (score > 0.3) return 'text-success-400';
    if (score < -0.3) return 'text-danger-400';
    return 'text-warning-400';
  };

  // Map sentiment score (-1 to 1) to needle angle (0 to 180 degrees)
  const needleAngle = ((overallSentiment + 1) / 2) * 180;
  // Convert to radians for SVG positioning
  const needleRad = (needleAngle - 180) * (Math.PI / 180);
  const cx = 90, cy = 55, r = 40;
  const needleX = cx + Math.cos(needleRad) * (r - 8);
  const needleY = cy + Math.sin(needleRad) * (r - 8);

  // Arc path helper
  const describeArc = (startAngle, endAngle) => {
    const startRad = (startAngle - 180) * (Math.PI / 180);
    const endRad = (endAngle - 180) * (Math.PI / 180);
    const x1 = cx + Math.cos(startRad) * r;
    const y1 = cy + Math.sin(startRad) * r;
    const x2 = cx + Math.cos(endRad) * r;
    const y2 = cy + Math.sin(endRad) * r;
    const largeArc = endAngle - startAngle > 180 ? 1 : 0;
    return `M ${x1} ${y1} A ${r} ${r} 0 ${largeArc} 1 ${x2} ${y2}`;
  };

  const hasFactors = Object.keys(factors).length > 0;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.15 }}
      className="glass-card-elevated rounded-xl p-5"
    >
      <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider mb-4">
        Sentiment Report
      </h3>

      {/* Sentiment Arc Gauge */}
      <div className="p-4 bg-dark-inset rounded-lg">
        <div className="flex items-start justify-between mb-2">
          <div>
            <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Overall Sentiment</div>
            <div className={`text-2xl font-bold ${getSentimentColor(overallSentiment)}`}>
              {getSentimentLabel(overallSentiment)}
              <span className="text-sm font-mono ml-1.5 opacity-60">{overallSentiment.toFixed(2)}</span>
            </div>
          </div>
          <div className="text-right">
            <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Confidence</div>
            <div className="text-2xl font-bold font-mono">{(confidence * 100).toFixed(0)}%</div>
          </div>
        </div>

        {/* SVG Arc Gauge */}
        <div className="flex justify-center my-4 px-2">
          <svg viewBox="0 0 180 68" className="w-full max-w-[200px]">
            <defs>
              <linearGradient id="sentArcGrad" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stopColor="#f31260" />
                <stop offset="50%" stopColor="#f5a524" />
                <stop offset="100%" stopColor="#17c964" />
              </linearGradient>
            </defs>
            {/* Background track */}
            <path d={describeArc(0, 180)} fill="none" stroke="#27272a" strokeWidth="10" strokeLinecap="round" />
            {/* Colored arc */}
            <path d={describeArc(0, 180)} fill="none" stroke="url(#sentArcGrad)" strokeWidth="10" strokeLinecap="round" opacity="0.4" />
            {/* Active portion (brighter up to needle) */}
            {needleAngle > 2 && (
              <path d={describeArc(0, Math.min(needleAngle, 179))} fill="none" stroke="url(#sentArcGrad)" strokeWidth="10" strokeLinecap="round" opacity="0.8" />
            )}
            {/* Needle */}
            <line x1={cx} y1={cy} x2={needleX} y2={needleY} stroke="white" strokeWidth="2" strokeLinecap="round" />
            <circle cx={cx} cy={cy} r="3.5" fill="#18181b" stroke="white" strokeWidth="2" />
            {/* Labels */}
            <text x="12" y="65" fill="#71717a" fontSize="8" fontFamily="'JetBrains Mono', monospace">BEAR</text>
            <text x="140" y="65" fill="#71717a" fontSize="8" fontFamily="'JetBrains Mono', monospace">BULL</text>
          </svg>
        </div>
      </div>

      {/* Reasoning */}
      {sentimentData.reasoning && (
        <div className="mt-3 p-4 bg-dark-inset rounded-lg">
          <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Analysis</div>
          <div className="text-sm text-gray-300 leading-relaxed">{sentimentData.reasoning}</div>
        </div>
      )}

      {/* Key Themes */}
      {sentimentData.key_themes && sentimentData.key_themes.length > 0 && (
        <div className="mt-3 p-4 bg-dark-inset rounded-lg">
          <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Key Themes</div>
          <div className="flex flex-wrap gap-1.5">
            {sentimentData.key_themes.map((theme, index) => (
              <span
                key={index}
                className="px-2.5 py-1 bg-accent-purple/10 border border-accent-purple/20 rounded-md text-[10px] text-accent-purple font-medium transition-colors duration-200 hover:bg-accent-purple/20 hover:border-accent-purple/30"
              >
                {theme}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Factor Breakdown */}
      {hasFactors && (
        <div className="mt-3 p-4 bg-dark-inset rounded-lg">
          <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-3">Sentiment by Factor</div>
          <div className="space-y-2">
            {Object.entries(factors).map(([factorName, factorData], index) => {
              const score = factorData.score || 0;
              const weight = factorData.weight || 0;
              const contribution = factorData.contribution || 0;
              const barWidth = Math.abs(score) * 50;
              const barLeft = score < 0 ? 50 - barWidth : 50;

              return (
                <div key={factorName} className="p-3 bg-white/[0.02] rounded-lg">
                  <div className="flex justify-between items-center mb-2">
                    <div className="font-medium text-xs capitalize">
                      {factorName.replace(/_/g, ' ')}
                    </div>
                    <div className="flex items-center space-x-2">
                      <span className={`text-xs font-semibold font-mono ${getSentimentColor(score)}`}>
                        {score > 0 ? '+' : ''}{score.toFixed(2)}
                      </span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-accent-purple/15 text-accent-purple font-mono font-medium">
                        {(weight * 100).toFixed(0)}%
                      </span>
                    </div>
                  </div>

                  {/* Centered bar chart */}
                  <div className="relative h-2 bg-gray-700/50 rounded-full overflow-hidden">
                    <motion.div
                      className={`absolute h-full rounded-full ${score > 0 ? 'bg-success' : 'bg-danger'}`}
                      initial={{ width: 0 }}
                      animate={{ width: `${barWidth}%` }}
                      transition={{ duration: 0.5, delay: index * 0.05, ease: 'easeOut' }}
                      style={{ left: `${barLeft}%`, opacity: 0.7 }}
                    />
                    <div className="absolute left-1/2 top-0 w-px h-full bg-gray-500/50" />
                  </div>

                  <div className="mt-1.5 text-[10px] text-gray-500 font-mono">
                    Contribution: <span className={getSentimentColor(contribution)}>{contribution > 0 ? '+' : ''}{contribution.toFixed(3)}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </motion.div>
  );
};

export default SentimentReport;
