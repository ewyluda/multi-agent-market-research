/**
 * HistoryDashboard - Browse past analyses with trends and filtering
 */

import React, { useEffect, useState, useMemo } from 'react';
import { useHistory } from '../hooks/useHistory';
import { getCalibrationSummary } from '../utils/api';
import {
  HistoryIcon,
  FilterIcon,
  TrashIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  ArrowLeftIcon,
  TrendingUpIcon,
  TrendingDownIcon,
  ClockIcon,
  LoadingSpinner,
  SearchIcon,
} from './Icons';

/* ──────── Recommendation badge ──────── */
const RecommendationBadge = ({ rec }) => {
  const styles = {
    BUY: 'bg-success/15 text-success-400 border-success/25',
    HOLD: 'bg-warning/15 text-warning-400 border-warning/25',
    SELL: 'bg-danger/15 text-danger-400 border-danger/25',
  };
  return (
    <span className={`text-[11px] font-semibold px-2 py-0.5 rounded border ${styles[rec] || 'bg-gray-500/15 text-gray-400 border-gray-500/25'}`}>
      {rec || 'N/A'}
    </span>
  );
};

/* ──────── Score bar (visual) ──────── */
const ScoreBar = ({ score }) => {
  if (score == null) return <span className="text-xs text-gray-500">—</span>;
  const normalized = ((score + 100) / 200) * 100; // -100..100 → 0..100
  const color = score > 30 ? 'bg-success' : score > -30 ? 'bg-warning' : 'bg-danger';
  return (
    <div className="flex items-center space-x-2">
      <div className="w-16 h-1.5 bg-dark-inset rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full transition-all`} style={{ width: `${Math.max(2, normalized)}%` }} />
      </div>
      <span className="text-xs font-semibold tabular-nums w-8 text-right">{score}</span>
    </div>
  );
};

/* ──────── Confidence display ──────── */
const ConfidencePill = ({ confidence }) => {
  if (confidence == null) return <span className="text-xs text-gray-500">—</span>;
  const pct = Math.round(confidence * 100);
  return (
    <span className="text-xs font-semibold tabular-nums">
      {pct}%
    </span>
  );
};

/* ──────── Outcome chips ──────── */
const OutcomeChips = ({ outcomes }) => {
  if (!outcomes || typeof outcomes !== 'object') {
    return <span className="text-xs text-gray-500">—</span>;
  }

  const order = ['1d', '7d', '30d'];
  const styleFor = (status) => {
    if (status === 'complete') return 'bg-success/15 text-success-400 border-success/25';
    if (status === 'skipped') return 'bg-gray-500/15 text-gray-400 border-gray-500/25';
    return 'bg-warning/15 text-warning-400 border-warning/25';
  };

  return (
    <div className="flex items-center gap-1.5 flex-wrap">
      {order.map((horizon) => {
        const status = outcomes?.[horizon]?.status || 'pending';
        return (
          <span
            key={horizon}
            className={`text-[10px] px-1.5 py-0.5 rounded border font-semibold ${styleFor(status)}`}
            title={`${horizon}: ${status}`}
          >
            {horizon}:{status[0].toUpperCase()}
          </span>
        );
      })}
    </div>
  );
};

