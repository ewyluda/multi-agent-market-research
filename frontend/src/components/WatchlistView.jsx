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
  API_BASE_URL,
} from '../utils/api';

/* ──────── Recommendation badge ──────── */
const RecBadge = ({ rec }) => {
  const colors = {
    BUY: { bg: 'rgba(23,201,100,0.12)', color: '#17c964', border: 'rgba(23,201,100,0.25)' },
    HOLD: { bg: 'rgba(245,165,36,0.12)', color: '#f5a524', border: 'rgba(245,165,36,0.25)' },
    SELL: { bg: 'rgba(243,18,96,0.12)', color: '#f31260', border: 'rgba(243,18,96,0.25)' },
  };
  const s = colors[rec] || { bg: 'rgba(255,255,255,0.06)', color: 'rgba(255,255,255,0.5)', border: 'rgba(255,255,255,0.1)' };
  return (
    <span style={{
      fontSize: '0.7rem',
      fontWeight: 700,
      padding: '2px 8px',
      borderRadius: 4,
      background: s.bg,
      color: s.color,
      border: `1px solid ${s.border}`,
      letterSpacing: '0.04em',
    }}>
      {rec || '—'}
    </span>
  );
};

/* ──────── Mini ticker card ──────── */
const MiniCard = ({ ticker, analysis, onRemove, onSelect }) => {
  const a = analysis?.latest_analysis;
  const price = a?.market_data?.current_price;
  const change = a?.market_data?.price_change_pct_1d;

  return (
    <div
      style={{
        background: 'rgba(255,255,255,0.02)',
        border: '1px solid rgba(255,255,255,0.06)',
        borderRadius: 10,
        padding: '14px',
        cursor: 'pointer',
        transition: 'border-color 0.15s, background 0.15s',
        position: 'relative',
      }}
      onClick={() => onSelect(ticker)}
      onMouseEnter={(e) => { e.currentTarget.style.borderColor = 'rgba(255,255,255,0.12)'; e.currentTarget.style.background = 'rgba(255,255,255,0.04)'; }}
      onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'rgba(255,255,255,0.06)'; e.currentTarget.style.background = 'rgba(255,255,255,0.02)'; }}
    >
      {/* Remove button */}
      <button
        onClick={(e) => { e.stopPropagation(); onRemove(ticker); }}
        style={{
          position: 'absolute',
          top: 8,
          right: 8,
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          color: 'rgba(255,255,255,0.2)',
          fontSize: '0.75rem',
          lineHeight: 1,
          padding: '2px 4px',
          borderRadius: 4,
          transition: 'color 0.15s',
        }}
        onMouseEnter={(e) => { e.currentTarget.style.color = '#f31260'; }}
        onMouseLeave={(e) => { e.currentTarget.style.color = 'rgba(255,255,255,0.2)'; }}
        title="Remove from watchlist"
      >
        ✕
      </button>

      {/* Ticker */}
      <div style={{ fontFamily: 'monospace', fontWeight: 700, fontSize: '0.95rem', color: 'rgba(255,255,255,0.9)', marginBottom: 6 }}>
        {ticker}
      </div>

      {/* Rec badge */}
      <div style={{ marginBottom: 8 }}>
        {a ? <RecBadge rec={a.recommendation} /> : (
          <span style={{ fontSize: '0.7rem', color: 'rgba(255,255,255,0.25)' }}>Not analyzed</span>
        )}
      </div>

      {/* Price row */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        {price != null ? (
          <span style={{ fontSize: '0.82rem', fontFamily: 'monospace', color: 'rgba(255,255,255,0.7)' }}>
            ${Number(price).toFixed(2)}
          </span>
        ) : (
          <span style={{ fontSize: '0.75rem', color: 'rgba(255,255,255,0.25)' }}>—</span>
        )}
        {change != null && (
          <span style={{
            fontSize: '0.72rem',
            fontFamily: 'monospace',
            color: change >= 0 ? '#17c964' : '#f31260',
          }}>
            {change >= 0 ? '+' : ''}{Number(change).toFixed(2)}%
          </span>
        )}
      </div>
    </div>
  );
};

