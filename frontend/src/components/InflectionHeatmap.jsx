import { useState, useEffect } from 'react';
import { getWatchlistInflections } from '../utils/api';
import { Card, CardContent } from '@/components/ui/card';

const InflectionHeatmap = ({ selectedTicker, onSelectTicker, watchlistId }) => {
  const [inflections, setInflections] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!watchlistId) return;
    setLoading(true);
    getWatchlistInflections(watchlistId)
      .then((data) => {
        const byTicker = {};
        for (const event of data) {
          const t = event.ticker;
          if (!byTicker[t] || Math.abs(event.convergence_score) > Math.abs(byTicker[t].convergence_score)) {
            byTicker[t] = event;
          }
        }
        const sorted = Object.values(byTicker).sort(
          (a, b) => Math.abs(b.convergence_score || 0) - Math.abs(a.convergence_score || 0)
        );
        setInflections(sorted);
      })
      .catch(() => setInflections([]))
      .finally(() => setLoading(false));
  }, [watchlistId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-32 text-sm" style={{ color: 'var(--text-muted)' }}>
        Loading inflections…
      </div>
    );
  }

  if (inflections.length === 0) {
    return (
      <div className="text-sm p-4" style={{ color: 'var(--text-muted)' }}>
        No inflection data yet. Analyze tickers in your watchlist to start tracking.
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-1">
      <div className="text-[0.65rem] uppercase tracking-wider mb-2 px-2" style={{ color: 'var(--text-muted)' }}>
        Convergence Radar
      </div>
      {inflections.map((inf) => {
        const score = inf.convergence_score || 0;
        const isPositive = inf.direction === 'positive';
        const barColor = isPositive ? 'var(--success)' : 'var(--danger)';
        const barWidth = Math.min(Math.abs(score) * 100, 100);
        const isSelected = selectedTicker === inf.ticker;
        return (
          <button
            key={inf.ticker}
            onClick={() => onSelectTicker(inf.ticker)}
            className="flex items-center gap-2 px-2 py-1.5 rounded-md text-left transition-colors w-full"
            style={{
              background: isSelected ? 'var(--card)' : 'transparent',
              border: 'none',
              cursor: 'pointer',
            }}
            onMouseEnter={(e) => { if (!isSelected) e.currentTarget.style.background = 'rgba(255,255,255,0.03)'; }}
            onMouseLeave={(e) => { if (!isSelected) e.currentTarget.style.background = 'transparent'; }}
          >
            <span className="text-xs font-data w-12 shrink-0" style={{ color: 'var(--text-secondary)' }}>
              {inf.ticker}
            </span>
            <div className="flex-1 h-3 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.06)' }}>
              <div
                className="h-full rounded-full transition-all"
                style={{ width: `${barWidth}%`, backgroundColor: barColor }}
              />
            </div>
            <span className="text-xs font-data w-12 text-right" style={{ color: barColor }}>
              {isPositive ? '+' : '-'}{score.toFixed(2)}
            </span>
          </button>
        );
      })}
    </div>
  );
};

export default InflectionHeatmap;
