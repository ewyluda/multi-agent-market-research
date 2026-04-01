/**
 * AlertsView - Full-page alert rules management + triggered notifications
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  getAlertRules,
  createAlertRule,
  updateAlertRule,
  deleteAlertRule,
  getAlertNotifications,
  acknowledgeAlert,
} from '../utils/api';

const RULE_TYPE_OPTIONS = [
  { value: 'recommendation_change', label: 'Recommendation Change', needsThreshold: false },
  { value: 'score_above', label: 'Score Above Threshold', needsThreshold: true },
  { value: 'score_below', label: 'Score Below Threshold', needsThreshold: true },
  { value: 'confidence_above', label: 'Confidence Above Threshold', needsThreshold: true },
  { value: 'confidence_below', label: 'Confidence Below Threshold', needsThreshold: true },
  { value: 'ev_above', label: 'EV Above Threshold', needsThreshold: true },
  { value: 'ev_below', label: 'EV Below Threshold', needsThreshold: true },
  { value: 'regime_change', label: 'Regime Change', needsThreshold: false },
  { value: 'data_quality_below', label: 'Data Quality Below', needsThreshold: true },
  { value: 'calibration_drop', label: 'Calibration Drop', needsThreshold: true },
];

/* ──────── Helpers ──────── */
const formatRuleType = (ruleType) => {
  const opt = RULE_TYPE_OPTIONS.find((o) => o.value === ruleType);
  return opt ? opt.label : ruleType;
};

const formatThreshold = (ruleType, threshold) => {
  if (threshold == null) return '';
  if (ruleType.startsWith('confidence_') || ruleType === 'calibration_drop') {
    return `${(threshold * 100).toFixed(0)}%`;
  }
  return threshold.toString();
};

