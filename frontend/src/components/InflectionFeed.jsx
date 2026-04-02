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

  if (loading) return <div className="text-zinc-500 text-sm p-3">Loading feed…</div>;
  if (events.length === 0) return <div className="text-zinc-500 text-sm p-3">No inflection events yet.</div>;

  return (
    <div className="flex flex-col gap-1 overflow-y-auto">
      <div className="text-[0.65rem] uppercase tracking-wider text-zinc-500 mb-1 px-3 pt-2">Inflection Feed</div>
      {events.map((event) => {
        const isPositive = event.direction === 'positive';
        const isExpanded = expandedId === event.id;
        const date = event.detected_at ? new Date(event.detected_at).toLocaleDateString() : '';
        return (
          <div key={event.id} className="px-3 py-2 hover:bg-zinc-800/30 rounded-md transition-colors">
            <button onClick={() => { setExpandedId(isExpanded ? null : event.id); onSelectTicker?.(event.ticker); }} className="w-full text-left">
              <div className="flex items-center gap-2">
                <span className={`text-sm ${isPositive ? 'text-emerald-400' : 'text-red-400'}`}>{isPositive ? '\u25B2' : '\u25BC'}</span>
                <span className="text-xs font-mono text-zinc-300 font-medium">{event.ticker}</span>
                <span className="text-[0.65rem] text-zinc-500">{date}</span>
                <span className={`ml-auto text-xs font-mono ${isPositive ? 'text-emerald-400' : 'text-red-400'}`}>{(event.convergence_score || 0).toFixed(2)}</span>
              </div>
              <div className="text-[0.7rem] text-zinc-400 mt-0.5 line-clamp-1">{event.summary}</div>
            </button>
            {isExpanded && (
              <div className="mt-2 pl-6 text-[0.65rem] text-zinc-500 space-y-1">
                <div>KPI: <span className="text-zinc-300">{event.kpi_name?.replace(/_/g, ' ')}</span></div>
                <div>Change: <span className="text-zinc-300">{event.pct_change?.toFixed(1)}%</span></div>
                <div>Prior: <span className="text-zinc-300">{event.prior_value?.toFixed(2)}</span>{' \u2192 '}Current: <span className="text-zinc-300">{event.current_value?.toFixed(2)}</span></div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};

export default InflectionFeed;
