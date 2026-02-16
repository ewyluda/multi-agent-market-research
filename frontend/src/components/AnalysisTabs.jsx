/**
 * AnalysisTabs - Horizontal tab bar for the analysis content area
 * Tabs: Overview, Changes, Scenarios, Diagnostics, Research, Sentiment, News, Options
 * Uses framer-motion layoutId for smooth underline transitions
 */

import React from 'react';
import { motion } from 'framer-motion';

const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'changes', label: 'Changes' },
  { id: 'scenarios', label: 'Scenarios' },
  { id: 'diagnostics', label: 'Diagnostics' },
  { id: 'research', label: 'Research' },
  { id: 'sentiment', label: 'Sentiment' },
  { id: 'news', label: 'News' },
  { id: 'options', label: 'Options' },
];

/**
 * Determine whether the Options tab should be visible.
 * Hidden when there is no options data or total_contracts is 0.
 */
const hasOptionsData = (analysis) => {
  try {
    const optionsData = analysis?.agent_results?.options?.data;
    if (!optionsData) return false;
    if (optionsData.total_contracts === 0) return false;
    return true;
  } catch {
    return false;
  }
};

const AnalysisTabs = ({ activeTab, onTabChange, analysis }) => {
  const showOptions = hasOptionsData(analysis);

  const visibleTabs = showOptions
    ? TABS
    : TABS.filter((tab) => tab.id !== 'options');

  return (
    <div className="border-b border-white/5">
      <nav className="flex space-x-8" aria-label="Analysis tabs">
        {visibleTabs.map((tab) => {
          const isActive = activeTab === tab.id;

          return (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              className={`relative px-2 py-3.5 text-[13px] font-medium uppercase tracking-wider transition-colors duration-200 cursor-pointer ${
                isActive
                  ? 'text-white'
                  : 'text-gray-500 hover:text-gray-300'
              }`}
              aria-selected={isActive}
              role="tab"
            >
              {tab.label}

              {isActive && (
                <motion.div
                  layoutId="tab-underline"
                  className="absolute bottom-0 left-0 right-0 h-[2px] bg-accent-blue"
                  transition={{
                    type: 'spring',
                    stiffness: 500,
                    damping: 35,
                  }}
                />
              )}
            </button>
          );
        })}
      </nav>
    </div>
  );
};

export default AnalysisTabs;