const formatRelativeTime = (isoString) => {
  if (!isoString) return '—';
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now - date;
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

/* ──────── Rule card ──────── */
const RuleCard = ({ rule, onToggle, onDelete }) => {
  const [toggling, setToggling] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const handleToggle = async () => {
    setToggling(true);
    await onToggle(rule.id, !rule.enabled);
    setToggling(false);
  };

  const handleDelete = async () => {
    setDeleting(true);
    await onDelete(rule.id);
    setDeleting(false);
  };

  return (
    <div style={{
      background: 'rgba(255,255,255,0.02)',
      border: '1px solid rgba(255,255,255,0.06)',
      borderRadius: 10,
      padding: '14px 18px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      transition: 'border-color 0.15s',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        {/* Status dot */}
        <span style={{
          display: 'inline-block',
          width: 8,
          height: 8,
          borderRadius: '50%',
          background: rule.enabled ? '#17c964' : 'rgba(255,255,255,0.2)',
          boxShadow: rule.enabled ? '0 0 6px rgba(23,201,100,0.5)' : 'none',
          flexShrink: 0,
        }} />
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <span style={{ fontFamily: 'monospace', fontWeight: 700, fontSize: '0.85rem', color: 'rgba(255,255,255,0.9)' }}>
              {rule.ticker}
            </span>
            <span style={{
              fontSize: '0.7rem',
              color: 'rgba(255,255,255,0.45)',
              background: 'rgba(255,255,255,0.04)',
              border: '1px solid rgba(255,255,255,0.06)',
              borderRadius: 4,
              padding: '1px 6px',
            }}>
              {formatRuleType(rule.rule_type)}
            </span>
            {rule.threshold != null && (
              <span style={{
                fontSize: '0.7rem',
                fontFamily: 'monospace',
                fontWeight: 600,
                color: '#006fee',
                background: 'rgba(0,111,238,0.1)',
                border: '1px solid rgba(0,111,238,0.2)',
                borderRadius: 4,
                padding: '1px 6px',
              }}>
                {formatThreshold(rule.rule_type, rule.threshold)}
              </span>
            )}
          </div>
          <div style={{ fontSize: '0.7rem', color: 'rgba(255,255,255,0.3)' }}>
            Created {formatRelativeTime(rule.created_at)}
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <ToggleSwitch enabled={rule.enabled} onChange={handleToggle} disabled={toggling} />
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
          title="Delete rule"
        >
          ✕
        </button>
      </div>
    </div>
  );
};

/* ──────── Notification severity ──────── */
const getSeverityStyle = (notification) => {
  const ruleType = notification.trigger_context?.rule_type || '';
  if (ruleType.includes('sell') || ruleType === 'recommendation_change') {
    return { dot: '#f31260', bg: 'rgba(243,18,96,0.06)' };
  }
  if (ruleType.includes('above') || ruleType.includes('buy')) {
    return { dot: '#17c964', bg: 'rgba(23,201,100,0.04)' };
  }
  return { dot: '#f5a524', bg: 'rgba(245,165,36,0.04)' };
};

/* ──────── Notification row ──────── */
const NotificationRow = ({ notification, onAcknowledge }) => {
  const [acknowledging, setAcknowledging] = useState(false);
  const severity = getSeverityStyle(notification);
  const triggerCtx = notification.trigger_context || {};

  const handleAck = async () => {
    setAcknowledging(true);
    await onAcknowledge(notification.id);
    setAcknowledging(false);
  };

  return (
    <div style={{
      display: 'flex',
      alignItems: 'flex-start',
      justifyContent: 'space-between',
      padding: '12px 16px',
      borderRadius: 10,
      background: notification.acknowledged ? 'transparent' : severity.bg,
      border: notification.acknowledged ? '1px solid rgba(255,255,255,0.04)' : '1px solid rgba(255,255,255,0.06)',
      opacity: notification.acknowledged ? 0.5 : 1,
      gap: 12,
      transition: 'all 0.15s',
    }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10, flex: 1, minWidth: 0 }}>
        {/* Severity dot */}
        <span style={{
          display: 'inline-block',
          width: 7,
          height: 7,
          borderRadius: '50%',
          background: notification.acknowledged ? 'rgba(255,255,255,0.2)' : severity.dot,
          marginTop: 4,
          flexShrink: 0,
        }} />
        <div style={{ minWidth: 0, flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 2, flexWrap: 'wrap' }}>
            <span style={{ fontFamily: 'monospace', fontWeight: 700, fontSize: '0.82rem', color: 'rgba(255,255,255,0.85)' }}>
              {notification.ticker}
            </span>
            <span style={{ fontSize: '0.75rem', color: 'rgba(255,255,255,0.55)' }}>
              {notification.message}
            </span>
          </div>

          {triggerCtx.rule_type && (
            <div style={{ fontSize: '0.7rem', color: 'rgba(255,255,255,0.35)', marginBottom: 2 }}>
              Rule: {formatRuleType(triggerCtx.rule_type)}
              {triggerCtx.threshold != null && ` — Threshold: ${formatThreshold(triggerCtx.rule_type, triggerCtx.threshold)}`}
            </div>
          )}

          <div style={{ display: 'flex', gap: 12, fontSize: '0.7rem', color: 'rgba(255,255,255,0.3)', marginTop: 2 }}>
            {notification.previous_value && (
              <span>From: <span style={{ color: 'rgba(255,255,255,0.5)' }}>{notification.previous_value}</span></span>
            )}
            {notification.current_value && (
              <span>To: <span style={{ color: 'rgba(255,255,255,0.5)' }}>{notification.current_value}</span></span>
            )}
            <span>{formatRelativeTime(notification.created_at)}</span>
          </div>

          {notification.suggested_action && (
            <div style={{
              marginTop: 8,
              padding: '8px 10px',
              borderRadius: 6,
              background: 'rgba(0,111,238,0.08)',
              border: '1px solid rgba(0,111,238,0.15)',
            }}>
              <div style={{ fontSize: '0.6rem', color: '#006fee', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 3 }}>
                Suggested Action
              </div>
              <div style={{ fontSize: '0.75rem', color: 'rgba(255,255,255,0.7)', lineHeight: 1.5 }}>
                {notification.suggested_action}
              </div>
            </div>
          )}
        </div>
      </div>

      {!notification.acknowledged && (
        <button
          onClick={handleAck}
          disabled={acknowledging}
          style={{
            background: 'rgba(23,201,100,0.1)',
            border: '1px solid rgba(23,201,100,0.2)',
            borderRadius: 6,
            padding: '4px 10px',
            fontSize: '0.7rem',
            fontWeight: 600,
            color: '#17c964',
            cursor: acknowledging ? 'not-allowed' : 'pointer',
            opacity: acknowledging ? 0.5 : 1,
            whiteSpace: 'nowrap',
            flexShrink: 0,
            transition: 'background 0.15s',
          }}
          onMouseEnter={(e) => { if (!acknowledging) e.currentTarget.style.background = 'rgba(23,201,100,0.18)'; }}
          onMouseLeave={(e) => { e.currentTarget.style.background = 'rgba(23,201,100,0.1)'; }}
        >
          {acknowledging ? '...' : 'Dismiss'}
        </button>
      )}
    </div>
  );
};

/* ──────── Main AlertsView component ──────── */
const AlertsView = () => {
  const [rules, setRules] = useState([]);
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const [tickerInput, setTickerInput] = useState('');
  const [ruleType, setRuleType] = useState('recommendation_change');
  const [threshold, setThreshold] = useState('');
  const [creating, setCreating] = useState(false);

  const [showUnacknowledgedOnly, setShowUnacknowledgedOnly] = useState(false);

  const selectedRuleOption = RULE_TYPE_OPTIONS.find((o) => o.value === ruleType);
  const needsThreshold = selectedRuleOption?.needsThreshold ?? false;

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [rulesData, notifsData] = await Promise.all([
        getAlertRules(),
        getAlertNotifications(showUnacknowledgedOnly),
      ]);
      setRules(rulesData.rules || rulesData || []);
      setNotifications(notifsData.notifications || notifsData || []);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to load alerts');
    } finally {
      setLoading(false);
    }
  }, [showUnacknowledgedOnly]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!tickerInput.trim()) return;
    setCreating(true);
    setError(null);
    try {
      const thresholdVal = needsThreshold && threshold !== '' ? parseFloat(threshold) : null;
      await createAlertRule(tickerInput.trim().toUpperCase(), ruleType, thresholdVal);
      setTickerInput('');
      setRuleType('recommendation_change');
      setThreshold('');
      await loadData();
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to create alert rule');
    } finally {
      setCreating(false);
    }
  };

  const handleToggle = async (ruleId, enabled) => {
    setError(null);
    try {
      await updateAlertRule(ruleId, { enabled });
      setRules((prev) => prev.map((r) => r.id === ruleId ? { ...r, enabled } : r));
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to update rule');
    }
  };

  const handleDelete = async (ruleId) => {
    setError(null);
    try {
      await deleteAlertRule(ruleId);
      setRules((prev) => prev.filter((r) => r.id !== ruleId));
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to delete rule');
    }
  };

  const handleAcknowledge = async (notificationId) => {
    setError(null);
    try {
      await acknowledgeAlert(notificationId);
      setNotifications((prev) =>
        prev.map((n) => n.id === notificationId ? { ...n, acknowledged: true } : n)
      );
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to acknowledge alert');
    }
  };

  const filteredNotifications = showUnacknowledgedOnly
    ? notifications.filter((n) => !n.acknowledged)
    : notifications;

  const unreadCount = notifications.filter((n) => !n.acknowledged).length;

  const inputStyle = {
    background: 'rgba(255,255,255,0.04)',
    border: '1px solid rgba(255,255,255,0.06)',
    borderRadius: 8,
    padding: '9px 12px',
    fontSize: '0.82rem',
    color: 'rgba(255,255,255,0.9)',
    outline: 'none',
  };

  const cardStyle = {
    background: 'rgba(255,255,255,0.02)',
    border: '1px solid rgba(255,255,255,0.06)',
    borderRadius: 12,
    padding: '20px',
    marginBottom: 24,
  };

  const sectionLabelStyle = {
    fontSize: '0.65rem',
    fontWeight: 700,
    color: 'rgba(255,255,255,0.4)',
    textTransform: 'uppercase',
    letterSpacing: '0.08em',
    marginBottom: 12,
  };

  return (
    <div className="flex-1 p-6">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <h2 className="text-lg font-bold text-white/90">Alerts</h2>
        <span style={{ fontSize: '0.75rem', color: 'rgba(255,255,255,0.4)' }}>
          {rules.filter((r) => r.enabled).length} active rules / {unreadCount} unread
        </span>
      </div>

      {/* Create rule form */}
      <div style={cardStyle}>
        <div style={sectionLabelStyle}>New Alert Rule</div>
        <form onSubmit={handleCreate} style={{ display: 'flex', alignItems: 'flex-end', gap: 12, flexWrap: 'wrap' }}>
          <div style={{ flex: '0 0 120px' }}>
            <label style={{ ...sectionLabelStyle, marginBottom: 4 }}>Ticker</label>
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
          <div style={{ flex: 1, minWidth: 180 }}>
            <label style={{ ...sectionLabelStyle, marginBottom: 4 }}>Rule Type</label>
            <select
              value={ruleType}
              onChange={(e) => { setRuleType(e.target.value); setThreshold(''); }}
              disabled={creating}
              style={{ ...inputStyle, width: '100%', cursor: 'pointer', appearance: 'none' }}
            >
              {RULE_TYPE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value} style={{ background: '#1a1a1a' }}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
          {needsThreshold && (
            <div style={{ flex: '0 0 130px' }}>
              <label style={{ ...sectionLabelStyle, marginBottom: 4 }}>Threshold</label>
              <input
                type="number"
                step="any"
                value={threshold}
                onChange={(e) => setThreshold(e.target.value)}
                placeholder={
                  ruleType.startsWith('confidence_') || ruleType === 'calibration_drop'
                    ? '0.0–1.0'
                    : ruleType.includes('quality')
                      ? '0–100'
                      : '–100 to 100'
                }
                disabled={creating}
                style={{ ...inputStyle, width: '100%' }}
              />
            </div>
          )}
          <button
            type="submit"
            disabled={creating || !tickerInput.trim() || (needsThreshold && threshold === '')}
            style={{
              background: (creating || !tickerInput.trim() || (needsThreshold && threshold === '')) ? 'rgba(255,255,255,0.06)' : '#006fee',
              color: (creating || !tickerInput.trim() || (needsThreshold && threshold === '')) ? 'rgba(255,255,255,0.3)' : '#fff',
              border: 'none',
              borderRadius: 8,
              padding: '9px 20px',
              fontSize: '0.82rem',
              fontWeight: 600,
              cursor: (creating || !tickerInput.trim() || (needsThreshold && threshold === '')) ? 'not-allowed' : 'pointer',
              whiteSpace: 'nowrap',
            }}
          >
            {creating ? 'Creating...' : 'Create'}
          </button>
        </form>
      </div>

      {/* Active rules */}
      <div style={{ marginBottom: 28 }}>
        <div style={sectionLabelStyle}>Alert Rules</div>
        {loading && rules.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '32px', color: 'rgba(255,255,255,0.25)', fontSize: '0.82rem' }}>Loading...</div>
        ) : rules.length === 0 ? (
          <div style={{
            background: 'rgba(255,255,255,0.02)',
            border: '1px solid rgba(255,255,255,0.06)',
            borderRadius: 12,
            padding: '32px',
            textAlign: 'center',
            color: 'rgba(255,255,255,0.25)',
            fontSize: '0.82rem',
          }}>
            No alert rules yet. Create one above.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {rules.map((rule) => (
              <RuleCard key={rule.id} rule={rule} onToggle={handleToggle} onDelete={handleDelete} />
            ))}
          </div>
        )}
      </div>

      {/* Notifications */}
      <div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
          <div style={sectionLabelStyle}>Notifications</div>
          <button
            onClick={() => setShowUnacknowledgedOnly((prev) => !prev)}
            style={{
              background: showUnacknowledgedOnly ? 'rgba(245,165,36,0.12)' : 'transparent',
              border: showUnacknowledgedOnly ? '1px solid rgba(245,165,36,0.25)' : '1px solid rgba(255,255,255,0.06)',
              borderRadius: 6,
              padding: '4px 10px',
              fontSize: '0.72rem',
              fontWeight: 600,
              color: showUnacknowledgedOnly ? '#f5a524' : 'rgba(255,255,255,0.4)',
              cursor: 'pointer',
              transition: 'all 0.15s',
            }}
          >
            {showUnacknowledgedOnly ? 'Showing unread' : 'Unread only'}
          </button>
        </div>

        {filteredNotifications.length === 0 ? (
          <div style={{
            background: 'rgba(255,255,255,0.02)',
            border: '1px solid rgba(255,255,255,0.06)',
            borderRadius: 12,
            padding: '32px',
            textAlign: 'center',
            color: 'rgba(255,255,255,0.25)',
            fontSize: '0.82rem',
          }}>
            {showUnacknowledgedOnly ? 'No unread notifications.' : 'No notifications yet.'}
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {filteredNotifications.map((notif) => (
              <NotificationRow key={notif.id} notification={notif} onAcknowledge={handleAcknowledge} />
            ))}
          </div>
        )}
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

export default AlertsView;
