/**
 * SchedulesView - Full-page scheduled analyses management
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  getSchedules,
  createSchedule,
  updateSchedule,
  deleteSchedule,
  getScheduleWithRuns,
} from '../utils/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

const INTERVAL_OPTIONS = [
  { label: 'Every 30 minutes', value: 30 },
  { label: 'Every 1 hour', value: 60 },
  { label: 'Every 4 hours', value: 240 },
  { label: 'Every 12 hours', value: 720 },
  { label: 'Daily', value: 1440 },
  { label: 'Weekly', value: 10080 },
];

/* ──────── Helpers ──────── */
const formatIntervalLabel = (minutes) => {
  const opt = INTERVAL_OPTIONS.find((o) => o.value === minutes);
  if (opt) return opt.label;
  if (minutes < 60) return `Every ${minutes}m`;
  if (minutes < 1440) return `Every ${minutes / 60}h`;
  if (minutes < 10080) return `Every ${minutes / 1440}d`;
  return `Every ${minutes / 10080}w`;
};

const formatRelativeTime = (isoString) => {
  if (!isoString) return '—';
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now - date;

  if (diffMs < 0) {
    const absMin = Math.floor(-diffMs / 60000);
    const absHr = Math.floor(absMin / 60);
    const absDay = Math.floor(absHr / 24);
    if (absMin < 1) return 'in <1 min';
    if (absMin < 60) return `in ${absMin}m`;
    if (absHr < 24) return `in ${absHr}h`;
    return `in ${absDay}d`;
  }

  const diffMin = Math.floor(diffMs / 60000);
  const diffHr = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHr / 24);
  if (diffMin < 1) return 'just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffHr < 24) return `${diffHr}h ago`;
  if (diffDay < 7) return `${diffDay}d ago`;
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
};

/* ──────── Toggle switch ──────── */
const ToggleSwitch = ({ enabled, onChange, disabled }) => (
  <button
    onClick={onChange}
    disabled={disabled}
    className="relative inline-flex items-center rounded-full flex-shrink-0 transition-colors"
    style={{
      width: 36,
      height: 20,
      border: 'none',
      cursor: disabled ? 'not-allowed' : 'pointer',
      background: enabled ? 'rgba(23,201,100,0.4)' : 'rgba(255,255,255,0.1)',
      opacity: disabled ? 0.5 : 1,
      padding: 0,
    }}
  >
    <span style={{
      display: 'inline-block',
      width: 14,
      height: 14,
      borderRadius: '50%',
      background: '#fff',
      transform: enabled ? 'translateX(18px)' : 'translateX(3px)',
      transition: 'transform 0.2s',
    }} />
  </button>
);

/* ──────── Status dot ──────── */
const StatusDot = ({ enabled }) => (
  <span style={{
    display: 'inline-block',
    width: 8,
    height: 8,
    borderRadius: '50%',
    background: enabled ? 'var(--success)' : 'rgba(255,255,255,0.2)',
    boxShadow: enabled ? '0 0 6px rgba(23,201,100,0.5)' : 'none',
    flexShrink: 0,
  }} />
);

/* ──────── Run history row ──────── */
const RunRow = ({ run, fallbackTicker }) => {
  const success = run.success === true || run.success === 1;
  const ticker = run.ticker || fallbackTicker || '—';
  const rec = run.recommendation;
  const recVariant = { BUY: 'success', HOLD: 'warning', SELL: 'danger' }[rec] || 'secondary';

  return (
    <div
      className="flex items-center justify-between px-2 py-1.5 rounded-md transition-colors hover:bg-white/[0.02]"
    >
      <div className="flex items-center gap-2">
        <span className="text-[0.75rem]" style={{ color: success ? 'var(--success)' : 'var(--danger)' }}>
          {success ? '✓' : '✗'}
        </span>
        <span className="font-data text-[0.75rem]" style={{ color: 'var(--text-secondary)' }}>
          {ticker}
        </span>
        {rec && (
          <Badge variant={recVariant} className="text-[0.6rem] px-1.5 py-0">
            {rec}
          </Badge>
        )}
      </div>
      <span className="text-[0.7rem] font-data" style={{ color: 'var(--text-muted)' }}>
        {formatRelativeTime(run.timestamp || run.completed_at)}
      </span>
    </div>
  );
};

