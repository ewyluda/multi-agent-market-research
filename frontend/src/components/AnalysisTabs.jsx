/**
 * AnalysisTabs - Horizontal tab bar for the analysis content area
 * Tabs: Overview, Risk, Opportunities, Diagnostics
 * Uses framer-motion layoutId for smooth underline transitions
 */

import React from 'react';
import { motion as Motion } from 'framer-motion';

const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'risk', label: 'Risk' },
  { id: 'opportunities', label: 'Opportunities' },
  { id: 'diagnostics', label: 'Diagnostics' },
];

const AnalysisTabs = ({ activeTab, onTabChange }) => {
  const visibleTabs = TABS;

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
                <Motion.div
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