const CalibrationSummaryCards = ({ summary, loading }) => {
  const horizons = ['1d', '7d', '30d'];

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
      {horizons.map((horizon) => {
        const row = summary?.horizons?.[horizon] || null;
        const accuracy = row?.directional_accuracy != null ? `${(row.directional_accuracy * 100).toFixed(1)}%` : '—';
        const brier = row?.brier_score != null ? Number(row.brier_score).toFixed(3) : '—';
        const sample = row?.sample_size ?? 0;

        return (
          <div key={horizon} className="bg-dark-inset border border-white/5 rounded-lg p-3">
            <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-2">{horizon} Calibration</div>
            {loading ? (
              <div className="flex justify-center py-3">
                <LoadingSpinner size={12} className="text-gray-500" />
              </div>
            ) : (
              <div className="space-y-1 text-xs">
                <div className="flex justify-between">
                  <span className="text-gray-500">Accuracy</span>
                  <span className="font-mono text-gray-200">{accuracy}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Brier</span>
                  <span className="font-mono text-gray-200">{brier}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Sample</span>
                  <span className="font-mono text-gray-200">{sample}</span>
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};

/* ──────── Ticker selector chip ──────── */
const TickerChip = ({ ticker, isActive, count, recommendation, onClick }) => {
  const borderColor = {
    BUY: 'border-success/30',
    HOLD: 'border-warning/30',
    SELL: 'border-danger/30',
  }[recommendation] || 'border-white/10';

  return (
    <button
      onClick={() => onClick(ticker.ticker)}
      className={`flex items-center space-x-2 px-3 py-2 rounded-lg border text-left transition-all ${
        isActive
          ? 'bg-primary/15 border-primary/40 text-white'
          : `bg-dark-card hover:bg-dark-card-hover ${borderColor} text-gray-300 hover:text-white`
      }`}
    >
      <span className="font-mono text-sm font-semibold">{ticker.ticker}</span>
      <span className="text-[10px] text-gray-500">{count}x</span>
      {recommendation && <RecommendationBadge rec={recommendation} />}
    </button>
  );
};

/* ──────── SVG Trend chart ──────── */
const TrendChart = ({ data }) => {
  const [hoveredIdx, setHoveredIdx] = useState(null);

  if (!data || data.length < 2) {
    return (
      <div className="h-32 flex items-center justify-center text-xs text-gray-500">
        Not enough data points for trend visualization
      </div>
    );
  }

  const width = 600;
  const height = 120;
  const padX = 40;
  const padY = 16;
  const chartW = width - padX * 2;
  const chartH = height - padY * 2;

  // Use scores for the line chart (sorted chronologically)
  const sorted = [...data].reverse(); // API returns DESC, we want ASC
  const scores = sorted.map((d) => d.score ?? d.confidence_score ?? 0);
  const minScore = Math.min(...scores, -10);
  const maxScore = Math.max(...scores, 10);
  const range = maxScore - minScore || 1;

  const points = scores.map((s, i) => {
    const x = padX + (i / (scores.length - 1)) * chartW;
    const y = padY + chartH - ((s - minScore) / range) * chartH;
    return { x, y, score: s, rec: sorted[i].recommendation, date: sorted[i].timestamp, confidence: sorted[i].confidence };
  });

  const linePath = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x},${p.y}`).join(' ');

  // Gradient fill area
  const areaPath = `${linePath} L${points[points.length - 1].x},${padY + chartH} L${points[0].x},${padY + chartH} Z`;

  // Zero line if range spans 0
  const zeroY = minScore < 0 && maxScore > 0 ? padY + chartH - ((0 - minScore) / range) * chartH : null;

  const hoveredPoint = hoveredIdx != null ? points[hoveredIdx] : null;

  return (
    <div className="relative">
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full" preserveAspectRatio="xMidYMid meet">
        <defs>
          <linearGradient id="scoreGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#006fee" stopOpacity="0.3" />
            <stop offset="100%" stopColor="#006fee" stopOpacity="0.02" />
          </linearGradient>
        </defs>

        {/* Grid lines */}
        <line x1={padX} y1={padY} x2={padX} y2={padY + chartH} stroke="rgba(255,255,255,0.06)" strokeWidth="1" />
        <line x1={padX} y1={padY + chartH} x2={padX + chartW} y2={padY + chartH} stroke="rgba(255,255,255,0.06)" strokeWidth="1" />

        {/* Zero line */}
        {zeroY && (
          <line x1={padX} y1={zeroY} x2={padX + chartW} y2={zeroY} stroke="rgba(255,255,255,0.1)" strokeWidth="1" strokeDasharray="4 4" />
        )}

        {/* Y axis labels */}
        <text x={padX - 4} y={padY + 4} textAnchor="end" fill="rgba(255,255,255,0.3)" fontSize="9">{maxScore}</text>
        <text x={padX - 4} y={padY + chartH + 4} textAnchor="end" fill="rgba(255,255,255,0.3)" fontSize="9">{minScore}</text>
        {zeroY && <text x={padX - 4} y={zeroY + 3} textAnchor="end" fill="rgba(255,255,255,0.3)" fontSize="9">0</text>}

        {/* Area fill */}
        <path d={areaPath} fill="url(#scoreGrad)" />

        {/* Line */}
        <path d={linePath} fill="none" stroke="#006fee" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />

        {/* Hover crosshair */}
        {hoveredPoint && (
          <line
            x1={hoveredPoint.x}
            y1={padY}
            x2={hoveredPoint.x}
            y2={padY + chartH}
            stroke="rgba(255,255,255,0.15)"
            strokeWidth="1"
            strokeDasharray="3 3"
          />
        )}

        {/* Data points */}
        {points.map((p, i) => {
          const dotColor = p.rec === 'BUY' ? '#17c964' : p.rec === 'SELL' ? '#f31260' : '#f5a524';
          const isHovered = hoveredIdx === i;
          return (
            <g key={i}>
              {/* Invisible larger hit area for easier hovering */}
              <circle
                cx={p.x}
                cy={p.y}
                r="12"
                fill="transparent"
                onMouseEnter={() => setHoveredIdx(i)}
                onMouseLeave={() => setHoveredIdx(null)}
                style={{ cursor: 'pointer' }}
              />
              <circle
                cx={p.x}
                cy={p.y}
                r={isHovered ? 6 : 4}
                fill={dotColor}
                stroke={isHovered ? 'white' : '#18181b'}
                strokeWidth={isHovered ? 2.5 : 2}
                style={{ transition: 'r 0.15s, stroke-width 0.15s' }}
                pointerEvents="none"
              />
              {/* Date label for first and last */}
              {(i === 0 || i === points.length - 1) && (
                <text
                  x={p.x}
                  y={padY + chartH + 12}
                  textAnchor={i === 0 ? 'start' : 'end'}
                  fill="rgba(255,255,255,0.3)"
                  fontSize="8"
                >
                  {new Date(p.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                </text>
              )}
            </g>
          );
        })}
      </svg>

      {/* Floating tooltip card */}
      {hoveredPoint && (
        <div
          className="absolute z-50 pointer-events-none"
          style={{
            left: `${(hoveredPoint.x / width) * 100}%`,
            top: `${(hoveredPoint.y / height) * 100}%`,
            transform: hoveredPoint.x > width * 0.7 ? 'translate(-110%, -120%)' : 'translate(-50%, -120%)',
          }}
        >
          <div className="bg-dark-card border border-white/10 rounded-lg shadow-xl px-3 py-2 min-w-[140px]">
            <div className="text-[10px] text-gray-500 mb-1">
              {new Date(hoveredPoint.date).toLocaleDateString('en-US', {
                month: 'short',
                day: 'numeric',
                year: 'numeric',
              })}
            </div>
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-[9px] text-gray-500 uppercase">Score</div>
                <div className="text-sm font-bold font-mono tabular-nums">
                  {hoveredPoint.score > 0 ? '+' : ''}{hoveredPoint.score}
                </div>
              </div>
              <div>
                <div className="text-[9px] text-gray-500 uppercase">Conf</div>
                <div className="text-sm font-bold font-mono tabular-nums">
                  {hoveredPoint.confidence != null ? `${Math.round(hoveredPoint.confidence * 100)}%` : '—'}
                </div>
              </div>
              <RecommendationBadge rec={hoveredPoint.rec} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

/* ──────── Filter bar ──────── */
const FilterBar = ({ filters, onApply }) => {
  const recs = [null, 'BUY', 'HOLD', 'SELL'];

  return (
    <div className="flex items-center space-x-3 flex-wrap">
      <div className="flex items-center space-x-1">
        <FilterIcon className="w-3.5 h-3.5 text-gray-500" />
        <span className="text-[11px] text-gray-500 font-medium">Filter:</span>
      </div>
      {recs.map((rec) => (
        <button
          key={rec || 'all'}
          onClick={() => onApply({ recommendation: rec })}
          className={`text-[11px] px-2.5 py-1 rounded-md border transition-all ${
            filters.recommendation === rec
              ? 'bg-primary/15 border-primary/40 text-white font-semibold'
              : 'bg-dark-card border-white/5 text-gray-400 hover:text-white hover:border-white/15'
          }`}
        >
          {rec || 'All'}
        </button>
      ))}
    </div>
  );
};

/* ──────── Pagination controls ──────── */
const Pagination = ({ page, pageSize, totalCount, hasMore, onPageChange }) => {
  const totalPages = Math.ceil(totalCount / pageSize);
  if (totalPages <= 1) return null;

  return (
    <div className="flex items-center justify-between mt-4 pt-4 border-t border-white/5">
      <span className="text-[11px] text-gray-500">
        Showing {page * pageSize + 1}–{Math.min((page + 1) * pageSize, totalCount)} of {totalCount}
      </span>
      <div className="flex items-center space-x-1">
        <button
          onClick={() => onPageChange(page - 1)}
          disabled={page === 0}
          className="p-1.5 rounded-md border border-white/5 text-gray-400 hover:text-white hover:border-white/15 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
        >
          <ChevronLeftIcon className="w-3.5 h-3.5" />
        </button>
        <span className="text-[11px] text-gray-400 px-2 tabular-nums">
          {page + 1} / {totalPages}
        </span>
        <button
          onClick={() => onPageChange(page + 1)}
          disabled={!hasMore}
          className="p-1.5 rounded-md border border-white/5 text-gray-400 hover:text-white hover:border-white/15 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
        >
          <ChevronRightIcon className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
};

/* ──────── Main HistoryDashboard component ──────── */
const HistoryDashboard = ({ onBack, initialTicker }) => {
  const {
    tickers,
    tickersLoading,
    fetchTickers,
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
    removeAnalysis,
    error,
  } = useHistory();

  const [confirmDelete, setConfirmDelete] = useState(null);
  const [tickerSearch, setTickerSearch] = useState('');
  const [calibrationSummary, setCalibrationSummary] = useState(null);
  const [calibrationLoading, setCalibrationLoading] = useState(false);

  // Load tickers on mount
  useEffect(() => {
    fetchTickers().then((loadedTickers) => {
      // Auto-select initialTicker or first ticker
      if (initialTicker && loadedTickers.some((t) => t.ticker === initialTicker)) {
        selectTicker(initialTicker);
      } else if (loadedTickers.length > 0 && !selectedTicker) {
        selectTicker(loadedTickers[0].ticker);
      }
    });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    let mounted = true;
    const loadCalibration = async () => {
      setCalibrationLoading(true);
      try {
        const data = await getCalibrationSummary(180);
        if (mounted) setCalibrationSummary(data);
      } catch {
        if (mounted) setCalibrationSummary(null);
      } finally {
        if (mounted) setCalibrationLoading(false);
      }
    };

    loadCalibration();
    return () => {
      mounted = false;
    };
  }, []);

  // Filter tickers by search
  const filteredTickers = useMemo(() => {
    if (!tickerSearch) return tickers;
    return tickers.filter((t) => t.ticker.includes(tickerSearch.toUpperCase()));
  }, [tickers, tickerSearch]);

  const handleDelete = async (analysisId) => {
    const success = await removeAnalysis(analysisId);
    if (success) setConfirmDelete(null);
  };

  return (
    <div className="animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center space-x-3">
          <button
            onClick={onBack}
            className="p-2 rounded-lg border border-white/5 text-gray-400 hover:text-white hover:border-white/15 transition-all"
          >
            <ArrowLeftIcon className="w-4 h-4" />
          </button>
          <div className="flex items-center space-x-2">
            <HistoryIcon className="w-5 h-5 text-accent-blue" />
            <h2 className="text-lg font-bold tracking-tight">Analysis History</h2>
          </div>
        </div>
        {totalCount > 0 && (
          <span className="text-xs text-gray-500">{totalCount} analyses for {selectedTicker}</span>
        )}
      </div>

      <div className="grid grid-cols-12 gap-6">
        {/* Left panel - Ticker selector */}
        <div className="col-span-3">
          <div className="glass-card-elevated rounded-xl p-4">
            <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
              Analyzed Tickers
            </h3>

            {/* Ticker search */}
            <div className="relative mb-3">
              <SearchIcon className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-500" />
              <input
                type="text"
                value={tickerSearch}
                onChange={(e) => setTickerSearch(e.target.value.toUpperCase())}
                placeholder="Search..."
                className="w-full pl-8 pr-3 py-1.5 bg-dark-inset border border-dark-border rounded-md text-xs focus:outline-none focus:ring-1 focus:ring-primary/30 focus:border-primary/40 transition-all uppercase"
                maxLength={5}
              />
            </div>

            {tickersLoading ? (
              <div className="flex items-center justify-center py-8">
                <LoadingSpinner size={16} className="text-gray-500" />
              </div>
            ) : filteredTickers.length === 0 ? (
              <p className="text-xs text-gray-500 text-center py-6">
                {tickers.length === 0 ? 'No analyses found. Run an analysis first.' : 'No matching tickers.'}
              </p>
            ) : (
              <div className="space-y-1.5 max-h-[500px] overflow-y-auto">
                {filteredTickers.map((t) => (
                  <TickerChip
                    key={t.ticker}
                    ticker={t}
                    isActive={selectedTicker === t.ticker}
                    count={t.analysis_count}
                    recommendation={t.latest_recommendation}
                    onClick={selectTicker}
                  />
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right panel - History details */}
        <div className="col-span-9">
          {!selectedTicker ? (
            <div className="glass-card-elevated rounded-xl p-12 text-center">
              <HistoryIcon className="w-10 h-10 text-gray-600 mx-auto mb-3" />
              <p className="text-sm text-gray-500">Select a ticker to view its analysis history</p>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="glass-card-elevated rounded-xl p-5">
                <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
                  Calibration Summary (180d)
                </h3>
                <CalibrationSummaryCards summary={calibrationSummary} loading={calibrationLoading} />
              </div>

              {/* Trend chart */}
              <div className="glass-card-elevated rounded-xl p-5">
                <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3 flex items-center space-x-2">
                  <TrendingUpIcon className="w-3.5 h-3.5 text-accent-blue" />
                  <span>Score Trend — {selectedTicker}</span>
                </h3>
                {historyLoading ? (
                  <div className="h-32 flex items-center justify-center">
                    <LoadingSpinner size={16} className="text-gray-500" />
                  </div>
                ) : (
                  <TrendChart data={history} />
                )}
              </div>

              {/* Filters + Table */}
              <div className="glass-card-elevated rounded-xl p-5">
                <div className="flex items-center justify-between mb-4">
                  <FilterBar filters={filters} onApply={applyFilters} />
                </div>

                {historyLoading ? (
                  <div className="space-y-2">
                    {[...Array(5)].map((_, i) => (
                      <div key={i} className="skeleton h-10 w-full" />
                    ))}
                  </div>
                ) : history.length === 0 ? (
                  <div className="text-center py-8">
                    <p className="text-sm text-gray-500">
                      {filters.recommendation ? `No ${filters.recommendation} analyses found.` : 'No analyses found for this ticker.'}
                    </p>
                  </div>
                ) : (
                  <>
                    {/* Table header */}
                    <div className="grid grid-cols-12 gap-2 px-3 py-2 text-[10px] font-semibold text-gray-500 uppercase tracking-wider border-b border-white/5">
                      <div className="col-span-3">Date</div>
                      <div className="col-span-2">Recommendation</div>
                      <div className="col-span-2">Score</div>
                      <div className="col-span-1">Conf</div>
                      <div className="col-span-2">Outcomes</div>
                      <div className="col-span-2 text-right">Actions</div>
                    </div>

                    {/* Table rows */}
                    <div className="divide-y divide-white/[0.03]">
                      {history.map((item) => (
                        <div
                          key={item.id}
                          className="grid grid-cols-12 gap-2 px-3 py-2.5 items-center hover:bg-white/[0.02] transition-colors rounded"
                        >
                          <div className="col-span-3 flex items-center space-x-2">
                            <ClockIcon className="w-3.5 h-3.5 text-gray-600 flex-shrink-0" />
                            <div>
                              <div className="text-xs font-medium">
                                {new Date(item.timestamp).toLocaleDateString('en-US', {
                                  month: 'short',
                                  day: 'numeric',
                                  year: 'numeric',
                                })}
                              </div>
                              <div className="text-[10px] text-gray-500">
                                {new Date(item.timestamp).toLocaleTimeString('en-US', {
                                  hour: '2-digit',
                                  minute: '2-digit',
                                })}
                              </div>
                            </div>
                          </div>
                          <div className="col-span-2">
                            <RecommendationBadge rec={item.recommendation} />
                          </div>
                          <div className="col-span-2">
                            <ScoreBar score={item.score} />
                          </div>
                          <div className="col-span-1">
                            <ConfidencePill confidence={item.confidence} />
                          </div>
                          <div className="col-span-2">
                            <OutcomeChips outcomes={item.outcomes} />
                          </div>
                          <div className="col-span-2 flex justify-end space-x-1">
                            {confirmDelete === item.id ? (
                              <div className="flex items-center space-x-1">
                                <button
                                  onClick={() => handleDelete(item.id)}
                                  className="text-[10px] px-2 py-1 rounded bg-danger/20 text-danger-400 hover:bg-danger/30 transition-colors"
                                >
                                  Confirm
                                </button>
                                <button
                                  onClick={() => setConfirmDelete(null)}
                                  className="text-[10px] px-2 py-1 rounded bg-dark-card text-gray-400 hover:text-white transition-colors"
                                >
                                  Cancel
                                </button>
                              </div>
                            ) : (
                              <button
                                onClick={() => setConfirmDelete(item.id)}
                                className="p-1.5 rounded-md text-gray-600 hover:text-danger-400 hover:bg-danger/10 transition-all"
                                title="Delete analysis"
                              >
                                <TrashIcon className="w-3.5 h-3.5" />
                              </button>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>

                    {/* Pagination */}
                    <Pagination
                      page={page}
                      pageSize={pageSize}
                      totalCount={totalCount}
                      hasMore={hasMore}
                      onPageChange={goToPage}
                    />
                  </>
                )}
              </div>
            </div>
          )}

          {/* Error display */}
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

export default HistoryDashboard;
