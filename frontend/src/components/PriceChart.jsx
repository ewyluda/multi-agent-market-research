/**
 * PriceChart - Lightweight Charts candlestick/volume chart with technical indicator metric cards
 */

import React, { useRef, useEffect, useMemo, useState, useCallback } from 'react';
import {
  createChart,
  ColorType,
  CrosshairMode,
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
} from 'lightweight-charts';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

const EMPTY_ARRAY = [];

const SMA_CONFIG = [
  { period: 9, color: '#ef4444', label: 'SMA 9', defaultVisible: true },
  { period: 20, color: '#f59e0b', label: 'SMA 20', defaultVisible: true },
  { period: 50, color: '#22c55e', label: 'SMA 50', defaultVisible: true },
  { period: 100, color: '#3b82f6', label: 'SMA 100', defaultVisible: true },
  { period: 200, color: '#a855f7', label: 'SMA 200', defaultVisible: true },
];

function calculateSMA(data, period) {
  const result = [];
  for (let i = period - 1; i < data.length; i++) {
    let sum = 0;
    for (let j = i - period + 1; j <= i; j++) {
      sum += data[j].close;
    }
    result.push({ time: data[i].time, value: sum / period });
  }
  return result;
}

/* ──────────────────────────────────────────────
   SVG micro-components for metric cards
   ────────────────────────────────────────────── */

/** RSI arc gauge -- 60px wide, zones: <30 green, 30-70 gray, >70 red */
const RsiGauge = ({ value }) => {
  const clampedValue = Math.max(0, Math.min(100, value ?? 50));
  // Arc spans 180 degrees (pi radians), radius 24, center at (30, 32)
  const r = 24;
  const cx = 30;
  const cy = 32;
  const startAngle = Math.PI; // left (180 deg)

  const arcPath = (fromPct, toPct) => {
    const a1 = startAngle - (fromPct / 100) * Math.PI;
    const a2 = startAngle - (toPct / 100) * Math.PI;
    const x1 = cx + r * Math.cos(a1);
    const y1 = cy - r * Math.sin(a1);
    const x2 = cx + r * Math.cos(a2);
    const y2 = cy - r * Math.sin(a2);
    const large = toPct - fromPct > 50 ? 1 : 0;
    return `M ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2}`;
  };

  // Needle angle
  const needleAngle = startAngle - (clampedValue / 100) * Math.PI;
  const needleLen = r - 4;
  const nx = cx + needleLen * Math.cos(needleAngle);
  const ny = cy - needleLen * Math.sin(needleAngle);

  return (
    <svg width="60" height="38" viewBox="0 0 60 38">
      {/* Zone arcs */}
      <path d={arcPath(0, 30)} fill="none" stroke="rgba(23,201,100,0.4)" strokeWidth="4" strokeLinecap="round" />
      <path d={arcPath(30, 70)} fill="none" stroke="rgba(113,113,122,0.35)" strokeWidth="4" strokeLinecap="round" />
      <path d={arcPath(70, 100)} fill="none" stroke="rgba(243,18,96,0.4)" strokeWidth="4" strokeLinecap="round" />
      {/* Needle */}
      <line x1={cx} y1={cy} x2={nx} y2={ny} stroke="#e4e4e7" strokeWidth="1.5" strokeLinecap="round" />
      <circle cx={cx} cy={cy} r="2" fill="#e4e4e7" />
    </svg>
  );
};

/** Single MACD histogram bar */
const MacdBar = ({ value }) => {
  const maxH = 20;
  const absVal = Math.min(Math.abs(value || 0), 5);
  const h = Math.max(2, (absVal / 5) * maxH);
  const color = (value || 0) >= 0 ? '#17c964' : '#f31260';
  return (
    <svg width="16" height="24" viewBox="0 0 16 24">
      <rect x="3" y={24 - h} width="10" height={h} rx="1" fill={color} opacity="0.7" />
      <line x1="0" y1="24" x2="16" y2="24" stroke="#3f3f46" strokeWidth="0.5" />
    </svg>
  );
};

