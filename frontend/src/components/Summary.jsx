/**
 * Summary - Executive summary, price targets, risks and opportunities
 */

import React from 'react';
import { DocumentIcon, ShieldExclamationIcon, LightbulbIcon, ArrowUpIcon, ArrowDownIcon } from './Icons';

/**
 * FormattedReasoning - Parses LLM chain-of-thought reasoning into styled sections.
 * Handles numbered sections (1. Title: body), double-newline paragraphs, or raw text.
 */
const FormattedReasoning = ({ text }) => {
  if (!text) return null;

  // Try to split on numbered sections: "1. ", "2. ", etc.
  const sections = text.split(/(?=\d+\.\s)/).filter(s => s.trim());

  if (sections.length > 1) {
    return (
      <div className="space-y-2.5">
        {sections.map((section, index) => {
          const match = section.match(/^(\d+)\.\s*(.*)/s);
          if (!match) {
            return <p key={index} className="text-sm leading-relaxed text-gray-400">{section.trim()}</p>;
          }

          const num = match[1];
          const content = match[2].trim();

          // Split title from body at first colon
          const colonIdx = content.indexOf(':');
          let title, body;
          if (colonIdx > 0 && colonIdx < 80) {
            title = content.substring(0, colonIdx).trim();
            body = content.substring(colonIdx + 1).trim();
          } else {
            // No colon found — use first sentence as title
            const periodIdx = content.indexOf('. ');
            if (periodIdx > 0 && periodIdx < 100) {
              title = content.substring(0, periodIdx).trim();
              body = content.substring(periodIdx + 2).trim();
            } else {
              title = content.substring(0, 80);
              body = content.length > 80 ? content.substring(80).trim() : '';
            }
          }

          return (
            <div key={index} className="flex items-start space-x-3 p-3 bg-dark-inset rounded-lg">
              <span className="flex-shrink-0 w-6 h-6 rounded-full bg-accent-blue/15 border border-accent-blue/30 flex items-center justify-center text-[10px] font-bold text-accent-blue mt-0.5">
                {num}
              </span>
              <div className="min-w-0 flex-1">
                <div className="text-sm font-medium text-gray-200 leading-snug">{title}</div>
                {body && <div className="text-[13px] text-gray-400 leading-relaxed mt-1">{body}</div>}
              </div>
            </div>
          );
        })}
      </div>
    );
  }

  // Fallback: split on double newlines for paragraphs
  const paragraphs = text.split(/\n\n+/).filter(p => p.trim());
  if (paragraphs.length > 1) {
    return (
      <div className="space-y-3">
        {paragraphs.map((para, i) => (
          <p key={i} className="text-sm leading-relaxed text-gray-300">{para.trim()}</p>
        ))}
      </div>
    );
  }

  // Final fallback: render as single paragraph
  return <p className="text-sm leading-7 text-gray-300">{text}</p>;
};

const Summary = ({ analysis }) => {
  if (!analysis) {
    return null;
  }

  const { reasoning, risks, opportunities, price_targets } = analysis.analysis || {};

  // Calculate upside/downside from entry
  const getPercent = (target, entry) => {
    if (!target || !entry || entry === 0) return null;
    return (((target - entry) / entry) * 100).toFixed(1);
  };

  const upside = getPercent(price_targets?.target, price_targets?.entry);
  const downside = getPercent(price_targets?.stop_loss, price_targets?.entry);

  return (
    <div className="space-y-4">
      {/* Executive Summary */}
      {reasoning && (
        <div className="glass-card-elevated rounded-xl p-5 animate-fade-in">
          <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider mb-3 flex items-center space-x-2">
            <DocumentIcon className="w-4 h-4 text-accent-blue" />
            <span>Executive Summary</span>
          </h3>
          <FormattedReasoning text={reasoning} />
        </div>
      )}

      {/* Price Targets */}
      {price_targets && (
        <div className="glass-card-elevated rounded-xl p-5 animate-fade-in" style={{ animationDelay: '0.1s' }}>
          <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider mb-3">Price Targets</h3>
          <div className="grid grid-cols-3 gap-3">
            {price_targets.entry != null && (
              <div className="p-3 bg-dark-inset rounded-lg border-t-2 border-t-accent-blue">
                <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Entry</div>
                <div className="text-xl font-bold text-accent-blue tabular-nums">
                  ${price_targets.entry.toFixed(2)}
                </div>
              </div>
            )}
            {price_targets.target != null && (
              <div className="p-3 bg-dark-inset rounded-lg border-t-2 border-t-emerald-500">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[10px] text-gray-500 uppercase tracking-wider">Target</span>
                  {upside && (
                    <span className="text-[10px] text-emerald-400 font-medium flex items-center">
                      <ArrowUpIcon className="w-2.5 h-2.5 mr-0.5" />+{upside}%
                    </span>
                  )}
                </div>
                <div className="text-xl font-bold text-emerald-400 tabular-nums">
                  ${price_targets.target.toFixed(2)}
                </div>
              </div>
            )}
            {price_targets.stop_loss != null && (
              <div className="p-3 bg-dark-inset rounded-lg border-t-2 border-t-red-500">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[10px] text-gray-500 uppercase tracking-wider">Stop Loss</span>
                  {downside && (
                    <span className="text-[10px] text-red-400 font-medium flex items-center">
                      <ArrowDownIcon className="w-2.5 h-2.5 mr-0.5" />{downside}%
                    </span>
                  )}
                </div>
                <div className="text-xl font-bold text-red-400 tabular-nums">
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
          <div
            className="glass-card-elevated rounded-xl p-5 border-l-2 border-l-red-500 bg-gradient-to-r from-red-500/[0.03] to-transparent animate-fade-in"
            style={{ animationDelay: '0.2s' }}
          >
            <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider mb-3 flex items-center space-x-2">
              <ShieldExclamationIcon className="w-4 h-4 text-red-400" />
              <span>Risks</span>
            </h3>
            <ul className="space-y-2">
              {risks.map((risk, index) => (
                <li key={index} className="text-sm text-gray-300 flex items-start">
                  <span className="text-[10px] text-red-400/60 font-mono mr-2 mt-0.5 flex-shrink-0">{String(index + 1).padStart(2, '0')}</span>
                  <span>{risk}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Opportunities */}
        {opportunities && opportunities.length > 0 && (
          <div
            className="glass-card-elevated rounded-xl p-5 border-l-2 border-l-emerald-500 bg-gradient-to-r from-emerald-500/[0.03] to-transparent animate-fade-in"
            style={{ animationDelay: '0.25s' }}
          >
            <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider mb-3 flex items-center space-x-2">
              <LightbulbIcon className="w-4 h-4 text-emerald-400" />
              <span>Opportunities</span>
            </h3>
            <ul className="space-y-2">
              {opportunities.map((opportunity, index) => (
                <li key={index} className="text-sm text-gray-300 flex items-start">
                  <span className="text-[10px] text-emerald-400/60 font-mono mr-2 mt-0.5 flex-shrink-0">{String(index + 1).padStart(2, '0')}</span>
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
