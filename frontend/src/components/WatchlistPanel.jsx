/**
 * WatchlistPanel - Multi-ticker watchlist management and comparison
 */

import React, { useEffect, useState, useCallback, useRef } from 'react';
import {
  getWatchlists,
  getWatchlist,
  getWatchlistOpportunities,
  createWatchlist,
  deleteWatchlist,
  addTickerToWatchlist,
  removeTickerFromWatchlist,
  analyzeTickerAPI,
  API_BASE_URL,
} from '../utils/api';
import {
  ArrowLeftIcon,
  LoadingSpinner,
  SearchIcon,
  TrashIcon,
  ChartBarIcon,
  TrendingUpIcon,
  TrendingDownIcon,
  PulseIcon,
  ClockIcon,
  CheckCircleIcon,
  XCircleIcon,
} from './Icons';

/* ──────── Recommendation badge ──────── */
const RecBadge = ({ rec }) => {
  const s = {
    BUY: 'bg-success/15 text-success-400 border-success/25',
    HOLD: 'bg-warning/15 text-warning-400 border-warning/25',
    SELL: 'bg-danger/15 text-danger-400 border-danger/25',
  };
  return (
    <span className={`text-[11px] font-semibold px-2 py-0.5 rounded border ${s[rec] || 'bg-gray-500/15 text-gray-400 border-gray-500/25'}`}>
      {rec || '—'}
    </span>
  );
};

/* ──────── Score visual ──────── */
const ScorePill = ({ score }) => {
  if (score == null) return <span className="text-xs text-gray-500">—</span>;
  const color = score > 30 ? 'text-success-400' : score > -30 ? 'text-warning-400' : 'text-danger-400';
  return <span className={`text-xs font-bold tabular-nums ${color}`}>{score > 0 ? '+' : ''}{score}</span>;
};

const formatUsd = (value) => {
  if (value == null || Number.isNaN(Number(value))) return '—';
  const numeric = Number(value);
  if (numeric >= 1_000_000_000) return `$${(numeric / 1_000_000_000).toFixed(2)}B`;
  if (numeric >= 1_000_000) return `$${(numeric / 1_000_000).toFixed(2)}M`;
  if (numeric >= 1_000) return `$${(numeric / 1_000).toFixed(1)}K`;
  return `$${numeric.toFixed(0)}`;
};