/** Bollinger range bar */
const BollingerRange = ({ lower, upper, current }) => {
  if (lower == null || upper == null) return null;
  const range = upper - lower;
  if (range <= 0) return null;
  const pct = Math.max(0, Math.min(100, ((current - lower) / range) * 100));

  return (
    <div className="relative w-full h-3 bg-[var(--card-hover)] rounded-full overflow-hidden mt-1">
      {/* Band fill */}
      <div className="absolute inset-0 rounded-full"
        style={{ background: 'linear-gradient(90deg, rgba(23,201,100,0.25), rgba(113,113,122,0.15), rgba(243,18,96,0.25))' }}
      />
      {/* Current price marker */}
      <div
        className="absolute top-1/2 -translate-y-1/2 w-2.5 h-2.5 rounded-full border-2 border-white bg-accent-blue shadow-[0_0_6px_rgba(0,111,238,0.6)]"
        style={{ left: `calc(${pct}% - 5px)` }}
      />
    </div>
  );
};

/** Animated signal strength bar */
const SignalBar = ({ strength, overall }) => {
  const pct = Math.max(0, Math.min(100, (strength || 0) * 100));
  const color =
    overall === 'bullish' ? 'var(--success)' :
    overall === 'bearish' ? 'var(--danger)' :
    'var(--warning)';
  const glowColor =
    overall === 'bullish' ? 'rgba(23,201,100,0.4)' :
    overall === 'bearish' ? 'rgba(243,18,96,0.4)' :
    'rgba(245,165,36,0.4)';

  return (
    <div className="relative w-full h-2 bg-[var(--card-hover)] rounded-full overflow-hidden mt-1.5">
      <div
        className="h-full rounded-full transition-all duration-700 ease-out"
        style={{
          width: `${pct}%`,
          backgroundColor: color,
          boxShadow: `0 0 8px ${glowColor}`,
        }}
      />
    </div>
  );
};

/* ──────────────────────────────────────────────
   PriceChart component
   ────────────────────────────────────────────── */

