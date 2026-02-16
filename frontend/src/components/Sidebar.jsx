/**
 * Sidebar - Fixed left navigation with icon tooltips and active state indicators.
 * 64px wide, full viewport height, z-40.
 * Uses framer-motion for staggered entrance animation.
 *
 * Props:
 *   activeView         - current VIEW_MODE string
 *   onViewChange       - (viewKey) => void
 *   unacknowledgedCount - number of unread alert notifications
 */

import React from 'react';
import { motion as Motion } from 'framer-motion';
import {
  PulseIcon,
  HistoryIcon,
  ChartBarIcon,
  BuildingIcon,
  ClockIcon,
  BellIcon,
} from './Icons';

/* ─── Navigation items ─── */
const NAV_ITEMS = [
  { key: 'analysis',  label: 'Analysis',  Icon: PulseIcon   },
  { key: 'history',   label: 'History',   Icon: HistoryIcon  },
  { key: 'watchlist',  label: 'Watchlist',  Icon: ChartBarIcon },
  { key: 'portfolio', label: 'Portfolio', Icon: BuildingIcon },
  { key: 'schedules', label: 'Schedules', Icon: ClockIcon    },
  { key: 'alerts',    label: 'Alerts',    Icon: BellIcon     },
];

/* ─── framer-motion variants ─── */
const listVariants = {
  hidden: {},
  visible: {
    transition: { staggerChildren: 0.06, delayChildren: 0.2 },
  },
};

const itemVariants = {
  hidden: { opacity: 0, x: -8 },
  visible: { opacity: 1, x: 0, transition: { duration: 0.3, ease: [0.22, 1, 0.36, 1] } },
};

const Sidebar = ({ activeView, onViewChange, unacknowledgedCount = 0 }) => {
  return (
    <nav
      className="fixed top-0 left-0 h-screen flex flex-col items-center z-40"
      style={{
        width: 'var(--sidebar-width, 64px)',
        backgroundColor: 'var(--bg-sidebar)',
        borderRight: '1px solid rgba(255,255,255,0.04)',
      }}
    >
      {/* ─── Brand icon ─── */}
      <div className="flex items-center justify-center pt-5 pb-4">
        <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-primary to-primary-300 flex items-center justify-center shadow-[0_0_16px_rgba(0,111,238,0.25)]">
          <PulseIcon className="w-5 h-5 text-white" />
        </div>
      </div>

      {/* ─── Separator ─── */}
      <div className="w-7 h-px bg-white/[0.06] mb-4" />

      {/* ─── Nav items ─── */}
      <Motion.ul
        className="flex flex-col items-center gap-2 list-none p-0 m-0"
        variants={listVariants}
        initial="hidden"
        animate="visible"
      >
        {NAV_ITEMS.map(({ key, label, Icon: iconComponent }) => {
          const isActive = activeView === key;
          const isAlerts = key === 'alerts';
          const iconNode = React.createElement(iconComponent, { className: 'w-[18px] h-[18px] relative z-10' });

          return (
            <Motion.li key={key} variants={itemVariants}>
              <button
                onClick={() => onViewChange(key)}
                className={`sidebar-nav-item group ${isActive ? 'active' : ''}`}
                aria-label={label}
                aria-current={isActive ? 'page' : undefined}
              >
                {/* Icon */}
                {iconNode}

                {/* Alert badge */}
                {isAlerts && unacknowledgedCount > 0 && (
                  <span className="absolute -top-1 -right-1 flex items-center justify-center min-w-[16px] h-4 px-1 text-[9px] font-bold text-white bg-danger rounded-full shadow-[0_0_8px_rgba(243,18,96,0.4)] z-20">
                    {unacknowledgedCount > 99 ? '99+' : unacknowledgedCount}
                  </span>
                )}

                {/* Tooltip */}
                <span className="pointer-events-none absolute left-full ml-3 px-2.5 py-1 rounded-md text-[11px] font-medium text-white bg-content2 border border-white/[0.08] shadow-lg opacity-0 scale-95 group-hover:opacity-100 group-hover:scale-100 transition-all duration-150 whitespace-nowrap z-50">
                  {label}
                </span>
              </button>
            </Motion.li>
          );
        })}
      </Motion.ul>
    </nav>
  );
};

export default Sidebar;
