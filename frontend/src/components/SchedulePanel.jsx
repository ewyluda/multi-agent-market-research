/**
 * SchedulePanel - Manage scheduled recurring analyses
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  getSchedules,
  createSchedule,
  updateSchedule,
  deleteSchedule,
  getScheduleWithRuns,
  analyzeTickerAPI,
} from '../utils/api';
import {
  ArrowLeftIcon,
  LoadingSpinner,
  ClockIcon,
  TrashIcon,
  PulseIcon,
  CheckCircleIcon,
  XCircleIcon,
  ChevronDownIcon,
} from './Icons';

const INTERVAL_OPTIONS = [
  { label: 'Every 30 minutes', value: 30 },
  { label: 'Every 1 hour', value: 60 },
  { label: 'Every 4 hours', value: 240 },
  { label: 'Every 12 hours', value: 720 },
  { label: 'Daily', value: 1440 },
  { label: 'Weekly', value: 10080 },
];

/* ──────── Helpers ──────── */

const formatInterval = (minutes) => {
  if (minutes < 60) return `${minutes}m`;
  if (minutes < 1440) return `${minutes / 60}h`;
  if (minutes < 10080) return `${minutes / 1440}d`;
  return `${minutes / 10080}w`;
};

const formatIntervalLabel = (minutes) => {
  const opt = INTERVAL_OPTIONS.find((o) => o.value === minutes);
  if (opt) return opt.label;
  if (minutes < 60) return `Every ${minutes} minutes`;
  if (minutes < 1440) return `Every ${minutes / 60} hours`;
  if (minutes < 10080) return `Every ${minutes / 1440} days`;
  return `Every ${minutes / 10080} weeks`;
};

const formatRelativeTime = (isoString) => {
  if (!isoString) return '—';
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now - date;
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHr = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHr / 24);

  if (diffMs < 0) {
    // Future time (next run)
    const absSec = Math.floor(-diffMs / 1000);
    const absMin = Math.floor(absSec / 60);
    const absHr = Math.floor(absMin / 60);
    const absDay = Math.floor(absHr / 24);
    if (absMin < 1) return 'in <1 min';
    if (absMin < 60) return `in ${absMin} min`;
    if (absHr < 24) return `in ${absHr}h ${absMin % 60}m`;
    return `in ${absDay}d`;
  }

  if (diffMin < 1) return 'just now';
  if (diffMin < 60) return `${diffMin} min ago`;
  if (diffHr < 24) return `${diffHr}h ago`;
  if (diffDay < 7) return `${diffDay}d ago`;
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
};

