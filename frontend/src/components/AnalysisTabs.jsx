/**
 * AnalysisTabs - Horizontal tab bar for the analysis content area
 * Tabs: Overview, Risk, Opportunities, Diagnostics
 * Uses framer-motion layoutId for smooth underline transitions
 */

import React from 'react';
import { motion as Motion } from 'framer-motion';

const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'risk', label: 'Risks' },
  { id: 'opportunities', label: 'Opportunities' },
  { id: 'leadership', label: 'Leadership' },
  { id: 'diagnostics', label: 'Diagnostics' },
];

const AnalysisTabs = ({ activeTab, onTabChange }) => {
  const visibleTabs = TABS;

  return (
    <div className="border-b border-white/5 pb-1">
      <nav
        className="flex items-center gap-2 overflow-x-auto py-1 pr-1"
        aria-label="Analysis tabs"
        role="tablist"
      >
        {visibleTabs.map((tab) => {
          const isActive = activeTab === tab.id;

          return (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              className={`relative shrink-0 rounded-lg border px-4 py-2.5 text-[12px] sm:text-[13px] font-semibold tracking-wide transition-all duration-200 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 ${
                isActive
                  ? 'text-white bg-white/[0.06] border-white/15 shadow-[inset_0_0_0_1px_rgba(255,255,255,0.02)]'
                  : 'text-gray-400 border-transparent hover:text-gray-200 hover:bg-white/[0.03] hover:border-white/10'
              }`}
              aria-selected={isActive}
              role="tab"
            >
              {tab.label}

              {isActive && (
                <Motion.div
                  layoutId="tab-underline"
                  className="absolute bottom-[6px] left-3 right-3 h-[2px] rounded-full bg-accent-blue"
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
