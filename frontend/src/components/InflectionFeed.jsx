import { useState, useEffect } from 'react';
import { getWatchlistInflections } from '../utils/api';

const InflectionFeed = ({ watchlistId, onSelectTicker }) => {
  const [events, setEvents] = useState([]);
  const [expandedId, setExpandedId] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!watchlistId) return;
    setLoading(true);
    getWatchlistInflections(watchlistId)
      .then(setEvents)
      .catch(() => setEvents([]))
      .finally(() => setLoading(false));
  }, [watchlistId]);

  if (loading) {
    return <div className="text-sm p-3" style={{ color: 'var(--text-muted)' }}>Loading feed…</div>;
  }
  if (events.length === 0) {
    return <div className="text-sm p-3" style={{ color: 'var(--text-muted)' }}>No inflection events yet.</div>;
  }

  return (
    <div className="flex flex-col gap-1 overflow-y-auto">
      <div className="text-[0.65rem] uppercase tracking-wider mb-1 px-3 pt-2" style={{ color: 'var(--text-muted)' }}>
        Inflection Feed
      </div>
      {events.map((event) => {
        const isPositive = event.direction === 'positive';
        const isExpanded = expandedId === event.id;
        const date = event.detected_at ? new Date(event.detected_at).toLocaleDateString() : '';
        const dirColor = isPositive ? 'var(--success)' : 'var(--danger)';
        return (
          <div
            key={event.id}
            className="px-3 py-2 rounded-md transition-colors"
            style={{ cursor: 'pointer' }}
            onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(255,255,255,0.03)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
          >
            <button
              onClick={() => { setExpandedId(isExpanded ? null : event.id); onSelectTicker?.(event.ticker); }}
              className="w-full text-left bg-transparent border-none p-0 cursor-pointer"
            >
              <div className="flex items-center gap-2">
                <span className="text-sm" style={{ color: dirColor }}>{isPositive ? '▲' : '▼'}</span>
                <span className="text-xs font-data font-medium" style={{ color: 'var(--text-secondary)' }}>
                  {event.ticker}
                </span>
                <span className="text-[0.65rem]" style={{ color: 'var(--text-muted)' }}>{date}</span>
                <span className="ml-auto text-xs font-data" style={{ color: dirColor }}>
                  {(event.convergence_score || 0).toFixed(2)}
                </span>
              </div>
              <div className="text-[0.7rem] mt-0.5 line-clamp-1" style={{ color: 'var(--text-muted)' }}>
                {event.summary}
              </div>
            </button>
            {isExpanded && (
              <div className="mt-2 pl-6 text-[0.65rem] space-y-1" style={{ color: 'var(--text-muted)' }}>
                <div>KPI: <span style={{ color: 'var(--text-secondary)' }}>{event.kpi_name?.replace(/_/g, ' ')}</span></div>
                <div>Change: <span className="font-data" style={{ color: 'var(--text-secondary)' }}>{event.pct_change?.toFixed(1)}%</span></div>
                <div>
                  Prior: <span className="font-data" style={{ color: 'var(--text-secondary)' }}>{event.prior_value?.toFixed(2)}</span>
                  {' → '}
                  Current: <span className="font-data" style={{ color: 'var(--text-secondary)' }}>{event.current_value?.toFixed(2)}</span>
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};

export default InflectionFeed;
