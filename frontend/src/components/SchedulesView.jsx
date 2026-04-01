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
    style={{
      position: 'relative',
      display: 'inline-flex',
      alignItems: 'center',
      width: 36,
      height: 20,
      borderRadius: 10,
      border: 'none',
      cursor: disabled ? 'not-allowed' : 'pointer',
      background: enabled ? 'rgba(23,201,100,0.4)' : 'rgba(255,255,255,0.1)',
      transition: 'background 0.2s',
      opacity: disabled ? 0.5 : 1,
      padding: 0,
      flexShrink: 0,
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
    background: enabled ? '#17c964' : 'rgba(255,255,255,0.2)',
    boxShadow: enabled ? '0 0 6px rgba(23,201,100,0.5)' : 'none',
    flexShrink: 0,
  }} />
);

/* ──────── Run history row ──────── */
const RunRow = ({ run, fallbackTicker }) => {
  const success = run.success === true || run.success === 1;
  const ticker = run.ticker || fallbackTicker || '—';
  const recColors = {
    BUY: { bg: 'rgba(23,201,100,0.12)', color: '#17c964', border: 'rgba(23,201,100,0.25)' },
    HOLD: { bg: 'rgba(245,165,36,0.12)', color: '#f5a524', border: 'rgba(245,165,36,0.25)' },
    SELL: { bg: 'rgba(243,18,96,0.12)', color: '#f31260', border: 'rgba(243,18,96,0.25)' },
  };
  const rec = run.recommendation;
  const recStyle = recColors[rec];

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '6px 8px',
      borderRadius: 6,
      transition: 'background 0.15s',
    }}
      onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(255,255,255,0.02)'; }}
      onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ fontSize: '0.75rem', color: success ? '#17c964' : '#f31260' }}>
          {success ? '✓' : '✗'}
        </span>
        <span style={{ fontFamily: 'monospace', fontSize: '0.75rem', color: 'rgba(255,255,255,0.7)' }}>
          {ticker}
        </span>
        {rec && recStyle && (
          <span style={{
            fontSize: '0.65rem',
            fontWeight: 700,
            padding: '1px 6px',
            borderRadius: 4,
            background: recStyle.bg,
            color: recStyle.color,
            border: `1px solid ${recStyle.border}`,
          }}>
            {rec}
          </span>
        )}
      </div>
      <span style={{ fontSize: '0.7rem', color: 'rgba(255,255,255,0.3)' }}>
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
    <div style={{
      background: 'rgba(255,255,255,0.02)',
      border: '1px solid rgba(255,255,255,0.06)',
      borderRadius: 12,
      padding: '16px 20px',
      transition: 'border-color 0.15s',
    }}>
      {/* Main row */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <StatusDot enabled={schedule.enabled} />
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <span style={{ fontFamily: 'monospace', fontWeight: 700, fontSize: '0.9rem', color: 'rgba(255,255,255,0.9)' }}>
                {schedule.ticker}
              </span>
              <span style={{
                fontSize: '0.7rem',
                color: 'rgba(255,255,255,0.4)',
                background: 'rgba(255,255,255,0.04)',
                border: '1px solid rgba(255,255,255,0.06)',
                borderRadius: 4,
                padding: '1px 6px',
              }}>
                {formatIntervalLabel(schedule.interval_minutes)}
              </span>
            </div>
            <div style={{ display: 'flex', gap: 16, fontSize: '0.7rem', color: 'rgba(255,255,255,0.35)' }}>
              {schedule.last_run_at && (
                <span>Last: <span style={{ color: 'rgba(255,255,255,0.55)' }}>{formatRelativeTime(schedule.last_run_at)}</span></span>
              )}
              {schedule.next_run_at && schedule.enabled && (
                <span>Next: <span style={{ color: '#006fee' }}>{formatRelativeTime(schedule.next_run_at)}</span></span>
              )}
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <ToggleSwitch enabled={schedule.enabled} onChange={handleToggle} disabled={toggling} />

          {/* Expand runs */}
          <button
            onClick={() => onExpand(schedule.id)}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              color: 'rgba(255,255,255,0.4)',
              fontSize: '0.75rem',
              padding: '4px 6px',
              borderRadius: 6,
              transition: 'color 0.15s',
              transform: expanded ? 'rotate(180deg)' : 'none',
            }}
            onMouseEnter={(e) => { e.currentTarget.style.color = 'rgba(255,255,255,0.8)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.color = 'rgba(255,255,255,0.4)'; }}
            title="View run history"
          >
            ▾
          </button>

          {/* Delete */}
          <button
            onClick={handleDelete}
            disabled={deleting}
            style={{
              background: 'none',
              border: 'none',
              cursor: deleting ? 'not-allowed' : 'pointer',
              color: 'rgba(255,255,255,0.2)',
              fontSize: '0.75rem',
              padding: '4px 6px',
              borderRadius: 6,
              opacity: deleting ? 0.5 : 1,
              transition: 'color 0.15s',
            }}
            onMouseEnter={(e) => { if (!deleting) e.currentTarget.style.color = '#f31260'; }}
            onMouseLeave={(e) => { e.currentTarget.style.color = 'rgba(255,255,255,0.2)'; }}
            title="Delete schedule"
          >
            ✕
          </button>
        </div>
      </div>

      {/* Expanded run history */}
      {expanded && (
        <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px solid rgba(255,255,255,0.05)' }}>
          <div style={{ fontSize: '0.65rem', fontWeight: 700, color: 'rgba(255,255,255,0.3)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 6 }}>
            Recent Runs
          </div>
          {loadingRuns ? (
            <div style={{ textAlign: 'center', padding: '12px', color: 'rgba(255,255,255,0.25)', fontSize: '0.75rem' }}>Loading...</div>
          ) : runs && runs.length > 0 ? (
            <div>
              {runs.map((run, idx) => (
                <RunRow key={run.id || idx} run={run} fallbackTicker={schedule.ticker} />
              ))}
            </div>
          ) : (
            <div style={{ textAlign: 'center', padding: '10px', color: 'rgba(255,255,255,0.2)', fontSize: '0.75rem' }}>No runs yet</div>
          )}
        </div>
      )}
    </div>
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

  const inputStyle = {
    background: 'rgba(255,255,255,0.04)',
    border: '1px solid rgba(255,255,255,0.06)',
    borderRadius: 8,
    padding: '9px 12px',
    fontSize: '0.82rem',
    color: 'rgba(255,255,255,0.9)',
    outline: 'none',
  };

  const activeCount = schedules.filter((s) => s.enabled).length;

  return (
    <div className="flex-1 p-6">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <h2 className="text-lg font-bold text-white/90">Scheduled Analyses</h2>
        <span style={{ fontSize: '0.75rem', color: 'rgba(255,255,255,0.4)' }}>
          {activeCount} active / {schedules.length} total
        </span>
      </div>

      {/* Create form */}
      <div style={{
        background: 'rgba(255,255,255,0.02)',
        border: '1px solid rgba(255,255,255,0.06)',
        borderRadius: 12,
        padding: '20px',
        marginBottom: 24,
      }}>
        <div style={{ fontSize: '0.65rem', fontWeight: 700, color: 'rgba(255,255,255,0.4)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 12 }}>
          New Schedule
        </div>
        <form onSubmit={handleCreate} style={{ display: 'flex', alignItems: 'flex-end', gap: 12 }}>
          <div style={{ flex: '0 0 140px' }}>
            <label style={{ fontSize: '0.65rem', color: 'rgba(255,255,255,0.4)', display: 'block', marginBottom: 4, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              Ticker
            </label>
            <input
              type="text"
              value={tickerInput}
              onChange={(e) => setTickerInput(e.target.value.toUpperCase())}
              placeholder="e.g. NVDA"
              maxLength={5}
              disabled={creating}
              style={{ ...inputStyle, width: '100%', textTransform: 'uppercase' }}
            />
          </div>
          <div style={{ flex: 1 }}>
            <label style={{ fontSize: '0.65rem', color: 'rgba(255,255,255,0.4)', display: 'block', marginBottom: 4, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              Interval
            </label>
            <select
              value={intervalValue}
              onChange={(e) => setIntervalValue(Number(e.target.value))}
              disabled={creating}
              style={{
                ...inputStyle,
                width: '100%',
                cursor: 'pointer',
                appearance: 'none',
              }}
            >
              {INTERVAL_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value} style={{ background: '#1a1a1a' }}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
          <button
            type="submit"
            disabled={creating || !tickerInput.trim()}
            style={{
              background: creating || !tickerInput.trim() ? 'rgba(255,255,255,0.06)' : '#006fee',
              color: creating || !tickerInput.trim() ? 'rgba(255,255,255,0.3)' : '#fff',
              border: 'none',
              borderRadius: 8,
              padding: '9px 20px',
              fontSize: '0.82rem',
              fontWeight: 600,
              cursor: creating || !tickerInput.trim() ? 'not-allowed' : 'pointer',
              whiteSpace: 'nowrap',
            }}
          >
            {creating ? 'Creating...' : 'Create'}
          </button>
        </form>
      </div>

      {/* Schedule list */}
      {loading && schedules.length === 0 ? (
        <div style={{
          background: 'rgba(255,255,255,0.02)',
          border: '1px solid rgba(255,255,255,0.06)',
          borderRadius: 12,
          padding: '48px',
          textAlign: 'center',
          color: 'rgba(255,255,255,0.25)',
          fontSize: '0.82rem',
        }}>
          Loading...
        </div>
      ) : schedules.length === 0 ? (
        <div style={{
          background: 'rgba(255,255,255,0.02)',
          border: '1px solid rgba(255,255,255,0.06)',
          borderRadius: 12,
          padding: '48px',
          textAlign: 'center',
        }}>
          <div style={{ fontSize: '2rem', marginBottom: 10 }}>🕐</div>
          <div style={{ fontSize: '0.82rem', color: 'rgba(255,255,255,0.3)' }}>No scheduled analyses yet.</div>
          <div style={{ fontSize: '0.75rem', color: 'rgba(255,255,255,0.2)', marginTop: 4 }}>Create one above to get started.</div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
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

export default SchedulesView;
