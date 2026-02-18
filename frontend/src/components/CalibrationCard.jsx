/**
 * CalibrationCard - Compact calibration health widget for the right sidebar
 * Fetches calibration summary and reliability data on mount
 */

import React, { useState, useEffect } from 'react';
import { motion as Motion } from 'framer-motion';
import { getCalibrationSummary, getCalibrationReliability } from '../utils/api';

const TargetIcon = ({ className }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <circle cx="12" cy="12" r="10" />
    <circle cx="12" cy="12" r="6" />
    <circle cx="12" cy="12" r="2" />
    <line x1="12" y1="2" x2="12" y2="6" />
    <line x1="12" y1="18" x2="12" y2="22" />
    <line x1="2" y1="12" x2="6" y2="12" />
    <line x1="18" y1="12" x2="22" y2="12" />
  </svg>
);

const accuracyColor = (value) => {
  if (value == null) return 'text-gray-400';
  if (value >= 70) return 'text-success-400';
  if (value >= 50) return 'text-warning-400';
  return 'text-danger-400';
};

const accuracyBarColor = (value) => {
  if (value == null) return 'bg-gray-600';
  if (value >= 70) return 'bg-success/60';
  if (value >= 50) return 'bg-warning/60';
  return 'bg-danger/60';
};

const staggerContainer = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.06, delayChildren: 0.1 },
  },
};

const staggerItem = {
  hidden: { opacity: 0, y: 6 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.3 } },
};

const CalibrationCard = () => {
  const [summary, setSummary] = useState(null);
  const [reliability, setReliability] = useState(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let cancelled = false;

    const fetchData = async () => {
      try {
        const [summaryRes, reliabilityRes] = await Promise.all([
          getCalibrationSummary().catch(() => null),
          getCalibrationReliability().catch(() => null),
        ]);
        if (!cancelled) {
          setSummary(summaryRes);
          setReliability(reliabilityRes);
        }
      } catch {
        // silently ignore — show empty state
      } finally {
        if (!cancelled) setLoaded(true);
      }
    };

    fetchData();
    return () => { cancelled = true; };
  }, []);

  // Don't render anything until we've attempted the fetch
  if (!loaded) return null;

  const overallAccuracy = summary?.overall_accuracy;
  const totalOutcomes = summary?.total_outcomes ?? 0;
  const ece = reliability?.ece;
  const hasData = totalOutcomes > 0 && overallAccuracy != null;

  // Graceful empty state
  if (!hasData) {
    return (
      <div className="glass-card-elevated rounded-xl p-5">
        <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3 flex items-center space-x-2">
          <TargetIcon className="w-4 h-4 text-gray-600" />
          <span>Calibration</span>
        </h3>
        <p className="text-xs text-gray-600 leading-relaxed">
          Run analyses to build calibration history
        </p>
      </div>
    );
  }

  // Extract per-ticker horizon data if available
  const tickers = summary?.tickers ?? [];
  const horizonAccuracies = {};

  // Aggregate horizon-level accuracy from ticker data
  for (const t of tickers) {
    const snapshots = t.snapshots ?? [];
    for (const snap of snapshots) {
      const h = snap.horizon_days;
      if (h && snap.accuracy != null) {
        if (!horizonAccuracies[h]) {
          horizonAccuracies[h] = { sum: 0, count: 0 };
        }
        horizonAccuracies[h].sum += snap.accuracy;
        horizonAccuracies[h].count += 1;
      }
    }
  }

  // Standard horizons to display
  const horizonLabels = { 1: '1d', 7: '7d', 30: '30d' };
  const horizonBars = Object.entries(horizonLabels)
    .filter(([days]) => horizonAccuracies[days])
    .map(([days, label]) => {
      const avg = horizonAccuracies[days].sum / horizonAccuracies[days].count;
      return { label, accuracy: Math.round(avg), days: Number(days) };
    });

  return (
    <Motion.div
      initial={{ opacity: 0, x: 12 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.4, delay: 0.1 }}
      className="glass-card-elevated rounded-xl p-5"
    >
      <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider mb-4 flex items-center space-x-2">
        <TargetIcon className="w-4 h-4 text-accent-cyan" />
        <span>Calibration</span>
      </h3>

      <Motion.div
        variants={staggerContainer}
        initial="hidden"
        animate="visible"
        className="space-y-3"
      >
        {/* Overall Accuracy — hero number */}
        <Motion.div variants={staggerItem} className="text-center pb-2">
          <div className={`text-2xl font-bold font-mono ${accuracyColor(overallAccuracy)}`}>
            {overallAccuracy.toFixed(1)}%
          </div>
          <div className="text-xs text-gray-500 mt-0.5">Overall Accuracy</div>
        </Motion.div>

        {/* Sample count + ECE row */}
        <Motion.div variants={staggerItem} className="flex items-center justify-between">
          <span className="text-xs text-gray-400">Outcomes</span>
          <span className="text-xs font-semibold font-mono">{totalOutcomes}</span>
        </Motion.div>

        {ece != null && (
          <Motion.div variants={staggerItem} className="flex items-center justify-between">
            <span className="text-xs text-gray-400">ECE</span>
            <span className={`text-xs font-semibold font-mono ${ece <= 0.1 ? 'text-success-400' : ece <= 0.2 ? 'text-warning-400' : 'text-danger-400'}`}>
              {ece.toFixed(3)}
            </span>
          </Motion.div>
        )}

        {/* Per-horizon accuracy bars */}
        {horizonBars.length > 0 && (
          <>
            <Motion.div variants={staggerItem} className="border-t border-white/[0.04] pt-2">
              <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Horizon Accuracy</div>
              <div className="space-y-2">
                {horizonBars.map((bar) => (
                  <div key={bar.days} className="flex items-center space-x-2">
                    <span className="text-[11px] text-gray-400 w-6 shrink-0 font-mono">{bar.label}</span>
                    <div className="flex-1 h-1.5 bg-dark-inset rounded-full overflow-hidden">
                      <Motion.div
                        className={`h-full rounded-full ${accuracyBarColor(bar.accuracy)}`}
                        initial={{ width: 0 }}
                        animate={{ width: `${Math.min(100, bar.accuracy)}%` }}
                        transition={{ duration: 0.6, ease: 'easeOut', delay: 0.3 }}
                      />
                    </div>
                    <span className={`text-[11px] font-mono font-semibold w-9 text-right ${accuracyColor(bar.accuracy)}`}>
                      {bar.accuracy}%
                    </span>
                  </div>
                ))}
              </div>
            </Motion.div>
          </>
        )}

        {/* Avg confidence if available */}
        {summary?.avg_confidence != null && (
          <Motion.div variants={staggerItem} className="flex items-center justify-between border-t border-white/[0.04] pt-2">
            <span className="text-xs text-gray-400">Avg Confidence</span>
            <span className="text-xs font-semibold font-mono">
              {(summary.avg_confidence * 100).toFixed(0)}%
            </span>
          </Motion.div>
        )}
      </Motion.div>
    </Motion.div>
  );
};

export default CalibrationCard;
