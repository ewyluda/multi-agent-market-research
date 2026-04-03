/**
 * WatchlistView - Full-page watchlist management with mini card grid
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  getWatchlists,
  getWatchlist,
  createWatchlist,
  deleteWatchlist,
  addTickerToWatchlist,
  removeTickerFromWatchlist,
  setWatchlistSchedule,
  API_BASE_URL,
} from '../utils/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

/* ──────── Recommendation badge ──────── */
const RecBadge = ({ rec }) => {
  const variant = { BUY: 'success', HOLD: 'warning', SELL: 'danger' }[rec] || 'secondary';
  return (
    <Badge variant={variant} className="text-[0.65rem] px-1.5 py-0">
      {rec || '—'}
    </Badge>
  );
};

/* ──────── Mini ticker card ──────── */
const MiniCard = ({ ticker, analysis, onRemove, onSelect }) => {
  const a = analysis?.latest_analysis;
  const price = a?.market_data?.current_price;
  const change = a?.market_data?.price_change_pct_1d;

  return (
    <Card
      className="relative cursor-pointer hover:border-white/[0.12] transition-colors"
      onClick={() => onSelect(ticker)}
    >
      <CardContent className="pt-4 pb-3">
        {/* Remove button */}
        <button
          onClick={(e) => { e.stopPropagation(); onRemove(ticker); }}
          className="absolute top-2 right-2 p-0.5 text-[0.75rem] leading-none rounded transition-colors"
          style={{ color: 'var(--text-muted)' }}
          onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--danger)'; }}
          onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--text-muted)'; }}
          title="Remove from watchlist"
        >
          ✕
        </button>

        {/* Ticker */}
        <div className="font-data font-bold text-[0.95rem] mb-1.5" style={{ color: 'var(--text-primary)' }}>
          {ticker}
        </div>

        {/* Rec badge */}
        <div className="mb-2">
          {a ? <RecBadge rec={a.recommendation} /> : (
            <span className="text-[0.7rem]" style={{ color: 'var(--text-muted)' }}>Not analyzed</span>
          )}
        </div>

        {/* Price row */}
        <div className="flex items-center gap-1.5">
          {price != null ? (
            <span className="text-[0.82rem] font-data" style={{ color: 'var(--text-secondary)' }}>
              ${Number(price).toFixed(2)}
            </span>
          ) : (
            <span className="text-[0.75rem]" style={{ color: 'var(--text-muted)' }}>—</span>
          )}
          {change != null && (
            <span
              className="text-[0.72rem] font-data"
              style={{ color: change >= 0 ? 'var(--success)' : 'var(--danger)' }}
            >
              {change >= 0 ? '+' : ''}{Number(change).toFixed(2)}%
            </span>
          )}
        </div>
      </CardContent>
    </Card>
  );
};

/* ──────── Batch progress bar ──────── */
const BatchProgress = ({ results, total }) => {
  if (!results || results.length === 0) return null;
  const done = results.length;
  const pct = Math.round((done / total) * 100);
  const successes = results.filter((r) => r.success).length;
  return (
    <Card className="mt-4">
      <CardContent className="pt-4 pb-3">
        <div className="flex justify-between mb-2">
          <span className="text-[0.75rem] font-semibold" style={{ color: 'var(--text-secondary)' }}>Batch Analysis</span>
          <span className="text-[0.75rem] font-data" style={{ color: 'var(--text-muted)' }}>{done}/{total}</span>
        </div>
        <div className="h-1 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.06)' }}>
          <div
            className="h-full rounded-full transition-all duration-300"
            style={{ width: `${pct}%`, background: 'linear-gradient(90deg, var(--primary), color-mix(in srgb, var(--primary) 60%, white))' }}
          />
        </div>
        <div className="mt-1.5 text-[0.7rem]" style={{ color: 'var(--success)' }}>
          {successes} succeeded{done - successes > 0 && `, ${done - successes} failed`}
        </div>
      </CardContent>
    </Card>
  );
};

