import { useState, useMemo, useEffect } from 'react';
import { useHistory } from '../hooks/useHistory';
import { getCalibrationSummary } from '../utils/api';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

const FILTERS = ['All', 'BUY', 'HOLD', 'SELL'];

const REC_VARIANT = { BUY: 'success', SELL: 'danger', HOLD: 'warning' };

function formatRelativeTime(ts) {
  if (!ts) return '';
  const diff = Date.now() - new Date(ts).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

export default function HistoryView({ onSelectAnalysis }) {
  const {
    tickers,
    tickersLoading,
    selectedTicker,
    selectTicker,
    history,
    historyLoading,
    totalCount,
    hasMore,
    page,
    pageSize,
    goToPage,
    filters,
    applyFilters,
  } = useHistory();
  const [recFilter, setRecFilter] = useState('All');
  const [search, setSearch] = useState('');
  const [calibration, setCalibration] = useState(null);

  useEffect(() => {
    getCalibrationSummary(180).then((r) => setCalibration(r?.data)).catch(() => {});
  }, []);

  const filteredTickers = useMemo(() => {
    let list = tickers || [];
    if (search) list = list.filter((t) => t.ticker.includes(search.toUpperCase()));
    return list;
  }, [tickers, search]);

  const filteredHistory = useMemo(() => {
    if (recFilter === 'All') return history;
    return (history || []).filter((h) => (h.recommendation || '').toUpperCase() === recFilter);
  }, [history, recFilter]);

  const loadMore = () => {
    if (hasMore) goToPage(page + 1);
  };

  return (
    <div className="flex-1 p-6">
      <h2 className="text-lg font-bold mb-4" style={{ color: 'var(--text-primary)' }}>Analysis History</h2>

      <div className="flex items-center gap-2 mb-4">
        {FILTERS.map((f) => (
          <Button
            key={f}
            size="sm"
            variant={recFilter === f ? 'default' : 'secondary'}
            onClick={() => setRecFilter(f)}
            className="text-xs h-7 px-3"
          >
            {f}
          </Button>
        ))}
        <Input
          type="text"
          placeholder="Search ticker..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="ml-4 h-7 text-xs w-[140px]"
        />
        <span className="ml-auto text-[0.7rem]" style={{ color: 'var(--text-muted)' }}>
          {totalCount ?? filteredHistory.length} analyses
        </span>
      </div>

      {filteredTickers.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-4">
          {filteredTickers.map((t) => (
            <Button
              key={t.ticker}
              size="sm"
              variant={selectedTicker === t.ticker ? 'default' : 'secondary'}
              onClick={() => selectTicker(t.ticker)}
              className="text-xs h-6 px-3"
            >
              {t.ticker}
              <span className="ml-1.5 opacity-50">{t.analysis_count}</span>
            </Button>
          ))}
        </div>
      )}

      <div className="flex flex-col gap-0.5">
        {historyLoading && (
          <div className="py-8 text-center text-[0.82rem]" style={{ color: 'var(--text-muted)' }}>Loading...</div>
        )}
        {!historyLoading && filteredHistory.length === 0 && (
          <div className="py-8 text-center text-[0.82rem]" style={{ color: 'var(--text-muted)' }}>No analyses found</div>
        )}
        {filteredHistory.map((item) => {
          const rec = (item.recommendation || 'HOLD').toUpperCase();
          const summary = item.executive_summary || item.synthesis || item.summary || '';
          return (
            <button
              key={item.id}
              onClick={() => onSelectAnalysis?.(item.ticker || selectedTicker)}
              className="flex items-center py-2.5 px-3 rounded-md text-[0.8rem] text-left w-full border-none cursor-pointer transition-colors hover:bg-white/[0.03]"
              style={{ background: 'rgba(255,255,255,0.02)' }}
            >
              <span className="flex-shrink-0 w-[70px] font-semibold font-data" style={{ color: 'var(--text-primary)' }}>
                {item.ticker || selectedTicker}
              </span>
              <span className="flex-shrink-0 w-[60px]">
                <Badge variant={REC_VARIANT[rec] || 'secondary'} className="text-[0.65rem] px-1.5 py-0">
                  {rec}
                </Badge>
              </span>
              <span className="flex-1 text-[0.78rem] truncate mr-4" style={{ color: 'var(--text-muted)' }}>{summary}</span>
              <span className="flex-shrink-0 w-[80px] text-right text-[0.72rem] font-data tabular-nums" style={{ color: 'var(--text-muted)' }}>
                {formatRelativeTime(item.timestamp)}
              </span>
            </button>
          );
        })}
      </div>

      {hasMore && !historyLoading && (
        <Button
          variant="outline"
          onClick={loadMore}
          className="mt-4 w-full text-[0.78rem]"
        >
          Load more
        </Button>
      )}

      {calibration?.horizons && (
        <div className="mt-8">
          <h3 className="text-[0.85rem] font-semibold mb-3" style={{ color: 'var(--text-muted)' }}>Calibration (180d)</h3>
          <div className="flex gap-4">
            {Object.entries(calibration.horizons).map(([horizon, data]) => (
              <Card key={horizon} className="flex-1">
                <CardContent className="pt-4">
                  <div className="text-[0.65rem] uppercase mb-2" style={{ color: 'var(--text-muted)' }}>{horizon}</div>
                  <div className="text-[1rem] font-bold font-data tabular-nums" style={{ color: 'var(--text-primary)' }}>
                    {((data.directional_accuracy || 0) * 100).toFixed(0)}%
                  </div>
                  <div className="text-[0.68rem]" style={{ color: 'var(--text-muted)' }}>
                    accuracy · {data.sample_size || 0} samples
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
