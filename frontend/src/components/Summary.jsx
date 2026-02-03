/**
 * Summary - Executive summary and key points
 */

import React from 'react';

const Summary = ({ analysis }) => {
  if (!analysis) {
    return null;
  }

  const { reasoning, risks, opportunities, price_targets } = analysis.analysis || {};

  return (
    <div className="space-y-6">
      {/* Executive Summary */}
      {reasoning && (
        <div className="bg-dark-card border border-dark-border rounded-lg p-6">
          <h3 className="text-lg font-semibold mb-4">Executive Summary</h3>
          <p className="text-sm leading-relaxed text-gray-300">{reasoning}</p>
        </div>
      )}

      {/* Price Targets */}
      {price_targets && (
        <div className="bg-dark-card border border-dark-border rounded-lg p-6">
          <h3 className="text-lg font-semibold mb-4">Price Targets</h3>
          <div className="grid grid-cols-3 gap-4">
            {price_targets.entry && (
              <div className="p-3 bg-dark-bg rounded-md">
                <div className="text-xs text-gray-400 mb-1">Entry</div>
                <div className="text-xl font-bold text-accent-blue">
                  ${price_targets.entry.toFixed(2)}
                </div>
              </div>
            )}
            {price_targets.target && (
              <div className="p-3 bg-dark-bg rounded-md">
                <div className="text-xs text-gray-400 mb-1">Target</div>
                <div className="text-xl font-bold text-green-500">
                  ${price_targets.target.toFixed(2)}
                </div>
              </div>
            )}
            {price_targets.stop_loss && (
              <div className="p-3 bg-dark-bg rounded-md">
                <div className="text-xs text-gray-400 mb-1">Stop Loss</div>
                <div className="text-xl font-bold text-red-500">
                  ${price_targets.stop_loss.toFixed(2)}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Risks & Opportunities */}
      <div className="grid grid-cols-2 gap-4">
        {/* Risks */}
        {risks && risks.length > 0 && (
          <div className="bg-dark-card border border-dark-border rounded-lg p-6">
            <h3 className="text-lg font-semibold mb-4 flex items-center">
              <span className="text-red-500 mr-2">⚠️</span>
              Risks
            </h3>
            <ul className="space-y-2">
              {risks.map((risk, index) => (
                <li key={index} className="text-sm text-gray-300 flex items-start">
                  <span className="text-red-500 mr-2">•</span>
                  <span>{risk}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Opportunities */}
        {opportunities && opportunities.length > 0 && (
          <div className="bg-dark-card border border-dark-border rounded-lg p-6">
            <h3 className="text-lg font-semibold mb-4 flex items-center">
              <span className="text-green-500 mr-2">💡</span>
              Opportunities
            </h3>
            <ul className="space-y-2">
              {opportunities.map((opportunity, index) => (
                <li key={index} className="text-sm text-gray-300 flex items-start">
                  <span className="text-green-500 mr-2">•</span>
                  <span>{opportunity}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
};

export default Summary;