/* ──────── Toggle Switch ──────── */
const ToggleSwitch = ({ enabled, onChange, disabled }) => (
  <button
    onClick={onChange}
    disabled={disabled}
    className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus:outline-none disabled:opacity-40 ${
      enabled ? 'bg-success/40' : 'bg-zinc-700'
    }`}
  >
    <span
      className={`inline-block h-3.5 w-3.5 rounded-full bg-white transition-transform ${
        enabled ? 'translate-x-[18px]' : 'translate-x-[3px]'
      }`}
    />
  </button>
);

/* ──────── Status Dot ──────── */
const StatusDot = ({ enabled }) => (
  <span
    className={`inline-block w-2 h-2 rounded-full ${
      enabled ? 'bg-success-400 shadow-[0_0_6px_rgba(23,201,100,0.4)]' : 'bg-zinc-600'
    }`}
  />
);

/* ──────── Run row (in expanded section) ──────── */
const RunRow = ({ run, fallbackTicker }) => {
  const success = run.success === true || run.success === 1;
  const ticker = run.ticker || fallbackTicker || '—';
  return (
    <div className="flex items-center justify-between px-3 py-2 hover:bg-white/[0.02] transition-colors rounded">
      <div className="flex items-center space-x-2">
        {success ? (
          <CheckCircleIcon className="w-3 h-3 text-success-400" />
        ) : (
          <XCircleIcon className="w-3 h-3 text-danger-400" />
        )}
        <span className="text-[11px] text-gray-300 font-mono">{ticker}</span>
        {run.recommendation && (
          <span
            className={`text-[10px] font-semibold px-1.5 py-0.5 rounded border ${
              run.recommendation === 'BUY'
                ? 'bg-success/15 text-success-400 border-success/25'
                : run.recommendation === 'SELL'
                ? 'bg-danger/15 text-danger-400 border-danger/25'
                : 'bg-warning/15 text-warning-400 border-warning/25'
            }`}
          >
            {run.recommendation}
          </span>
        )}
      </div>
      <span className="text-[11px] text-gray-500">{formatRelativeTime(run.timestamp || run.completed_at)}</span>
    </div>
  );
};

/* ──────── Schedule card ──────── */
const ScheduleCard = ({ schedule, onToggle, onDelete, onRunNow, onExpand, expanded, runs, loadingRuns }) => {
  const [toggling, setToggling] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [running, setRunning] = useState(false);

  const handleToggle = async () => {
    setToggling(true);
    await onToggle(schedule.id, !schedule.enabled);
    setToggling(false);
  };

  const handleDelete = async () => {
    setDeleting(true);
    await onDelete(schedule.id);
    setDeleting(false);
  };

  const handleRunNow = async () => {
    setRunning(true);
    await onRunNow(schedule.ticker);
    setRunning(false);
  };

  return (
    <div className="glass-card-elevated rounded-xl p-5 transition-all">
      {/* Main row */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <StatusDot enabled={schedule.enabled} />
          <div>
            <div className="flex items-center space-x-2">
              <span className="font-mono text-sm font-semibold">{schedule.ticker}</span>
              <span className="text-[11px] text-gray-500 bg-dark-inset px-2 py-0.5 rounded border border-dark-border">
                {formatIntervalLabel(schedule.interval_minutes)}
              </span>
            </div>
            <div className="flex items-center space-x-3 mt-1">
              {schedule.last_run_at && (
                <span className="text-[11px] text-gray-500">
                  Last: <span className="text-gray-400">{formatRelativeTime(schedule.last_run_at)}</span>
                </span>
              )}
              {schedule.next_run_at && schedule.enabled && (
                <span className="text-[11px] text-gray-500">
                  Next: <span className="text-accent-blue">{formatRelativeTime(schedule.next_run_at)}</span>
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          {/* Run Now */}
          <button
            onClick={handleRunNow}
            disabled={running}
            className="flex items-center space-x-1 px-2.5 py-1.5 bg-primary/15 text-accent-blue text-[11px] font-medium rounded-lg hover:bg-primary/25 disabled:opacity-40 transition-all"
          >
            {running ? (
              <><LoadingSpinner size={12} /><span>Running...</span></>
            ) : (
              <><PulseIcon className="w-3 h-3" /><span>Run Now</span></>
            )}
          </button>

          {/* Toggle */}
          <ToggleSwitch enabled={schedule.enabled} onChange={handleToggle} disabled={toggling} />

          {/* Expand runs */}
          <button
            onClick={() => onExpand(schedule.id)}
            className={`p-1.5 rounded-lg text-gray-500 hover:text-gray-300 hover:bg-white/5 transition-all ${
              expanded ? 'rotate-180' : ''
            }`}
            title="View recent runs"
          >
            <ChevronDownIcon className="w-3.5 h-3.5" />
          </button>

          {/* Delete */}
          <button
            onClick={handleDelete}
            disabled={deleting}
            className="p-1.5 rounded-lg text-gray-600 hover:text-danger-400 hover:bg-danger/10 transition-all disabled:opacity-40"
            title="Delete schedule"
          >
            <TrashIcon className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Expanded: recent runs */}
      {expanded && (
        <div className="mt-4 pt-3 border-t border-white/5 animate-fade-in">
          <h4 className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider mb-2">Recent Runs</h4>
          {loadingRuns ? (
            <div className="flex items-center justify-center py-4">
              <LoadingSpinner size={14} className="text-gray-500" />
            </div>
          ) : runs && runs.length > 0 ? (
            <div className="space-y-0.5">
              {runs.map((run, idx) => (
                <RunRow key={run.id || idx} run={run} fallbackTicker={schedule.ticker} />
              ))}
            </div>
          ) : (
            <p className="text-[11px] text-gray-600 text-center py-3">No runs yet</p>
          )}
        </div>
      )}
    </div>
  );
};

/* ──────── Main SchedulePanel component ──────── */
const SchedulePanel = ({ onBack }) => {
  const [schedules, setSchedules] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Form state
  const [tickerInput, setTickerInput] = useState('');
  const [intervalValue, setIntervalValue] = useState(60);
  const [creating, setCreating] = useState(false);

  // Expanded schedule (to show runs)
  const [expandedId, setExpandedId] = useState(null);
  const [runs, setRuns] = useState([]);
  const [loadingRuns, setLoadingRuns] = useState(false);

  // Load all schedules
  const loadSchedules = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getSchedules();
      setSchedules(data.schedules || data || []);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to load schedules');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSchedules();
  }, [loadSchedules]);

  // Create schedule
  const handleCreate = async (e) => {
    e.preventDefault();
    if (!tickerInput.trim()) return;
    setCreating(true);
    setError(null);
    try {
      await createSchedule(tickerInput.trim().toUpperCase(), intervalValue);
      setTickerInput('');
      setIntervalValue(60);
      await loadSchedules();
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to create schedule');
    } finally {
      setCreating(false);
    }
  };

  // Toggle enable/disable
  const handleToggle = async (scheduleId, enabled) => {
    setError(null);
    try {
      await updateSchedule(scheduleId, { enabled });
      setSchedules((prev) =>
        prev.map((s) => (s.id === scheduleId ? { ...s, enabled } : s))
      );
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to update schedule');
    }
  };

  // Delete schedule
  const handleDelete = async (scheduleId) => {
    setError(null);
    try {
      await deleteSchedule(scheduleId);
      if (expandedId === scheduleId) {
        setExpandedId(null);
        setRuns([]);
      }
      setSchedules((prev) => prev.filter((s) => s.id !== scheduleId));
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to delete schedule');
    }
  };

  // Run now (trigger analysis via existing API)
  const handleRunNow = async (ticker) => {
    setError(null);
    try {
      await analyzeTickerAPI(ticker);
      // Refresh schedules to get updated last_run_at
      await loadSchedules();
    } catch (err) {
      setError(`Analysis failed for ${ticker}: ${err.message}`);
    }
  };

  // Expand/collapse runs
  const handleExpand = async (scheduleId) => {
    if (expandedId === scheduleId) {
      setExpandedId(null);
      setRuns([]);
      return;
    }
    setExpandedId(scheduleId);
    setLoadingRuns(true);
    try {
      const data = await getScheduleWithRuns(scheduleId);
      setRuns(data.runs || data.recent_runs || []);
    } catch (err) {
      setRuns([]);
    } finally {
      setLoadingRuns(false);
    }
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
            <ClockIcon className="w-5 h-5 text-accent-purple" />
            <h2 className="text-lg font-bold tracking-tight">Scheduled Analyses</h2>
          </div>
        </div>
        <span className="text-xs text-gray-500">
          {schedules.filter((s) => s.enabled).length} active / {schedules.length} total
        </span>
      </div>

      {/* Create schedule form */}
      <div className="glass-card-elevated rounded-xl p-5 mb-6">
        <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
          New Schedule
        </h3>
        <form onSubmit={handleCreate} className="flex items-end space-x-3">
          <div className="flex-1">
            <label className="text-xs font-medium text-gray-500 mb-1 block">Ticker</label>
            <input
              type="text"
              value={tickerInput}
              onChange={(e) => setTickerInput(e.target.value.toUpperCase())}
              placeholder="e.g. NVDA"
              className="w-full px-3 py-2 bg-dark-inset border border-dark-border rounded-lg text-sm focus:outline-none focus:ring-1 focus:ring-primary/30 focus:border-primary/40 transition-all uppercase"
              maxLength={5}
              disabled={creating}
            />
          </div>
          <div className="flex-1">
            <label className="text-xs font-medium text-gray-500 mb-1 block">Interval</label>
            <select
              value={intervalValue}
              onChange={(e) => setIntervalValue(Number(e.target.value))}
              className="w-full px-3 py-2 bg-dark-inset border border-dark-border rounded-lg text-sm focus:outline-none focus:ring-1 focus:ring-primary/30 focus:border-primary/40 transition-all appearance-none cursor-pointer"
              disabled={creating}
            >
              {INTERVAL_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
          <button
            type="submit"
            disabled={creating || !tickerInput.trim()}
            className="flex items-center space-x-1.5 px-4 py-2 bg-gradient-to-r from-primary-600 to-primary hover:from-primary hover:to-primary-400 disabled:from-zinc-700 disabled:to-zinc-700 disabled:cursor-not-allowed rounded-lg text-sm font-medium transition-all"
          >
            {creating ? (
              <><LoadingSpinner size={14} /><span>Creating...</span></>
            ) : (
              <><ClockIcon className="w-3.5 h-3.5" /><span>Create</span></>
            )}
          </button>
        </form>
      </div>

      {/* Schedule list */}
      {loading && schedules.length === 0 ? (
        <div className="glass-card-elevated rounded-xl p-12 text-center">
          <LoadingSpinner size={20} className="text-gray-500 mx-auto" />
        </div>
      ) : schedules.length === 0 ? (
        <div className="glass-card-elevated rounded-xl p-12 text-center">
          <ClockIcon className="w-10 h-10 text-gray-600 mx-auto mb-3" />
          <p className="text-sm text-gray-500">No scheduled analyses yet.</p>
          <p className="text-xs text-gray-600 mt-1">Create one above to get started.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {schedules.map((schedule) => (
            <ScheduleCard
              key={schedule.id}
              schedule={schedule}
              onToggle={handleToggle}
              onDelete={handleDelete}
              onRunNow={handleRunNow}
              onExpand={handleExpand}
              expanded={expandedId === schedule.id}
              runs={expandedId === schedule.id ? runs : []}
              loadingRuns={expandedId === schedule.id && loadingRuns}
            />
          ))}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="mt-4 p-3 bg-danger/10 border border-danger/30 rounded-lg text-danger-400 text-sm animate-fade-in">
          {error}
        </div>
      )}
    </div>
  );
};

export default SchedulePanel;
