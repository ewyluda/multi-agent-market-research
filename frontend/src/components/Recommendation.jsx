/**
 * Recommendation - BUY/HOLD/SELL gauge with score
 */

import React from 'react';

const Recommendation = ({ analysis }) => {
  if (!analysis) {
    return (
      <div className="bg-dark-card border border-dark-border rounded-lg p-6">
        <h3 className="text-lg font-semibold mb-4">Recommendation</h3>
        <div className="text-gray-500 text-center py-8">
          No analysis available
        </div>
      </div>
    );
  }

  const { recommendation, score, confidence } = analysis.analysis || {};

  // Calculate rotation for gauge needle (-90deg for SELL, 0deg for HOLD, +90deg for BUY)
  // Score ranges from -100 to +100
  const rotation = (score / 100) * 90; // Maps -100 to -90deg, +100 to +90deg

  const getRecommendationColor = () => {
    if (recommendation === 'BUY') return 'text-green-500';
    if (recommendation === 'SELL') return 'text-red-500';
    return 'text-yellow-500';
  };

  return (
    <div className="bg-dark-card border border-dark-border rounded-lg p-6">
      <h3 className="text-lg font-semibold mb-4">Recommendation</h3>

      {/* Gauge */}
      <div className="relative w-64 h-32 mx-auto mb-6">
        {/* Background arc */}
        <svg className="w-full h-full" viewBox="0 0 200 100">
          {/* Red zone (SELL) */}
          <path
            d="M 10 90 A 80 80 0 0 1 50 20"
            fill="none"
            stroke="#ef4444"
            strokeWidth="20"
            opacity="0.3"
          />
          {/* Yellow zone (HOLD) */}
          <path
            d="M 50 20 A 80 80 0 0 1 150 20"
            fill="none"
            stroke="#eab308"
            strokeWidth="20"
            opacity="0.3"
          />
          {/* Green zone (BUY) */}
          <path
            d="M 150 20 A 80 80 0 0 1 190 90"
            fill="none"
            stroke="#10b981"
            strokeWidth="20"
            opacity="0.3"
          />

          {/* Needle */}
          <g transform={`rotate(${rotation} 100 90)`}>
            <line
              x1="100"
              y1="90"
              x2="100"
              y2="30"
              stroke="white"
              strokeWidth="3"
              strokeLinecap="round"
            />
            <circle cx="100" cy="90" r="6" fill="white" />
          </g>

          {/* Labels */}
          <text x="20" y="95" fill="#ef4444" fontSize="12" fontWeight="bold">
            SELL
          </text>
          <text x="85" y="15" fill="#eab308" fontSize="12" fontWeight="bold">
            HOLD
          </text>
          <text x="160" y="95" fill="#10b981" fontSize="12" fontWeight="bold">
            BUY
          </text>
        </svg>
      </div>

      {/* Score and confidence */}
      <div className="text-center space-y-2">
        <div className={`text-4xl font-bold ${getRecommendationColor()}`}>
          {score > 0 ? '+' : ''}{score}
        </div>
        <div className={`text-2xl font-semibold ${getRecommendationColor()}`}>
          {recommendation}
        </div>
        <div className="text-sm text-gray-400">
          Confidence: {(confidence * 100).toFixed(0)}%
        </div>
      </div>

      {/* Additional info */}
      {analysis.analysis?.position_size && (
        <div className="mt-6 pt-4 border-t border-dark-border space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-gray-400">Position Size:</span>
            <span className="font-medium">{analysis.analysis.position_size}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-400">Time Horizon:</span>
            <span className="font-medium">{analysis.analysis.time_horizon?.replace('_', ' ')}</span>
          </div>
        </div>
      )}
    </div>
  );
};

export default Recommendation;