/* ──────── Ticker row in watchlist ──────── */
const TickerRow = ({ ticker, analysis, onRemove, onAnalyze, analyzing }) => {
  const a = analysis?.latest_analysis;
  return (
    <div className="grid grid-cols-12 gap-2 px-3 py-3 items-center hover:bg-white/[0.02] transition-colors rounded group">
      <div className="col-span-2">
        <span className="font-mono text-sm font-semibold">{ticker}</span>
      </div>
      <div className="col-span-2">
        {a ? <RecBadge rec={a.recommendation} /> : <span className="text-[11px] text-gray-500">Not analyzed</span>}
      </div>
      <div className="col-span-2">
        <ScorePill score={a?.confidence_score != null ? Math.round(a.confidence_score * 100) : null} />
      </div>
      <div className="col-span-3">
        {a?.timestamp ? (
          <span className="text-[11px] text-gray-400">
            {new Date(a.timestamp).toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
          </span>
        ) : (
          <span className="text-[11px] text-gray-600">—</span>
        )}
      </div>
      <div className="col-span-3 flex justify-end gap-2 transition-opacity">
        <button
          onClick={() => onAnalyze(ticker)}
          disabled={analyzing}
          className="text-[11px] px-2.5 py-1.5 rounded-md bg-primary/15 text-accent-blue hover:bg-primary/25 transition-colors disabled:opacity-40"
        >
          {analyzing ? 'Running...' : 'Analyze'}
        </button>
        <button
          onClick={() => onRemove(ticker)}
          className="p-1.5 rounded-md text-gray-600 hover:text-danger-400 hover:bg-danger/10 transition-all"
          title="Remove from watchlist"
        >
          <TrashIcon className="w-3 h-3" />
        </button>
      </div>
    </div>
  );
};

/* ──────── Comparison table ──────── */
const ComparisonTable = ({ analyses }) => {
  if (!analyses || analyses.length === 0) return null;

  const withData = analyses.filter((a) => a.latest_analysis);
  if (withData.length < 2) return null;

  const sorted = [...withData].sort((a, b) => {
    const scoreA = a.latest_analysis?.confidence_score ?? 0;
    const scoreB = b.latest_analysis?.confidence_score ?? 0;
    return scoreB - scoreA;
  });

  return (
    <div className="glass-card-elevated rounded-xl p-5 mt-4">
      <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3 flex items-center space-x-2">
        <ChartBarIcon className="w-3.5 h-3.5 text-accent-purple" />
        <span>Comparison</span>
      </h3>

      <div className="grid grid-cols-12 gap-2 px-3 py-2 text-[10px] font-semibold text-gray-500 uppercase tracking-wider border-b border-white/5">
        <div className="col-span-2">Ticker</div>
        <div className="col-span-2">Signal</div>
        <div className="col-span-2">Confidence</div>
        <div className="col-span-2">Sentiment</div>
        <div className="col-span-2">Duration</div>
        <div className="col-span-2">When</div>
      </div>

      <div className="divide-y divide-white/[0.03]">
        {sorted.map(({ ticker, latest_analysis: a }) => (
          <div key={ticker} className="grid grid-cols-12 gap-2 px-3 py-2.5 items-center">
            <div className="col-span-2 font-mono text-sm font-semibold">{ticker}</div>
            <div className="col-span-2"><RecBadge rec={a.recommendation} /></div>
            <div className="col-span-2">
              <span className="text-xs font-semibold tabular-nums">{a.confidence_score != null ? `${Math.round(a.confidence_score * 100)}%` : '—'}</span>
            </div>
            <div className="col-span-2">
              {a.overall_sentiment_score != null ? (
                <span className={`text-xs font-semibold tabular-nums ${a.overall_sentiment_score > 0 ? 'text-success-400' : a.overall_sentiment_score < 0 ? 'text-danger-400' : 'text-gray-400'}`}>
                  {a.overall_sentiment_score > 0 ? '+' : ''}{a.overall_sentiment_score.toFixed(2)}
                </span>
              ) : (
                <span className="text-xs text-gray-500">—</span>
              )}
            </div>
            <div className="col-span-2 text-xs text-gray-400 tabular-nums">{a.duration_seconds?.toFixed(1)}s</div>
            <div className="col-span-2 text-[11px] text-gray-500">
              {new Date(a.timestamp).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

const OpportunitiesTable = ({ opportunities }) => {
  if (!opportunities || opportunities.length === 0) return null;

  return (
    <div className="glass-card-elevated rounded-xl p-5 mt-4">
      <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3 flex items-center space-x-2">
        <TrendingUpIcon className="w-3.5 h-3.5 text-accent-blue" />
        <span>Ranked Opportunities</span>
      </h3>

      <div className="grid grid-cols-12 gap-2 px-3 py-2 text-[10px] font-semibold text-gray-500 uppercase tracking-wider border-b border-white/5">
        <div className="col-span-2">Ticker</div>
        <div className="col-span-2">EV 7D</div>
        <div className="col-span-2">Cal Conf</div>
        <div className="col-span-2">Quality</div>
        <div className="col-span-2">Capacity</div>
        <div className="col-span-2">Action</div>
      </div>

      <div className="divide-y divide-white/[0.03]">
        {opportunities.map((item) => (
          <div key={`${item.ticker}-${item.analysis_id}`} className="grid grid-cols-12 gap-2 px-3 py-2.5 items-center">
            <div className="col-span-2 font-mono text-sm font-semibold">{item.ticker}</div>
            <div className="col-span-2 text-xs font-mono tabular-nums text-gray-200">
              {item.ev_score_7d != null ? Number(item.ev_score_7d).toFixed(2) : '—'}
            </div>
            <div className="col-span-2 text-xs font-mono tabular-nums text-gray-200">
              {item.confidence_calibrated != null ? `${Math.round(Number(item.confidence_calibrated) * 100)}%` : '—'}
            </div>
            <div className="col-span-2 text-xs font-mono tabular-nums text-gray-200">
              {item.data_quality_score != null ? Number(item.data_quality_score).toFixed(1) : '—'}
            </div>
            <div className="col-span-2 text-xs font-mono tabular-nums text-gray-200">
              {formatUsd(item.capacity_usd)}
            </div>
            <div className="col-span-2">
              <span className="text-[11px] px-2 py-0.5 rounded border bg-accent-blue/10 border-accent-blue/20 text-accent-blue uppercase">
                {item.recommended_action || item.recommendation || 'hold'}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

/* ──────── Batch analysis progress ──────── */
const BatchProgress = ({ results, total }) => {
  if (!results || results.length === 0) return null;
  const done = results.length;
  const pct = Math.round((done / total) * 100);
  const successes = results.filter((r) => r.success).length;

  return (
    <div className="glass-card-elevated rounded-xl p-4 mt-4 animate-fade-in">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-semibold text-gray-300">Batch Analysis</span>
        <span className="text-xs text-gray-400">{done}/{total} complete</span>
      </div>
      <div className="w-full h-1.5 bg-dark-inset rounded-full overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-primary-600 to-primary rounded-full transition-all duration-300"
          style={{ width: `${pct}%` }}
        />
      </div>
      <div className="flex items-center space-x-3 mt-2">
        <span className="flex items-center space-x-1 text-[11px] text-success-400">
          <CheckCircleIcon className="w-3 h-3" /><span>{successes} succeeded</span>
        </span>
        {done - successes > 0 && (
          <span className="flex items-center space-x-1 text-[11px] text-danger-400">
            <XCircleIcon className="w-3 h-3" /><span>{done - successes} failed</span>
          </span>
        )}
      </div>
    </div>
  );
};

/* ──────── Main WatchlistPanel component ──────── */
const WatchlistPanel = ({ onBack }) => {
  const [watchlists, setWatchlists] = useState([]);
  const [activeWatchlist, setActiveWatchlist] = useState(null);
  const [watchlistDetail, setWatchlistDetail] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Form state
  const [newWatchlistName, setNewWatchlistName] = useState('');
  const [addTickerInput, setAddTickerInput] = useState('');
  const [creatingWatchlist, setCreatingWatchlist] = useState(false);

  // Batch analysis state
  const [batchRunning, setBatchRunning] = useState(false);
  const [batchResults, setBatchResults] = useState([]);
  const [batchTotal, setBatchTotal] = useState(0);
  const [analyzingTicker, setAnalyzingTicker] = useState(null);
  const [opportunities, setOpportunities] = useState([]);

  const eventSourceRef = useRef(null);

  // Load watchlists
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

  // Load watchlist detail
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

  const loadOpportunities = useCallback(async (id) => {
    if (!id) return;
    try {
      const data = await getWatchlistOpportunities(id, { limit: 20 });
      setOpportunities(data?.opportunities || []);
    } catch {
      setOpportunities([]);
    }
  }, []);

  useEffect(() => {
    loadWatchlists();
  }, [loadWatchlists]);

  useEffect(() => {
    if (activeWatchlist) {
      loadWatchlistDetail(activeWatchlist);
      loadOpportunities(activeWatchlist);
    }
  }, [activeWatchlist, loadWatchlistDetail, loadOpportunities]);

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
        setOpportunities([]);
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
      await loadOpportunities(activeWatchlist);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to add ticker');
    }
  };

  const handleRemoveTicker = async (ticker) => {
    if (!activeWatchlist) return;
    try {
      await removeTickerFromWatchlist(activeWatchlist, ticker);
      await loadWatchlistDetail(activeWatchlist);
      await loadOpportunities(activeWatchlist);
    } catch (err) {
      setError(err.message || 'Failed to remove ticker');
    }
  };

  const handleAnalyzeSingle = async (ticker) => {
    setAnalyzingTicker(ticker);
    try {
      await analyzeTickerAPI(ticker);
      if (activeWatchlist) {
        await loadWatchlistDetail(activeWatchlist);
        await loadOpportunities(activeWatchlist);
      }
    } catch (err) {
      setError(`Analysis failed for ${ticker}: ${err.message}`);
    } finally {
      setAnalyzingTicker(null);
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
      try {
        const data = JSON.parse(e.data);
        setBatchResults((prev) => [...prev, data]);
      } catch {
        // ignore malformed event payload
      }
    });

    es.addEventListener('error', (e) => {
      if (e.data) {
        try {
          const data = JSON.parse(e.data);
          setBatchResults((prev) => [...prev, { ...data, success: false }]);
        } catch {
          // ignore malformed event payload
        }
      }
    });

    es.addEventListener('done', (event) => {
      if (event?.data) {
        try {
          const payload = JSON.parse(event.data);
          if (Array.isArray(payload?.opportunities)) {
            setOpportunities(payload.opportunities);
          }
        } catch {
          // ignored: best-effort parse of final SSE payload
        }
      }
      es.close();
      eventSourceRef.current = null;
      setBatchRunning(false);
      // Refresh data
      loadWatchlistDetail(activeWatchlist);
      loadWatchlists();
      loadOpportunities(activeWatchlist);
    });

    es.onerror = () => {
      es.close();
      eventSourceRef.current = null;
      setBatchRunning(false);
    };
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  return (
    <div className="animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center space-x-3">
          <button
            onClick={onBack}
            className="p-2.5 rounded-lg border border-white/5 text-gray-400 hover:text-white hover:border-white/15 transition-all"
          >
            <ArrowLeftIcon className="w-4 h-4" />
          </button>
          <div className="flex items-center space-x-2">
            <ChartBarIcon className="w-5 h-5 text-accent-purple" />
            <h2 className="text-lg font-bold tracking-tight">Watchlists</h2>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-12 gap-6">
        {/* Left sidebar - Watchlist list */}
        <div className="col-span-3">
          <div className="glass-card-elevated rounded-xl p-4">
            <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
              My Watchlists
            </h3>

            {/* Create watchlist form */}
            <form onSubmit={handleCreateWatchlist} className="mb-3">
              <div className="flex space-x-2">
                <input
                  type="text"
                  value={newWatchlistName}
                  onChange={(e) => setNewWatchlistName(e.target.value)}
                  placeholder="New watchlist..."
                  className="flex-1 px-3 py-2 bg-dark-inset border border-dark-border rounded-md text-xs focus:outline-none focus:ring-1 focus:ring-primary/30 focus:border-primary/40 transition-all"
                  maxLength={50}
                  disabled={creatingWatchlist}
                />
                <button
                  type="submit"
                  disabled={creatingWatchlist || !newWatchlistName.trim()}
                  className="px-3 py-2 bg-primary/15 text-accent-blue text-xs rounded-md hover:bg-primary/25 disabled:opacity-40 transition-all"
                >
                  {creatingWatchlist ? '...' : 'Add'}
                </button>
              </div>
            </form>

            {loading && watchlists.length === 0 ? (
              <div className="flex items-center justify-center py-6">
                <LoadingSpinner size={16} className="text-gray-500" />
              </div>
            ) : watchlists.length === 0 ? (
              <p className="text-xs text-gray-500 text-center py-4">
                No watchlists yet. Create one above.
              </p>
            ) : (
              <div className="space-y-1">
                {watchlists.map((wl) => (
                  <div
                    key={wl.id}
                    className={`flex items-center justify-between px-3.5 py-2.5 rounded-lg cursor-pointer transition-all group ${
                      activeWatchlist === wl.id
                        ? 'bg-primary/15 border border-primary/30 text-white'
                      : 'bg-dark-card hover:bg-dark-card-hover border border-transparent text-gray-300'
                    }`}
                    onClick={() => setActiveWatchlist(wl.id)}
                  >
                    <div>
                      <div className="text-xs font-semibold">{wl.name}</div>
                      <div className="text-[10px] text-gray-500">{wl.tickers?.length || 0} tickers</div>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDeleteWatchlist(wl.id);
                      }}
                      className="p-1.5 rounded text-gray-600 hover:text-danger-400 hover:bg-danger/10 opacity-60 group-hover:opacity-100 transition-all"
                    >
                      <TrashIcon className="w-3 h-3" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right panel - Watchlist detail */}
        <div className="col-span-9">
          {!activeWatchlist ? (
            <div className="glass-card-elevated rounded-xl p-12 text-center">
              <ChartBarIcon className="w-10 h-10 text-gray-600 mx-auto mb-3" />
              <p className="text-sm text-gray-500">Select or create a watchlist to get started</p>
            </div>
          ) : loading && !watchlistDetail ? (
            <div className="glass-card-elevated rounded-xl p-12 text-center">
              <LoadingSpinner size={20} className="text-gray-500 mx-auto" />
            </div>
          ) : watchlistDetail ? (
            <div className="space-y-4">
              {/* Watchlist header */}
              <div className="glass-card-elevated rounded-xl p-5">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <h3 className="text-sm font-bold">{watchlistDetail.name}</h3>
                    <span className="text-[11px] text-gray-500">{watchlistDetail.tickers?.length || 0} tickers</span>
                  </div>
                  <div className="flex items-center space-x-2">
                    {/* Add ticker form */}
                    <form onSubmit={handleAddTicker} className="flex space-x-2">
                      <input
                        type="text"
                        value={addTickerInput}
                        onChange={(e) => setAddTickerInput(e.target.value.toUpperCase())}
                        placeholder="Add ticker..."
                        className="w-32 px-3 py-2 bg-dark-inset border border-dark-border rounded-md text-xs focus:outline-none focus:ring-1 focus:ring-primary/30 uppercase"
                        maxLength={5}
                      />
                      <button
                        type="submit"
                        disabled={!addTickerInput.trim()}
                        className="px-3 py-2 bg-primary/15 text-accent-blue text-xs rounded-md hover:bg-primary/25 disabled:opacity-40 transition-all"
                      >
                        Add
                      </button>
                    </form>
                    {/* Batch analyze */}
                    <button
                      onClick={handleBatchAnalyze}
                      disabled={batchRunning || (watchlistDetail.tickers?.length || 0) === 0}
                      className="flex items-center space-x-1.5 px-4 py-2 bg-gradient-to-r from-primary-600 to-primary hover:from-primary hover:to-primary-400 disabled:from-zinc-700 disabled:to-zinc-700 disabled:cursor-not-allowed rounded-md text-[11px] font-medium transition-all"
                    >
                      {batchRunning ? (
                        <><LoadingSpinner size={12} /><span>Running...</span></>
                      ) : (
                        <><PulseIcon className="w-3 h-3" /><span>Analyze All</span></>
                      )}
                    </button>
                  </div>
                </div>

                {/* Ticker table header */}
                {watchlistDetail.tickers?.length > 0 && (
                  <>
                    <div className="grid grid-cols-12 gap-2 px-3 py-2 text-[10px] font-semibold text-gray-500 uppercase tracking-wider border-b border-white/5">
                      <div className="col-span-2">Ticker</div>
                      <div className="col-span-2">Signal</div>
                      <div className="col-span-2">Confidence</div>
                      <div className="col-span-3">Last Analyzed</div>
                      <div className="col-span-3 text-right">Actions</div>
                    </div>

                    <div className="divide-y divide-white/[0.03]">
                      {(watchlistDetail.analyses || []).map(({ ticker, latest_analysis }) => (
                        <TickerRow
                          key={ticker}
                          ticker={ticker}
                          analysis={{ latest_analysis }}
                          onRemove={handleRemoveTicker}
                          onAnalyze={handleAnalyzeSingle}
                          analyzing={analyzingTicker === ticker}
                        />
                      ))}
                      {/* Tickers with no analyses entry (shouldn't happen but handle gracefully) */}
                      {watchlistDetail.tickers
                        .filter((t) => !watchlistDetail.analyses?.some((a) => a.ticker === t.ticker))
                        .map((t) => (
                          <TickerRow
                            key={t.ticker}
                            ticker={t.ticker}
                            analysis={null}
                            onRemove={handleRemoveTicker}
                            onAnalyze={handleAnalyzeSingle}
                            analyzing={analyzingTicker === t.ticker}
                          />
                        ))}
                    </div>
                  </>
                )}

                {(!watchlistDetail.tickers || watchlistDetail.tickers.length === 0) && (
                  <div className="text-center py-8">
                    <p className="text-xs text-gray-500">Add tickers above to start building your watchlist.</p>
                  </div>
                )}
              </div>

              {/* Batch analysis progress */}
              {batchRunning && (
                <BatchProgress results={batchResults} total={batchTotal} />
              )}

              {/* Comparison table */}
              <ComparisonTable analyses={watchlistDetail.analyses} />
              <OpportunitiesTable opportunities={opportunities} />
            </div>
          ) : null}

          {/* Error */}
          {error && (
            <div className="mt-4 p-3 bg-danger/10 border border-danger/30 rounded-lg text-danger-400 text-sm animate-fade-in">
              {error}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default WatchlistPanel;