const PriceChart = ({ analysis }) => {
  const chartContainerRef = useRef(null);
  const chartInstanceRef = useRef(null);
  const smaSeriesRef = useRef({});
  // Ref mirror of smaVisibility so the chart useEffect can read initial values
  // without adding smaVisibility to its dependency array (which would recreate
  // the chart on every toggle instead of using applyOptions).
  const smaVisibilityRef = useRef(
    Object.fromEntries(SMA_CONFIG.map((s) => [s.period, s.defaultVisible]))
  );

  const [smaVisibility, setSmaVisibility] = useState(() => ({ ...smaVisibilityRef.current }));

  const toggleSMA = useCallback((period) => {
    setSmaVisibility((prev) => {
      const next = { ...prev, [period]: !prev[period] };
      smaVisibilityRef.current = next;
      const series = smaSeriesRef.current[period];
      if (series) {
        series.applyOptions({ visible: next[period] });
      }
      return next;
    });
  }, []);

  // ── Data extraction ──
  const marketData = analysis?.agent_results?.market?.data || {};
  const technicalData = analysis?.agent_results?.technical?.data || {};
  const priceHistory = marketData.price_history ?? EMPTY_ARRAY;
  const indicators = technicalData.indicators || {};
  const signals = technicalData.signals || {};

  // ── Transform data for lightweight-charts ──
  const candleData = useMemo(() => priceHistory
    .map((d) => ({
      time: d.date,
      open: Number(d.open),
      high: Number(d.high),
      low: Number(d.low),
      close: Number(d.close),
    }))
    .filter((d) => (
      typeof d.time === 'string' &&
      Number.isFinite(d.open) &&
      Number.isFinite(d.high) &&
      Number.isFinite(d.low) &&
      Number.isFinite(d.close)
    ))
    .sort((a, b) => String(a.time).localeCompare(String(b.time))), [priceHistory]);

  const volumeData = useMemo(() => priceHistory
    .map((d) => ({
      time: d.date,
      value: Number(d.volume),
      color: Number(d.close) >= Number(d.open) ? 'rgba(23, 201, 100, 0.3)' : 'rgba(243, 18, 96, 0.3)',
    }))
    .filter((d) => typeof d.time === 'string' && Number.isFinite(d.value))
    .sort((a, b) => String(a.time).localeCompare(String(b.time))), [priceHistory]);

  const hasChartData = candleData.length > 0;

  // ── Chart creation and lifecycle ──
  useEffect(() => {
    if (!hasChartData || !chartContainerRef.current) return;

    // Clean up any previous chart
    if (chartInstanceRef.current) {
      chartInstanceRef.current.remove();
      chartInstanceRef.current = null;
    }

    const container = chartContainerRef.current;

    let chart = null;
    let resizeObserver = null;
    let resizeHandler = null;

    try {
      chart = createChart(container, {
        width: container.clientWidth,
        height: 400,
        layout: {
          background: { type: ColorType.Solid, color: '#141414' },
          textColor: 'rgba(255, 255, 255, 0.6)',
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: 10,
        },
        grid: {
          vertLines: { color: 'rgba(255, 255, 255, 0.04)' },
          horzLines: { color: 'rgba(255, 255, 255, 0.04)' },
        },
        crosshair: {
          mode: CrosshairMode.Normal,
          vertLine: { color: 'rgba(0, 111, 238, 0.4)', labelBackgroundColor: '#006fee' },
          horzLine: { color: 'rgba(0, 111, 238, 0.4)', labelBackgroundColor: '#006fee' },
        },
        timeScale: {
          borderColor: '#27272a',
          timeVisible: false,
          rightOffset: 5,
        },
        rightPriceScale: {
          borderColor: '#27272a',
        },
      });

      chartInstanceRef.current = chart;

      const candleSeries = typeof chart.addSeries === 'function'
        ? chart.addSeries(CandlestickSeries, {
          upColor: '#17c964',
          downColor: '#f31260',
          borderUpColor: '#17c964',
          borderDownColor: '#f31260',
          wickUpColor: '#17c964',
          wickDownColor: '#f31260',
        })
        : chart.addCandlestickSeries({
          upColor: '#17c964',
          downColor: '#f31260',
          borderUpColor: '#17c964',
          borderDownColor: '#f31260',
          wickUpColor: '#17c964',
          wickDownColor: '#f31260',
        });
      candleSeries.setData(candleData);

      // Reset SMA series refs for this chart instance
      smaSeriesRef.current = {};
      SMA_CONFIG.forEach(({ period, color }) => {
        const lineOptions = {
          color,
          lineWidth: 1,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
          visible: smaVisibilityRef.current[period],
        };
        const lineSeries = typeof chart.addSeries === 'function'
          ? chart.addSeries(LineSeries, lineOptions)
          : chart.addLineSeries(lineOptions);
        const smaData = calculateSMA(candleData, period);
        if (smaData.length > 0) {
          lineSeries.setData(smaData);
        }
        smaSeriesRef.current[period] = lineSeries;
      });

      const volumeSeries = typeof chart.addSeries === 'function'
        ? chart.addSeries(HistogramSeries, {
          priceFormat: { type: 'volume' },
          priceScaleId: 'volume',
        })
        : chart.addHistogramSeries({
          priceFormat: { type: 'volume' },
          priceScaleId: 'volume',
        });
      volumeSeries.priceScale().applyOptions({
        scaleMargins: { top: 0.8, bottom: 0 },
      });
      volumeSeries.setData(volumeData);

      chart.timeScale().fitContent();

      if (typeof ResizeObserver !== 'undefined') {
        resizeObserver = new ResizeObserver((entries) => {
          for (const entry of entries) {
            const { width } = entry.contentRect;
            if (width > 0) {
              chart.applyOptions({ width });
            }
          }
        });
        resizeObserver.observe(container);
      } else {
        resizeHandler = () => {
          if (chart && container.clientWidth > 0) {
            chart.applyOptions({ width: container.clientWidth });
          }
        };
        window.addEventListener('resize', resizeHandler);
      }
    } catch (err) {
      console.error('Failed to initialize chart:', err);
      if (chart) {
        chart.remove();
      }
      chartInstanceRef.current = null;
    }

    return () => {
      if (resizeObserver) {
        resizeObserver.disconnect();
      }
      if (resizeHandler) {
        window.removeEventListener('resize', resizeHandler);
      }
      if (chart) {
        chart.remove();
      }
      chartInstanceRef.current = null;
    };
  }, [hasChartData, candleData, volumeData]);

  // ── Skeleton state ──
  if (!analysis) {
    return (
      <Card>
        <CardContent className="pt-5">
          <div className="skeleton h-[400px] w-full mb-5 rounded-lg" />
          <div className="grid grid-cols-4 gap-3">
            <div className="skeleton h-20 rounded-lg" />
            <div className="skeleton h-20 rounded-lg" />
            <div className="skeleton h-20 rounded-lg" />
            <div className="skeleton h-20 rounded-lg" />
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="animate-fade-in">
      <CardContent className="pt-5">
        {/* ── Chart area ── */}
        {hasChartData ? (
          <div
            ref={chartContainerRef}
            className="w-full rounded-lg overflow-hidden border border-[var(--border)]"
            style={{ height: 400 }}
          />
        ) : (
          <div className="w-full h-[400px] rounded-lg border border-[var(--border)] mb-5 flex items-center justify-center">
            <div className="text-center">
              <svg width="40" height="40" viewBox="0 0 40 40" fill="none" className="mx-auto mb-3 opacity-40">
                {/* Grid lines */}
                <line x1="8" y1="32" x2="34" y2="32" stroke="#3f3f46" strokeWidth="0.75" />
                <line x1="8" y1="24" x2="34" y2="24" stroke="#3f3f46" strokeWidth="0.5" strokeDasharray="2 2" />
                <line x1="8" y1="16" x2="34" y2="16" stroke="#3f3f46" strokeWidth="0.5" strokeDasharray="2 2" />
                {/* Candlestick wicks */}
                <line x1="13" y1="10" x2="13" y2="28" stroke="#52525b" strokeWidth="1" />
                <line x1="20" y1="14" x2="20" y2="30" stroke="#52525b" strokeWidth="1" />
                <line x1="27" y1="8" x2="27" y2="26" stroke="#52525b" strokeWidth="1" />
                {/* Candlestick bodies */}
                <rect x="11" y="14" width="4" height="10" rx="0.5" fill="#52525b" />
                <rect x="18" y="20" width="4" height="6" rx="0.5" fill="#3f3f46" stroke="#52525b" strokeWidth="0.5" />
                <rect x="25" y="12" width="4" height="10" rx="0.5" fill="#52525b" />
              </svg>
              <p className="text-sm text-gray-500">Chart data unavailable</p>
              <p className="text-[10px] text-gray-600 mt-1">Price history not returned by data agents</p>
            </div>
          </div>
        )}

        {/* ── SMA legend ── */}
        {hasChartData && (
          <div className="flex gap-3.5 mt-2.5 pt-2.5 mb-5 border-t border-white/[0.04]">
            {SMA_CONFIG.map(({ period, color, label }) => (
              <button
                key={period}
                onClick={() => toggleSMA(period)}
                className="flex items-center gap-1.5 text-[0.65rem] border-none bg-transparent cursor-pointer transition-opacity"
                style={{ color: smaVisibility[period] ? 'rgba(255,255,255,0.5)' : 'rgba(255,255,255,0.2)', opacity: smaVisibility[period] ? 1 : 0.5 }}
              >
                <div className="rounded-sm" style={{ width: 8, height: 2, background: color }} />
                {label}
              </button>
            ))}
          </div>
        )}

        {/* ── Technical indicator metric cards ── */}
        <div className="grid grid-cols-4 gap-4">
          {/* RSI Card */}
          <div className="bg-[var(--card-hover)] rounded-lg p-3.5 border border-white/[0.04] hover:border-white/[0.08] transition-colors">
            <div className="flex justify-between items-center mb-1.5">
              <span className="text-[11px] text-gray-500 uppercase tracking-wider font-medium">RSI</span>
              {indicators.rsi && (
                <Badge variant={
                  indicators.rsi.value > 70 ? 'danger' :
                  indicators.rsi.value < 30 ? 'success' :
                  'secondary'
                } className="text-[10px]">
                  {indicators.rsi.interpretation || (
                    indicators.rsi.value > 70 ? 'overbought' :
                    indicators.rsi.value < 30 ? 'oversold' : 'neutral'
                  )}
                </Badge>
              )}
            </div>
            {indicators.rsi ? (
              <div className="flex items-end gap-2">
                <RsiGauge value={indicators.rsi.value} />
                <span className="text-lg font-bold font-data leading-none mb-0.5">
                  {indicators.rsi.value?.toFixed(1)}
                </span>
              </div>
            ) : (
              <span className="text-sm text-gray-600">N/A</span>
            )}
          </div>

          {/* MACD Card */}
          <div className="bg-[var(--card-hover)] rounded-lg p-3.5 border border-white/[0.04] hover:border-white/[0.08] transition-colors">
            <div className="flex justify-between items-center mb-1.5">
              <span className="text-[11px] text-gray-500 uppercase tracking-wider font-medium">MACD</span>
              {indicators.macd && (
                <Badge variant={indicators.macd.interpretation?.includes('bullish') ? 'success' : 'danger'} className="text-[10px]">
                  {indicators.macd.interpretation || 'N/A'}
                </Badge>
              )}
            </div>
            {indicators.macd ? (
              <div className="flex items-end gap-2">
                <MacdBar value={indicators.macd.histogram} />
                <div className="flex flex-col gap-0.5">
                  <div className="flex items-center gap-1.5">
                    <span className="text-[9px] text-gray-500 w-3">M</span>
                    <span className="text-xs font-data text-gray-300">
                      {indicators.macd.macd_line?.toFixed(2) ?? indicators.macd.value?.toFixed(2) ?? '--'}
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="text-[9px] text-gray-500 w-3">S</span>
                    <span className="text-xs font-data text-gray-300">
                      {indicators.macd.signal_line?.toFixed(2) ?? '--'}
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="text-[9px] text-gray-500 w-3">H</span>
                    <span className={`text-xs font-data ${
                      (indicators.macd.histogram || 0) >= 0 ? 'text-success-400' : 'text-danger-400'
                    }`}>
                      {indicators.macd.histogram?.toFixed(2) ?? '--'}
                    </span>
                  </div>
                </div>
              </div>
            ) : (
              <span className="text-sm text-gray-600">N/A</span>
            )}
          </div>

          {/* Bollinger Bands Card */}
          <div className="bg-[var(--card-hover)] rounded-lg p-3.5 border border-white/[0.04] hover:border-white/[0.08] transition-colors">
            <div className="flex justify-between items-center mb-1.5">
              <span className="text-[11px] text-gray-500 uppercase tracking-wider font-medium">Bollinger</span>
              {indicators.bollinger_bands && (
                <Badge variant="secondary" className="text-[10px] text-accent-purple">
                  {indicators.bollinger_bands.interpretation || 'band'}
                </Badge>
              )}
            </div>
            {indicators.bollinger_bands ? (
              <div>
                <div className="flex justify-between text-[10px] font-data text-gray-400 mb-0.5">
                  <span>{indicators.bollinger_bands.lower_band?.toFixed(1)}</span>
                  <span className="text-gray-200 font-semibold">
                    {marketData.current_price?.toFixed(1)}
                  </span>
                  <span>{indicators.bollinger_bands.upper_band?.toFixed(1)}</span>
                </div>
                <BollingerRange
                  lower={indicators.bollinger_bands.lower_band}
                  upper={indicators.bollinger_bands.upper_band}
                  current={marketData.current_price}
                />
                {indicators.bollinger_bands.middle_band != null && (
                  <div className="text-[9px] text-gray-500 mt-1 text-center font-data">
                    SMA {indicators.bollinger_bands.middle_band.toFixed(1)}
                  </div>
                )}
              </div>
            ) : (
              <span className="text-sm text-gray-600">N/A</span>
            )}
          </div>

          {/* Signal Strength Card */}
          <div className="bg-[var(--card-hover)] rounded-lg p-3.5 border border-white/[0.04] hover:border-white/[0.08] transition-colors">
            <div className="flex justify-between items-center mb-1.5">
              <span className="text-[11px] text-gray-500 uppercase tracking-wider font-medium">Signal</span>
              {signals.overall && (
                <Badge variant={
                  signals.overall === 'bullish' ? 'success' :
                  signals.overall === 'bearish' ? 'danger' :
                  'warning'
                } className="text-[10px]">
                  {signals.overall}
                </Badge>
              )}
            </div>
            {signals.strength != null ? (
              <div>
                <span className="text-lg font-bold font-data">
                  {(signals.strength * 100).toFixed(0)}%
                </span>
                <SignalBar strength={signals.strength} overall={signals.overall} />
              </div>
            ) : (
              <span className="text-sm text-gray-600">N/A</span>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default PriceChart;
