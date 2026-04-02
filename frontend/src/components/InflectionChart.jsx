import { useState, useEffect, useRef, useMemo } from 'react';
import { createChart } from 'lightweight-charts';
import { getInflectionTimeseries } from '../utils/api';

const TIME_RANGES = [
  { label: '1M', days: 30 },
  { label: '3M', days: 90 },
  { label: '6M', days: 180 },
  { label: '1Y', days: 365 },
];

const KPI_COLORS = {
  forward_pe: '#006fee', profit_margins: '#17c964', revenue_growth: '#f5a524',
  overall_sentiment: '#a855f7', rsi: '#ec4899', analyst_target_median: '#06b6d4',
  fed_funds_rate: '#f97316', put_call_ratio: '#84cc16',
};

const InflectionChart = ({ ticker }) => {
  const chartRef = useRef(null);
  const chartInstance = useRef(null);
  const [timeRange, setTimeRange] = useState('3M');
  const [rawData, setRawData] = useState([]);
  const [activeKPIs, setActiveKPIs] = useState(new Set(['forward_pe', 'overall_sentiment', 'revenue_growth']));
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!ticker) return;
    setLoading(true);
    getInflectionTimeseries(ticker, null, 500)
      .then(setRawData)
      .catch(() => setRawData([]))
      .finally(() => setLoading(false));
  }, [ticker]);

  const availableKPIs = useMemo(() => {
    const kpis = new Set();
    for (const row of rawData) kpis.add(row.kpi_name);
    return [...kpis].sort();
  }, [rawData]);

  useEffect(() => {
    if (!chartRef.current || rawData.length === 0) return;
    if (chartInstance.current) { chartInstance.current.remove(); chartInstance.current = null; }

    const chart = createChart(chartRef.current, {
      layout: { background: { type: 'solid', color: 'transparent' }, textColor: '#a1a1aa', fontSize: 11 },
      grid: { vertLines: { color: 'rgba(255,255,255,0.04)' }, horzLines: { color: 'rgba(255,255,255,0.04)' } },
      rightPriceScale: { borderColor: 'rgba(255,255,255,0.1)' },
      timeScale: { borderColor: 'rgba(255,255,255,0.1)' },
      crosshair: { mode: 0 },
    });
    chartInstance.current = chart;

    const byKPI = {};
    for (const row of rawData) {
      if (!activeKPIs.has(row.kpi_name)) continue;
      if (!byKPI[row.kpi_name]) byKPI[row.kpi_name] = [];
      byKPI[row.kpi_name].push({ time: row.captured_at.split('T')[0], value: row.value });
    }

    for (const [kpi, points] of Object.entries(byKPI)) {
      const series = chart.addLineSeries({
        color: KPI_COLORS[kpi] || '#71717a', lineWidth: 2, title: kpi.replace(/_/g, ' '),
      });
      series.setData(points);
    }

    chart.timeScale().fitContent();

    const resizeObserver = new ResizeObserver(() => {
      if (chartRef.current) chart.applyOptions({ width: chartRef.current.clientWidth });
    });
    resizeObserver.observe(chartRef.current);

    return () => { resizeObserver.disconnect(); chart.remove(); chartInstance.current = null; };
  }, [rawData, activeKPIs, timeRange]);

  const toggleKPI = (kpi) => {
    setActiveKPIs((prev) => { const next = new Set(prev); if (next.has(kpi)) next.delete(kpi); else next.add(kpi); return next; });
  };

  if (!ticker) {
    return <div className="flex items-center justify-center min-h-[200px] text-zinc-500 text-sm">Select a ticker to view KPI trends</div>;
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-3 py-2 border-b border-zinc-800">
        <div className="flex gap-1">
          {TIME_RANGES.map((r) => (
            <button key={r.label} onClick={() => setTimeRange(r.label)}
              className={`px-2 py-0.5 text-xs rounded ${timeRange === r.label ? 'bg-zinc-700 text-white' : 'text-zinc-500 hover:text-zinc-300'}`}>
              {r.label}
            </button>
          ))}
        </div>
        <div className="flex gap-1 flex-wrap justify-end">
          {availableKPIs.map((kpi) => (
            <button key={kpi} onClick={() => toggleKPI(kpi)}
              className={`px-1.5 py-0.5 text-[0.6rem] rounded border transition-colors ${activeKPIs.has(kpi) ? 'border-zinc-600 text-zinc-200' : 'border-zinc-800 text-zinc-600'}`}
              style={{ borderLeftColor: activeKPIs.has(kpi) ? (KPI_COLORS[kpi] || '#71717a') : undefined, borderLeftWidth: activeKPIs.has(kpi) ? 2 : undefined }}>
              {kpi.replace(/_/g, ' ')}
            </button>
          ))}
        </div>
      </div>
      <div className="flex-1 min-h-0">
        {loading ? <div className="flex items-center justify-center h-full text-zinc-500 text-sm">Loading…</div> : <div ref={chartRef} className="w-full h-full" />}
      </div>
    </div>
  );
};

export default InflectionChart;
