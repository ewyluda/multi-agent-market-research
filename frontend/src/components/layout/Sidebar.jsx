import { NavLink } from 'react-router-dom'
import {
  Activity, BarChart3, Bell, Briefcase,
  Clock, History, LineChart, TrendingUp
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

const NAV_SECTIONS = [
  {
    label: 'RESEARCH',
    items: [
      { to: '/', icon: Activity, label: 'Analysis' },
      { to: '/macro', icon: TrendingUp, label: 'Macro' },
    ],
  },
  {
    label: 'TOOLS',
    items: [
      { to: '/watchlist', icon: BarChart3, label: 'Watchlist' },
      { to: '/portfolio', icon: Briefcase, label: 'Holdings' },
      { to: '/schedules', icon: Clock, label: 'Schedules' },
      { to: '/alerts', icon: Bell, label: 'Alerts', badge: true },
    ],
  },
  {
    label: 'HISTORY',
    items: [
      { to: '/history', icon: History, label: 'History' },
      { to: '/inflections', icon: LineChart, label: 'Inflections' },
    ],
  },
]

const REC_COLORS = {
  BUY: 'var(--success)',
  'STRONG BUY': 'var(--success)',
  SELL: 'var(--danger)',
  'STRONG SELL': 'var(--danger)',
  HOLD: 'var(--warning)',
}

export default function Sidebar({ unacknowledgedCount = 0, recentAnalyses = [], onSelectTicker }) {
  return (
    <aside
      className="fixed left-0 z-30 flex flex-col border-r border-[var(--border)] overflow-y-auto"
      style={{
        top: 'var(--header-height)',
        bottom: 0,
        width: 'var(--sidebar-width)',
        backgroundColor: 'var(--sidebar-bg)',
      }}
    >
      <nav className="flex-1 px-3 py-4 space-y-6">
        {NAV_SECTIONS.map((section) => (
          <div key={section.label}>
            <p className="px-3 mb-2 text-[10px] font-semibold tracking-widest text-[var(--text-muted)] uppercase">
              {section.label}
            </p>
            <div className="space-y-0.5">
              {section.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === '/'}
                  className={({ isActive }) =>
                    cn(
                      'flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors relative',
                      isActive
                        ? 'bg-[var(--sidebar-active-bg)] text-[var(--primary)]'
                        : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)] hover:bg-[rgba(255,255,255,0.03)]'
                    )
                  }
                >
                  {({ isActive }) => (
                    <>
                      {isActive && (
                        <div
                          className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 rounded-r-full"
                          style={{ backgroundColor: 'var(--primary)' }}
                        />
                      )}
                      <item.icon className="w-4 h-4 shrink-0" />
                      <span>{item.label}</span>
                      {item.badge && unacknowledgedCount > 0 && (
                        <Badge variant="destructive" className="ml-auto text-[10px] px-1.5 py-0">
                          {unacknowledgedCount}
                        </Badge>
                      )}
                    </>
                  )}
                </NavLink>
              ))}
            </div>
          </div>
        ))}
      </nav>

      {recentAnalyses.length > 0 && (
        <div className="px-3 pb-4 border-t border-[var(--border)] pt-4">
          <p className="px-3 mb-2 text-[10px] font-semibold tracking-widest text-[var(--text-muted)] uppercase">
            Recent
          </p>
          <div className="space-y-0.5">
            {recentAnalyses.map((item) => (
              <button
                key={item.ticker}
                onClick={() => onSelectTicker?.(item.ticker)}
                className="flex items-center gap-3 px-3 py-1.5 rounded-lg text-sm w-full text-left transition-colors text-[var(--text-muted)] hover:text-[var(--text-secondary)] hover:bg-[rgba(255,255,255,0.03)] cursor-pointer"
              >
                <div
                  className="w-2 h-2 rounded-full shrink-0"
                  style={{ backgroundColor: REC_COLORS[item.recommendation?.toUpperCase()] || 'var(--text-muted)' }}
                />
                <span className="font-data text-xs">{item.ticker}</span>
                <span className="ml-auto text-[10px] text-[var(--text-muted)]">
                  {item.recommendation?.toUpperCase()}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}
    </aside>
  )
}