/* ──────── Main WatchlistView component ──────── */
const WatchlistView = ({ onSelectTicker }) => {
  const [watchlists, setWatchlists] = useState([]);
  const [activeWatchlist, setActiveWatchlist] = useState(null);
  const [watchlistDetail, setWatchlistDetail] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const [newWatchlistName, setNewWatchlistName] = useState('');
  const [creatingWatchlist, setCreatingWatchlist] = useState(false);
  const [addTickerInput, setAddTickerInput] = useState('');

  const [batchRunning, setBatchRunning] = useState(false);
  const [batchResults, setBatchResults] = useState([]);
  const [batchTotal, setBatchTotal] = useState(0);

  const eventSourceRef = useRef(null);

  const loadWatchlists = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getWatchlists();
      setWatchlists(data.watchlists || []);
    } catch (err) {
      setError(err.message || 'Failed to load watchlists');
    } finally {
      setLoading(false);
    }
  }, []);

  const loadWatchlistDetail = useCallback(async (id) => {
    setLoading(true);
    setError(null);
    try {
      const data = await getWatchlist(id);
      setWatchlistDetail(data);
    } catch (err) {
      setError(err.message || 'Failed to load watchlist');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadWatchlists();
  }, [loadWatchlists]);

  useEffect(() => {
    if (activeWatchlist) {
      loadWatchlistDetail(activeWatchlist);
    }
  }, [activeWatchlist, loadWatchlistDetail]);

  useEffect(() => {
    return () => {
      if (eventSourceRef.current) eventSourceRef.current.close();
    };
  }, []);

  const handleCreateWatchlist = async (e) => {
    e.preventDefault();
    if (!newWatchlistName.trim()) return;
    setCreatingWatchlist(true);
    setError(null);
    try {
      const wl = await createWatchlist(newWatchlistName.trim());
      setNewWatchlistName('');
      await loadWatchlists();
      setActiveWatchlist(wl.id);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to create watchlist');
    } finally {
      setCreatingWatchlist(false);
    }
  };

  const handleDeleteWatchlist = async (id) => {
    try {
      await deleteWatchlist(id);
      if (activeWatchlist === id) {
        setActiveWatchlist(null);
        setWatchlistDetail(null);
      }
      await loadWatchlists();
    } catch (err) {
      setError(err.message || 'Failed to delete watchlist');
    }
  };

  const handleAddTicker = async (e) => {
    e.preventDefault();
    if (!addTickerInput.trim() || !activeWatchlist) return;
    setError(null);
    try {
      await addTickerToWatchlist(activeWatchlist, addTickerInput.trim().toUpperCase());
      setAddTickerInput('');
      await loadWatchlistDetail(activeWatchlist);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to add ticker');
    }
  };

  const handleRemoveTicker = async (ticker) => {
    if (!activeWatchlist) return;
    try {
      await removeTickerFromWatchlist(activeWatchlist, ticker);
      await loadWatchlistDetail(activeWatchlist);
    } catch (err) {
      setError(err.message || 'Failed to remove ticker');
    }
  };

  const handleBatchAnalyze = () => {
    if (!activeWatchlist || batchRunning) return;
    const tickers = watchlistDetail?.tickers?.map((t) => t.ticker) || [];
    if (tickers.length === 0) return;

    setBatchRunning(true);
    setBatchResults([]);
    setBatchTotal(tickers.length);

    const baseUrl = API_BASE_URL ?? '';
    const es = new EventSource(`${baseUrl}/api/watchlists/${activeWatchlist}/analyze`);
    eventSourceRef.current = es;

    es.addEventListener('result', (e) => {
      try { setBatchResults((prev) => [...prev, JSON.parse(e.data)]); } catch { /* ignore */ }
    });

    es.addEventListener('error', (e) => {
      if (e.data) {
        try { setBatchResults((prev) => [...prev, { ...JSON.parse(e.data), success: false }]); } catch { /* ignore */ }
      }
    });

    es.addEventListener('done', () => {
      es.close();
      eventSourceRef.current = null;
      setBatchRunning(false);
      loadWatchlistDetail(activeWatchlist);
      loadWatchlists();
    });

    es.onerror = () => {
      es.close();
      eventSourceRef.current = null;
      setBatchRunning(false);
    };
  };

  // Build analyses map from watchlistDetail
  const analysesMap = {};
  (watchlistDetail?.analyses || []).forEach((a) => {
    analysesMap[a.ticker] = a;
  });
  const allTickers = watchlistDetail?.tickers || [];

  return (
    <div className="flex-1 p-6">
      <h2 className="text-lg font-bold mb-4" style={{ color: 'var(--text-primary)' }}>Watchlists</h2>

      <div style={{ display: 'grid', gridTemplateColumns: '220px 1fr', gap: 24 }}>
        {/* Left: Watchlist list */}
        <div>
          <Card>
            <CardContent className="pt-4">
              <div className="text-[0.65rem] font-bold uppercase tracking-widest mb-2.5" style={{ color: 'var(--text-muted)' }}>
                My Watchlists
              </div>

              {/* Create form */}
              <form onSubmit={handleCreateWatchlist} className="flex gap-1.5 mb-3">
                <Input
                  type="text"
                  value={newWatchlistName}
                  onChange={(e) => setNewWatchlistName(e.target.value)}
                  placeholder="New watchlist..."
                  maxLength={50}
                  disabled={creatingWatchlist}
                  className="flex-1 min-w-0 h-8 text-xs"
                />
                <Button
                  type="submit"
                  size="sm"
                  disabled={creatingWatchlist || !newWatchlistName.trim()}
                  className="h-8 px-3"
                >
                  +
                </Button>
              </form>

              {/* Watchlist items */}
              <div className="flex flex-col gap-1">
                {loading && watchlists.length === 0 ? (
                  <div className="text-center py-4 text-[0.75rem]" style={{ color: 'var(--text-muted)' }}>Loading...</div>
                ) : watchlists.length === 0 ? (
                  <div className="text-center py-4 text-[0.75rem]" style={{ color: 'var(--text-muted)' }}>No watchlists yet</div>
                ) : watchlists.map((wl) => (
                  <div
                    key={wl.id}
                    onClick={() => setActiveWatchlist(wl.id)}
                    className="flex items-center justify-between px-3 py-2 rounded-lg cursor-pointer transition-all"
                    style={{
                      background: activeWatchlist === wl.id ? 'rgba(0,111,238,0.15)' : 'transparent',
                      border: activeWatchlist === wl.id ? '1px solid rgba(0,111,238,0.3)' : '1px solid transparent',
                    }}
                  >
                    <div>
                      <div className="text-[0.82rem] font-semibold" style={{ color: 'var(--text-primary)' }}>{wl.name}</div>
                      <div className="text-[0.65rem]" style={{ color: 'var(--text-muted)' }}>{wl.tickers?.length || 0} tickers</div>
                    </div>
                    <button
                      onClick={(e) => { e.stopPropagation(); handleDeleteWatchlist(wl.id); }}
                      className="text-[0.75rem] p-1 rounded transition-colors"
                      style={{ color: 'var(--text-muted)' }}
                      onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--danger)'; }}
                      onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--text-muted)'; }}
                    >
                      ✕
                    </button>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Right: Watchlist detail */}
        <div>
          {!activeWatchlist ? (
            <Card>
              <CardContent className="pt-12 pb-12 text-center">
                <div className="text-[0.82rem]" style={{ color: 'var(--text-muted)' }}>Select or create a watchlist to get started</div>
              </CardContent>
            </Card>
          ) : (
            <div>
              {/* Auto-analyze schedule */}
              <div className="flex items-center gap-3 mb-4 p-2 rounded-md bg-zinc-800/30">
                <span className="text-xs text-zinc-400">Auto-analyze:</span>
                <select
                  value={watchlistDetail?.auto_analyze_schedule || ''}
                  onChange={async (e) => {
                    const schedule = e.target.value || null;
                    try {
                      await setWatchlistSchedule(activeWatchlist, schedule);
                      setWatchlistDetail((prev) => prev ? { ...prev, auto_analyze_schedule: schedule } : prev);
                    } catch (err) {
                      setError('Failed to update schedule');
                    }
                  }}
                  className="bg-zinc-800 text-zinc-300 text-xs rounded px-2 py-1 border border-zinc-700">
                  <option value="">Off</option>
                  <option value="daily_am">Morning (9 AM ET)</option>
                  <option value="daily_pm">Evening (4 PM ET)</option>
                  <option value="twice_daily">Twice Daily</option>
                </select>
              </div>

              {/* Header: add ticker + batch analyze */}
              <div className="flex items-center gap-2.5 mb-4">
                <form onSubmit={handleAddTicker} className="flex gap-2 flex-1">
                  <Input
                    type="text"
                    value={addTickerInput}
                    onChange={(e) => setAddTickerInput(e.target.value.toUpperCase())}
                    placeholder="Add ticker (e.g. NVDA)"
                    maxLength={5}
                    className="w-40 h-9 text-xs font-data"
                  />
                  <Button type="submit" size="sm" disabled={!addTickerInput.trim()} className="h-9">
                    Add
                  </Button>
                </form>
                <Button
                  variant={batchRunning || allTickers.length === 0 ? 'secondary' : 'default'}
                  size="sm"
                  onClick={handleBatchAnalyze}
                  disabled={batchRunning || allTickers.length === 0}
                  className="h-9"
                >
                  {batchRunning ? 'Analyzing...' : 'Analyze All'}
                </Button>
              </div>

              {/* Ticker mini card grid */}
              {allTickers.length === 0 ? (
                <Card>
                  <CardContent className="pt-8 pb-8 text-center">
                    <div className="text-[0.82rem]" style={{ color: 'var(--text-muted)' }}>
                      Add tickers above to start building your watchlist.
                    </div>
                  </CardContent>
                </Card>
              ) : (
                <div
                  style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}
                  className="xl:grid-cols-4"
                >
                  {allTickers.map(({ ticker }) => (
                    <MiniCard
                      key={ticker}
                      ticker={ticker}
                      analysis={analysesMap[ticker] || null}
                      onRemove={handleRemoveTicker}
                      onSelect={onSelectTicker}
                    />
                  ))}
                </div>
              )}

              {/* Batch progress */}
              {batchRunning && (
                <BatchProgress results={batchResults} total={batchTotal} />
              )}
            </div>
          )}
        </div>
      </div>

      {/* Error */}
      {error && (
        <div
          className="mt-4 px-3.5 py-2.5 rounded-lg text-[0.82rem]"
          style={{
            background: 'rgba(243,18,96,0.1)',
            border: '1px solid rgba(243,18,96,0.3)',
            color: 'var(--danger)',
          }}
        >
          {error}
        </div>
      )}
    </div>
  );
};

export default WatchlistView;
