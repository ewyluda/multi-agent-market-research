import { motion } from 'framer-motion';
import { PulseIcon, HistoryIcon, ChartBarIcon, BuildingIcon, ClockIcon, BellIcon } from './Icons';

const ActivityIcon = () => (
  <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
    <path fillRule="evenodd" d="M2 10a.75.75 0 01.75-.75h2.793l1.874-3.748a.75.75 0 011.341.008L11.25 11.5l1.293-2.586a.75.75 0 011.326-.012L15.5 11.25h2.75a.75.75 0 010 1.5h-3.25a.75.75 0 01-.67-.415L13.25 10.5l-1.293 2.586a.75.75 0 01-1.326.012L8.14 7.109 6.83 9.724A.75.75 0 016.17 10.25H2.75A.75.75 0 012 10z" clipRule="evenodd" />
  </svg>
);

const NAV_SECTIONS = [
  {
    label: 'Analysis',
    items: [
      { key: 'analysis', label: 'Analysis', Icon: PulseIcon },
      { key: 'history', label: 'History', Icon: HistoryIcon },
    ],
  },
  {
    label: 'Portfolio',
    items: [
      { key: 'watchlist', label: 'Watchlist', Icon: ChartBarIcon },
      { key: 'inflections', label: 'Inflections', Icon: ActivityIcon },
      { key: 'portfolio', label: 'Holdings', Icon: BuildingIcon },
      { key: 'schedules', label: 'Schedules', Icon: ClockIcon },
      { key: 'alerts', label: 'Alerts', Icon: BellIcon },
    ],
  },
];

const STANCE_COLORS = {
  BUY: 'text-[#17c964]',
  SELL: 'text-[#f31260]',
  HOLD: 'text-[#f5a524]',
};

export default function Sidebar({ activeView, onViewChange, unacknowledgedCount = 0, recentAnalyses = [] }) {
  return (
    <aside className="fixed left-0 top-0 bottom-0 z-50 flex flex-col border-r"
      style={{
        width: 'var(--sidebar-width, 220px)',
        background: 'rgba(255,255,255,0.02)',
        borderColor: 'rgba(255,255,255,0.06)',
      }}
    >
      {/* Logo */}
      <div className="flex items-center gap-2 px-5 pt-4 pb-6">
        <div className="w-2 h-2 rounded-full bg-[#006fee]" />
        <span className="text-[0.95rem] font-bold text-white/90 tracking-tight">Market Research</span>
      </div>

      {/* Nav sections */}
      {NAV_SECTIONS.map((section) => (
        <div key={section.label} className="px-3 mb-5">
          <div className="px-2 pb-2 text-[0.6rem] uppercase tracking-[0.12em] font-semibold text-white/25">
            {section.label}
          </div>
          {section.items.map((item) => {
            const isActive = activeView === item.key;
            return (
              <button
                key={item.key}
                onClick={() => onViewChange(item.key)}
                className={`flex items-center gap-2.5 w-full px-3 py-2 rounded-lg text-[0.82rem] transition-colors relative ${
                  isActive
                    ? 'bg-[rgba(0,111,238,0.1)] text-[#006fee] font-medium'
                    : 'text-white/50 hover:bg-white/[0.04] hover:text-white/70'
                }`}
              >
                <item.Icon className="w-[18px] h-[18px]" style={{ opacity: isActive ? 1 : 0.5 }} />
                {item.label}
                {item.key === 'alerts' && unacknowledgedCount > 0 && (
                  <span className="ml-auto text-[0.6rem] font-semibold bg-[#f31260] text-white px-1.5 py-0.5 rounded-full min-w-[18px] text-center">
                    {unacknowledgedCount}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      ))}

      {/* Divider */}
      <div className="mx-5 h-px bg-white/5" />

      {/* Recent analyses */}
      <div className="px-3 mt-auto pb-4">
        <div className="px-2 pb-2 text-[0.6rem] uppercase tracking-[0.12em] font-semibold text-white/25">
          Recent
        </div>
        {recentAnalyses.slice(0, 5).map((item) => (
          <button
            key={item.ticker}
            onClick={() => {
              onViewChange('analysis');
              item.onSelect?.();
            }}
            className="flex items-center justify-between w-full px-3 py-1.5 rounded-md text-white/40 hover:bg-white/[0.03] hover:text-white/60 transition-colors"
          >
            <span className="text-[0.75rem] font-semibold tabular-nums">{item.ticker}</span>
            <span className={`text-[0.65rem] font-medium ${STANCE_COLORS[item.recommendation] || 'text-white/40'}`}>
              {item.recommendation}
            </span>
          </button>
        ))}
        {recentAnalyses.length === 0 && (
          <div className="px-3 py-2 text-[0.7rem] text-white/20">No recent analyses</div>
        )}
      </div>
    </aside>
  );
}