/* ──────── Batch progress bar ──────── */
const BatchProgress = ({ results, total }) => {
  if (!results || results.length === 0) return null;
  const done = results.length;
  const pct = Math.round((done / total) * 100);
  const successes = results.filter((r) => r.success).length;
  return (
    <div style={{
      background: 'rgba(255,255,255,0.02)',
      border: '1px solid rgba(255,255,255,0.06)',
      borderRadius: 10,
      padding: '14px 16px',
      marginTop: 16,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
        <span style={{ fontSize: '0.75rem', color: 'rgba(255,255,255,0.6)', fontWeight: 600 }}>Batch Analysis</span>
        <span style={{ fontSize: '0.75rem', color: 'rgba(255,255,255,0.4)' }}>{done}/{total}</span>
      </div>
      <div style={{ height: 4, background: 'rgba(255,255,255,0.06)', borderRadius: 2, overflow: 'hidden' }}>
        <div style={{
          height: '100%',
          width: `${pct}%`,
          background: 'linear-gradient(90deg, #006fee, #338ef7)',
          borderRadius: 2,
          transition: 'width 0.3s',
        }} />
      </div>
      <div style={{ marginTop: 6, fontSize: '0.7rem', color: '#17c964' }}>
        {successes} succeeded{done - successes > 0 && `, ${done - successes} failed`}
      </div>
    </div>
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

  const inputStyle = {
    background: 'rgba(255,255,255,0.04)',
    border: '1px solid rgba(255,255,255,0.06)',
    borderRadius: 8,
    padding: '8px 12px',
    fontSize: '0.82rem',
    color: 'rgba(255,255,255,0.9)',
    outline: 'none',
  };

  const btnPrimary = {
    background: '#006fee',
    color: '#fff',
    border: 'none',
    borderRadius: 8,
    padding: '8px 16px',
    fontSize: '0.82rem',
    fontWeight: 600,
    cursor: 'pointer',
    transition: 'opacity 0.15s',
  };

  // Build analyses map from watchlistDetail
  const analysesMap = {};
  (watchlistDetail?.analyses || []).forEach((a) => {
    analysesMap[a.ticker] = a;
  });
  const allTickers = watchlistDetail?.tickers || [];

  return (
    <div className="flex-1 p-6">
      <h2 className="text-lg font-bold text-white/90 mb-4">Watchlists</h2>

      <div style={{ display: 'grid', gridTemplateColumns: '220px 1fr', gap: 24 }}>
        {/* Left: Watchlist list */}
        <div>
          <div style={{
            background: 'rgba(255,255,255,0.02)',
            border: '1px solid rgba(255,255,255,0.06)',
            borderRadius: 12,
            padding: '16px',
          }}>
            <div style={{ fontSize: '0.65rem', fontWeight: 700, color: 'rgba(255,255,255,0.4)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 10 }}>
              My Watchlists
            </div>

            {/* Create form */}
            <form onSubmit={handleCreateWatchlist} style={{ display: 'flex', gap: 6, marginBottom: 12 }}>
              <input
                type="text"
                value={newWatchlistName}
                onChange={(e) => setNewWatchlistName(e.target.value)}
                placeholder="New watchlist..."
                maxLength={50}
                disabled={creatingWatchlist}
                style={{ ...inputStyle, flex: 1, minWidth: 0 }}
              />
              <button
                type="submit"
                disabled={creatingWatchlist || !newWatchlistName.trim()}
                style={{ ...btnPrimary, padding: '8px 12px', opacity: (creatingWatchlist || !newWatchlistName.trim()) ? 0.4 : 1 }}
              >
                +
              </button>
            </form>

            {/* Watchlist items */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {loading && watchlists.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '16px 0', color: 'rgba(255,255,255,0.25)', fontSize: '0.75rem' }}>Loading...</div>
              ) : watchlists.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '16px 0', color: 'rgba(255,255,255,0.25)', fontSize: '0.75rem' }}>No watchlists yet</div>
              ) : watchlists.map((wl) => (
                <div
                  key={wl.id}
                  onClick={() => setActiveWatchlist(wl.id)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '8px 12px',
                    borderRadius: 8,
                    cursor: 'pointer',
                    background: activeWatchlist === wl.id ? 'rgba(0,111,238,0.15)' : 'transparent',
                    border: activeWatchlist === wl.id ? '1px solid rgba(0,111,238,0.3)' : '1px solid transparent',
                    transition: 'all 0.15s',
                  }}
                >
                  <div>
                    <div style={{ fontSize: '0.82rem', fontWeight: 600, color: 'rgba(255,255,255,0.85)' }}>{wl.name}</div>
                    <div style={{ fontSize: '0.65rem', color: 'rgba(255,255,255,0.35)' }}>{wl.tickers?.length || 0} tickers</div>
                  </div>
                  <button
                    onClick={(e) => { e.stopPropagation(); handleDeleteWatchlist(wl.id); }}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'rgba(255,255,255,0.2)', fontSize: '0.75rem', padding: '2px 4px', borderRadius: 4 }}
                    onMouseEnter={(e) => { e.currentTarget.style.color = '#f31260'; }}
                    onMouseLeave={(e) => { e.currentTarget.style.color = 'rgba(255,255,255,0.2)'; }}
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right: Watchlist detail */}
        <div>
          {!activeWatchlist ? (
            <div style={{
              background: 'rgba(255,255,255,0.02)',
              border: '1px solid rgba(255,255,255,0.06)',
              borderRadius: 12,
              padding: '48px',
              textAlign: 'center',
            }}>
              <div style={{ fontSize: '0.82rem', color: 'rgba(255,255,255,0.3)' }}>Select or create a watchlist to get started</div>
            </div>
          ) : (
            <div>
              {/* Header: add ticker + batch analyze */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
                <form onSubmit={handleAddTicker} style={{ display: 'flex', gap: 8, flex: 1 }}>
                  <input
                    type="text"
                    value={addTickerInput}
                    onChange={(e) => setAddTickerInput(e.target.value.toUpperCase())}
                    placeholder="Add ticker (e.g. NVDA)"
                    maxLength={5}
                    style={{ ...inputStyle, width: 160 }}
                  />
                  <button
                    type="submit"
                    disabled={!addTickerInput.trim()}
                    style={{ ...btnPrimary, opacity: !addTickerInput.trim() ? 0.4 : 1 }}
                  >
                    Add
                  </button>
                </form>
                <button
                  onClick={handleBatchAnalyze}
                  disabled={batchRunning || allTickers.length === 0}
                  style={{
                    ...btnPrimary,
                    background: batchRunning || allTickers.length === 0 ? 'rgba(255,255,255,0.06)' : '#006fee',
                    color: batchRunning || allTickers.length === 0 ? 'rgba(255,255,255,0.3)' : '#fff',
                    cursor: batchRunning || allTickers.length === 0 ? 'not-allowed' : 'pointer',
                  }}
                >
                  {batchRunning ? 'Analyzing...' : 'Analyze All'}
                </button>
              </div>

              {/* Ticker mini card grid */}
              {allTickers.length === 0 ? (
                <div style={{
                  background: 'rgba(255,255,255,0.02)',
                  border: '1px solid rgba(255,255,255,0.06)',
                  borderRadius: 12,
                  padding: '32px',
                  textAlign: 'center',
                  color: 'rgba(255,255,255,0.3)',
                  fontSize: '0.82rem',
                }}>
                  Add tickers above to start building your watchlist.
                </div>
              ) : (
                <div style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(3, 1fr)',
                  gap: 12,
                }}}
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
        <div style={{
          marginTop: 16,
          padding: '10px 14px',
          background: 'rgba(243,18,96,0.1)',
          border: '1px solid rgba(243,18,96,0.3)',
          borderRadius: 8,
          color: '#f31260',
          fontSize: '0.82rem',
        }}>
          {error}
        </div>
      )}
    </div>
  );
};

export default WatchlistView;