/* ──────── Schedule card ──────── */
const ScheduleCard = ({ schedule, onToggle, onDelete, expanded, onExpand, runs, loadingRuns }) => {
  const [toggling, setToggling] = useState(false);
  const [deleting, setDeleting] = useState(false);

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

  return (
    <Card>
      <CardContent className="pt-4 pb-4">
        {/* Main row */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <StatusDot enabled={schedule.enabled} />
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="font-data font-bold text-[0.9rem]" style={{ color: 'var(--text-primary)' }}>
                  {schedule.ticker}
                </span>
                <Badge variant="secondary" className="text-[0.65rem] px-1.5 py-0">
                  {formatIntervalLabel(schedule.interval_minutes)}
                </Badge>
              </div>
              <div className="flex gap-4 text-[0.7rem]" style={{ color: 'var(--text-muted)' }}>
                {schedule.last_run_at && (
                  <span>Last: <span style={{ color: 'var(--text-secondary)' }}>{formatRelativeTime(schedule.last_run_at)}</span></span>
                )}
                {schedule.next_run_at && schedule.enabled && (
                  <span>Next: <span style={{ color: 'var(--primary)' }}>{formatRelativeTime(schedule.next_run_at)}</span></span>
                )}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2.5">
            <ToggleSwitch enabled={schedule.enabled} onChange={handleToggle} disabled={toggling} />

            {/* Expand runs */}
            <button
              onClick={() => onExpand(schedule.id)}
              className="text-[0.75rem] px-1.5 py-1 rounded-md transition-colors"
              style={{
                color: 'var(--text-muted)',
                transform: expanded ? 'rotate(180deg)' : 'none',
                background: 'none',
                border: 'none',
                cursor: 'pointer',
              }}
              onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--text-primary)'; }}
              onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--text-muted)'; }}
              title="View run history"
            >
              ▾
            </button>

            {/* Delete */}
            <button
              onClick={handleDelete}
              disabled={deleting}
              className="text-[0.75rem] px-1.5 py-1 rounded-md transition-colors"
              style={{
                color: 'var(--text-muted)',
                background: 'none',
                border: 'none',
                cursor: deleting ? 'not-allowed' : 'pointer',
                opacity: deleting ? 0.5 : 1,
              }}
              onMouseEnter={(e) => { if (!deleting) e.currentTarget.style.color = 'var(--danger)'; }}
              onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--text-muted)'; }}
              title="Delete schedule"
            >
              ✕
            </button>
          </div>
        </div>

        {/* Expanded run history */}
        {expanded && (
          <div className="mt-3 pt-3 border-t border-white/[0.05]">
            <div className="text-[0.65rem] font-bold uppercase tracking-widest mb-1.5" style={{ color: 'var(--text-muted)' }}>
              Recent Runs
            </div>
            {loadingRuns ? (
              <div className="text-center py-3 text-[0.75rem]" style={{ color: 'var(--text-muted)' }}>Loading...</div>
            ) : runs && runs.length > 0 ? (
              <div>
                {runs.map((run, idx) => (
                  <RunRow key={run.id || idx} run={run} fallbackTicker={schedule.ticker} />
                ))}
              </div>
            ) : (
              <div className="text-center py-2.5 text-[0.75rem]" style={{ color: 'var(--text-muted)' }}>No runs yet</div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

/* ──────── Main SchedulesView component ──────── */
const SchedulesView = () => {
  const [schedules, setSchedules] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const [tickerInput, setTickerInput] = useState('');
  const [intervalValue, setIntervalValue] = useState(60);
  const [creating, setCreating] = useState(false);

  const [expandedId, setExpandedId] = useState(null);
  const [runs, setRuns] = useState([]);
  const [loadingRuns, setLoadingRuns] = useState(false);

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

  const handleToggle = async (scheduleId, enabled) => {
    setError(null);
    try {
      await updateSchedule(scheduleId, { enabled });
      setSchedules((prev) => prev.map((s) => s.id === scheduleId ? { ...s, enabled } : s));
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to update schedule');
    }
  };

  const handleDelete = async (scheduleId) => {
    setError(null);
    try {
      await deleteSchedule(scheduleId);
      if (expandedId === scheduleId) { setExpandedId(null); setRuns([]); }
      setSchedules((prev) => prev.filter((s) => s.id !== scheduleId));
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to delete schedule');
    }
  };

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
    } catch {
      setRuns([]);
    } finally {
      setLoadingRuns(false);
    }
  };

  const activeCount = schedules.filter((s) => s.enabled).length;

  const selectStyle = {
    background: 'rgba(255,255,255,0.04)',
    border: '1px solid rgba(255,255,255,0.06)',
    borderRadius: 8,
    padding: '9px 12px',
    fontSize: '0.82rem',
    color: 'rgba(255,255,255,0.9)',
    outline: 'none',
    cursor: 'pointer',
    appearance: 'none',
    width: '100%',
  };

  return (
    <div className="flex-1 p-6">
      <div className="flex items-center justify-between mb-5">
        <h2 className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>Scheduled Analyses</h2>
        <span className="text-[0.75rem]" style={{ color: 'var(--text-muted)' }}>
          {activeCount} active / {schedules.length} total
        </span>
      </div>

      {/* Create form */}
      <Card className="mb-6">
        <CardHeader className="pb-3">
          <CardTitle className="text-xs uppercase tracking-widest" style={{ color: 'var(--text-muted)' }}>
            New Schedule
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          <form onSubmit={handleCreate} className="flex items-end gap-3">
            <div style={{ flex: '0 0 140px' }}>
              <label className="text-[0.65rem] font-semibold uppercase tracking-wider block mb-1" style={{ color: 'var(--text-muted)' }}>
                Ticker
              </label>
              <Input
                type="text"
                value={tickerInput}
                onChange={(e) => setTickerInput(e.target.value.toUpperCase())}
                placeholder="e.g. NVDA"
                maxLength={5}
                disabled={creating}
                className="uppercase font-data"
              />
            </div>
            <div className="flex-1">
              <label className="text-[0.65rem] font-semibold uppercase tracking-wider block mb-1" style={{ color: 'var(--text-muted)' }}>
                Interval
              </label>
              <select
                value={intervalValue}
                onChange={(e) => setIntervalValue(Number(e.target.value))}
                disabled={creating}
                style={selectStyle}
              >
                {INTERVAL_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value} style={{ background: '#1a1a1a' }}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
            <Button
              type="submit"
              disabled={creating || !tickerInput.trim()}
              className="whitespace-nowrap"
            >
              {creating ? 'Creating...' : 'Create'}
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Schedule list */}
      {loading && schedules.length === 0 ? (
        <Card>
          <CardContent className="pt-12 pb-12 text-center text-[0.82rem]" style={{ color: 'var(--text-muted)' }}>
            Loading...
          </CardContent>
        </Card>
      ) : schedules.length === 0 ? (
        <Card>
          <CardContent className="pt-12 pb-12 text-center">
            <div className="text-2xl mb-2.5">🕐</div>
            <div className="text-[0.82rem] mb-1" style={{ color: 'var(--text-muted)' }}>No scheduled analyses yet.</div>
            <div className="text-[0.75rem]" style={{ color: 'var(--text-muted)' }}>Create one above to get started.</div>
          </CardContent>
        </Card>
      ) : (
        <div className="flex flex-col gap-2.5">
          {schedules.map((schedule) => (
            <ScheduleCard
              key={schedule.id}
              schedule={schedule}
              onToggle={handleToggle}
              onDelete={handleDelete}
              expanded={expandedId === schedule.id}
              onExpand={handleExpand}
              runs={expandedId === schedule.id ? runs : []}
              loadingRuns={expandedId === schedule.id && loadingRuns}
            />
          ))}
        </div>
      )}

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

export default SchedulesView;
