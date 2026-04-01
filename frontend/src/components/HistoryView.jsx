import { useState, useMemo, useEffect } from 'react';
import { useHistory } from '../hooks/useHistory';
import { getCalibrationSummary } from '../utils/api';

const FILTERS = ['All', 'BUY', 'HOLD', 'SELL'];
const REC_COLORS = { BUY: '#17c964', SELL: '#f31260', HOLD: '#f5a524' };

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
      <h2 className="text-lg font-bold text-white/90 mb-4">Analysis History</h2>
      <div className="flex items-center gap-2 mb-4">
        {FILTERS.map((f) => (
          <button key={f} onClick={() => setRecFilter(f)}
            className={`px-3 py-1.5 rounded-md text-[0.75rem] font-medium border-none cursor-pointer ${
              recFilter === f ? 'bg-[rgba(0,111,238,0.1)] text-[#006fee]' : 'bg-white/[0.04] text-white/40 hover:text-white/60'}`}>
            {f}
          </button>
        ))}
        <input type="text" placeholder="Search ticker..." value={search} onChange={(e) => setSearch(e.target.value)}
          className="ml-4 px-3 py-1.5 rounded-md text-[0.75rem] text-white/70 placeholder:text-white/25 outline-none w-[140px]"
          style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.06)' }} />
        <span className="ml-auto text-[0.7rem] text-white/25">{totalCount ?? filteredHistory.length} analyses</span>
      </div>

      {filteredTickers.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-4">
          {filteredTickers.map((t) => (
            <button key={t.ticker} onClick={() => selectTicker(t.ticker)}
              className={`px-3 py-1 rounded-md text-[0.75rem] font-medium border-none cursor-pointer ${
                selectedTicker === t.ticker ? 'bg-[rgba(0,111,238,0.12)] text-[#006fee]' : 'bg-white/[0.03] text-white/40 hover:text-white/60'}`}>
              {t.ticker}<span className="ml-1.5 text-white/20">{t.analysis_count}</span>
            </button>
          ))}
        </div>
      )}

      <div className="flex flex-col gap-0.5">
        {historyLoading && <div className="py-8 text-center text-white/30 text-[0.82rem]">Loading...</div>}
        {!historyLoading && filteredHistory.length === 0 && <div className="py-8 text-center text-white/30 text-[0.82rem]">No analyses found</div>}
        {filteredHistory.map((item) => {
          const rec = (item.recommendation || 'HOLD').toUpperCase();
          const summary = item.executive_summary || item.synthesis || item.summary || '';
          return (
            <button key={item.id} onClick={() => onSelectAnalysis?.(item.ticker || selectedTicker)}
              className="flex items-center py-2.5 px-3 rounded-md text-[0.8rem] text-left w-full border-none cursor-pointer transition-colors hover:bg-white/[0.03]"
              style={{ background: 'rgba(255,255,255,0.02)' }}>
              <span className="flex-shrink-0 w-[70px] font-semibold text-white/85">{item.ticker || selectedTicker}</span>
              <span className="flex-shrink-0 w-[50px] text-[0.75rem] font-semibold" style={{ color: REC_COLORS[rec] || REC_COLORS.HOLD }}>{rec}</span>
              <span className="flex-1 text-white/45 text-[0.78rem] truncate mr-4">{summary}</span>
              <span className="flex-shrink-0 w-[80px] text-right text-[0.72rem] text-white/30 tabular-nums">{formatRelativeTime(item.timestamp)}</span>
            </button>
          );
        })}
      </div>

      {hasMore && !historyLoading && (
        <button onClick={loadMore} className="mt-4 w-full py-2 text-[0.78rem] text-[#006fee]/70 hover:text-[#006fee] bg-transparent border border-white/5 rounded-lg cursor-pointer">
          Load more
        </button>
      )}

      {calibration?.horizons && (
        <div className="mt-8">
          <h3 className="text-[0.85rem] font-semibold text-white/60 mb-3">Calibration (180d)</h3>
          <div className="flex gap-4">
            {Object.entries(calibration.horizons).map(([horizon, data]) => (
              <div key={horizon} className="flex-1 p-4 rounded-lg" style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)' }}>
                <div className="text-[0.65rem] text-white/30 uppercase mb-2">{horizon}</div>
                <div className="text-[1rem] font-bold tabular-nums text-white/80">{((data.directional_accuracy || 0) * 100).toFixed(0)}%</div>
                <div className="text-[0.68rem] text-white/35">accuracy · {data.sample_size || 0} samples</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
