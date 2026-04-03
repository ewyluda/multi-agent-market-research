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
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

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
    className="relative inline-flex items-center flex-shrink-0 rounded-full transition-colors"
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
    <Card>
      <CardContent className="pt-3.5 pb-3.5 flex items-center justify-between">
        <div className="flex items-center gap-3">
          {/* Status dot */}
          <span style={{
            display: 'inline-block',
            width: 8,
            height: 8,
            borderRadius: '50%',
            background: rule.enabled ? 'var(--success)' : 'rgba(255,255,255,0.2)',
            boxShadow: rule.enabled ? '0 0 6px rgba(23,201,100,0.5)' : 'none',
            flexShrink: 0,
          }} />
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="font-data font-bold text-[0.85rem]" style={{ color: 'var(--text-primary)' }}>
                {rule.ticker}
              </span>
              <Badge variant="secondary" className="text-[0.65rem] px-1.5 py-0">
                {formatRuleType(rule.rule_type)}
              </Badge>
              {rule.threshold != null && (
                <Badge variant="default" className="text-[0.65rem] px-1.5 py-0 font-data">
                  {formatThreshold(rule.rule_type, rule.threshold)}
                </Badge>
              )}
            </div>
            <div className="text-[0.7rem]" style={{ color: 'var(--text-muted)' }}>
              Created {formatRelativeTime(rule.created_at)}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          <ToggleSwitch enabled={rule.enabled} onChange={handleToggle} disabled={toggling} />
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
            title="Delete rule"
          >
            ✕
          </button>
        </div>
      </CardContent>
    </Card>
  );
};

/* ──────── Notification severity ──────── */
const getSeverityVariant = (notification) => {
  const ruleType = notification.trigger_context?.rule_type || '';
  if (ruleType.includes('sell') || ruleType === 'recommendation_change') return 'danger';
  if (ruleType.includes('above') || ruleType.includes('buy')) return 'success';
  return 'warning';
};

const getSeverityDotColor = (notification) => {
  const ruleType = notification.trigger_context?.rule_type || '';
  if (ruleType.includes('sell') || ruleType === 'recommendation_change') return 'var(--danger)';
  if (ruleType.includes('above') || ruleType.includes('buy')) return 'var(--success)';
  return 'var(--warning)';
};

const getSeverityBg = (notification) => {
  const ruleType = notification.trigger_context?.rule_type || '';
  if (ruleType.includes('sell') || ruleType === 'recommendation_change') return 'rgba(243,18,96,0.06)';
  if (ruleType.includes('above') || ruleType.includes('buy')) return 'rgba(23,201,100,0.04)';
  return 'rgba(245,165,36,0.04)';
};

/* ──────── Notification row ──────── */
const NotificationRow = ({ notification, onAcknowledge }) => {
  const [acknowledging, setAcknowledging] = useState(false);
  const triggerCtx = notification.trigger_context || {};

  const handleAck = async () => {
    setAcknowledging(true);
    await onAcknowledge(notification.id);
    setAcknowledging(false);
  };

  return (
    <Card
      style={{
        background: notification.acknowledged ? 'transparent' : getSeverityBg(notification),
        opacity: notification.acknowledged ? 0.5 : 1,
        transition: 'all 0.15s',
      }}
    >
      <CardContent className="pt-3 pb-3 flex items-start justify-between gap-3">
        <div className="flex items-start gap-2.5 flex-1 min-w-0">
          {/* Severity dot */}
          <span style={{
            display: 'inline-block',
            width: 7,
            height: 7,
            borderRadius: '50%',
            background: notification.acknowledged ? 'rgba(255,255,255,0.2)' : getSeverityDotColor(notification),
            marginTop: 4,
            flexShrink: 0,
          }} />
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 mb-0.5 flex-wrap">
              <span className="font-data font-bold text-[0.82rem]" style={{ color: 'var(--text-primary)' }}>
                {notification.ticker}
              </span>
              <span className="text-[0.75rem]" style={{ color: 'var(--text-secondary)' }}>
                {notification.message}
              </span>
            </div>

            {triggerCtx.rule_type && (
              <div className="text-[0.7rem] mb-0.5" style={{ color: 'var(--text-muted)' }}>
                Rule: {formatRuleType(triggerCtx.rule_type)}
                {triggerCtx.threshold != null && ` — Threshold: ${formatThreshold(triggerCtx.rule_type, triggerCtx.threshold)}`}
              </div>
            )}

            <div className="flex gap-3 text-[0.7rem] mt-0.5" style={{ color: 'var(--text-muted)' }}>
              {notification.previous_value && (
                <span>From: <span style={{ color: 'var(--text-secondary)' }}>{notification.previous_value}</span></span>
              )}
              {notification.current_value && (
                <span>To: <span style={{ color: 'var(--text-secondary)' }}>{notification.current_value}</span></span>
              )}
              <span>{formatRelativeTime(notification.created_at)}</span>
            </div>

            {notification.suggested_action && (
              <div
                className="mt-2 px-2.5 py-2 rounded-md"
                style={{
                  background: 'rgba(0,111,238,0.08)',
                  border: '1px solid rgba(0,111,238,0.15)',
                }}
              >
                <div className="text-[0.6rem] font-bold uppercase tracking-widest mb-0.5" style={{ color: 'var(--primary)' }}>
                  Suggested Action
                </div>
                <div className="text-[0.75rem] leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                  {notification.suggested_action}
                </div>
              </div>
            )}
          </div>
        </div>

        {!notification.acknowledged && (
          <Button
            variant="secondary"
            size="sm"
            onClick={handleAck}
            disabled={acknowledging}
            className="h-7 px-2.5 text-[0.7rem] shrink-0"
            style={{ color: 'var(--success)', borderColor: 'rgba(23,201,100,0.2)', background: 'rgba(23,201,100,0.1)' }}
          >
            {acknowledging ? '...' : 'Dismiss'}
          </Button>
        )}
      </CardContent>
    </Card>
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

  const sectionLabel = (
    <span className="text-[0.65rem] font-bold uppercase tracking-widest" style={{ color: 'var(--text-muted)' }} />
  );

  return (
    <div className="flex-1 p-6">
      <div className="flex items-center justify-between mb-5">
        <h2 className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>Alerts</h2>
        <span className="text-[0.75rem]" style={{ color: 'var(--text-muted)' }}>
          {rules.filter((r) => r.enabled).length} active rules / {unreadCount} unread
        </span>
      </div>

      {/* Create rule form */}
      <Card className="mb-6">
        <CardHeader className="pb-3">
          <CardTitle className="text-xs uppercase tracking-widest" style={{ color: 'var(--text-muted)' }}>
            New Alert Rule
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          <form onSubmit={handleCreate} className="flex items-end gap-3 flex-wrap">
            <div style={{ flex: '0 0 120px' }}>
              <label className="text-[0.65rem] font-semibold uppercase tracking-wider block mb-1" style={{ color: 'var(--text-muted)' }}>Ticker</label>
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
            <div style={{ flex: 1, minWidth: 180 }}>
              <label className="text-[0.65rem] font-semibold uppercase tracking-wider block mb-1" style={{ color: 'var(--text-muted)' }}>Rule Type</label>
              <select
                value={ruleType}
                onChange={(e) => { setRuleType(e.target.value); setThreshold(''); }}
                disabled={creating}
                style={selectStyle}
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
                <label className="text-[0.65rem] font-semibold uppercase tracking-wider block mb-1" style={{ color: 'var(--text-muted)' }}>Threshold</label>
                <Input
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
                  className="font-data"
                />
              </div>
            )}
            <Button
              type="submit"
              disabled={creating || !tickerInput.trim() || (needsThreshold && threshold === '')}
              className="whitespace-nowrap"
            >
              {creating ? 'Creating...' : 'Create'}
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Active rules */}
      <div className="mb-7">
        <div className="text-[0.65rem] font-bold uppercase tracking-widest mb-3" style={{ color: 'var(--text-muted)' }}>
          Alert Rules
        </div>
        {loading && rules.length === 0 ? (
          <div className="text-center py-8 text-[0.82rem]" style={{ color: 'var(--text-muted)' }}>Loading...</div>
        ) : rules.length === 0 ? (
          <Card>
            <CardContent className="pt-8 pb-8 text-center text-[0.82rem]" style={{ color: 'var(--text-muted)' }}>
              No alert rules yet. Create one above.
            </CardContent>
          </Card>
        ) : (
          <div className="flex flex-col gap-2">
            {rules.map((rule) => (
              <RuleCard key={rule.id} rule={rule} onToggle={handleToggle} onDelete={handleDelete} />
            ))}
          </div>
        )}
      </div>

      {/* Notifications */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <div className="text-[0.65rem] font-bold uppercase tracking-widest" style={{ color: 'var(--text-muted)' }}>
            Notifications
          </div>
          <Button
            variant={showUnacknowledgedOnly ? 'secondary' : 'outline'}
            size="sm"
            onClick={() => setShowUnacknowledgedOnly((prev) => !prev)}
            className="h-6 px-2.5 text-[0.72rem]"
            style={showUnacknowledgedOnly ? { color: 'var(--warning)', borderColor: 'rgba(245,165,36,0.25)' } : {}}
          >
            {showUnacknowledgedOnly ? 'Showing unread' : 'Unread only'}
          </Button>
        </div>

        {filteredNotifications.length === 0 ? (
          <Card>
            <CardContent className="pt-8 pb-8 text-center text-[0.82rem]" style={{ color: 'var(--text-muted)' }}>
              {showUnacknowledgedOnly ? 'No unread notifications.' : 'No notifications yet.'}
            </CardContent>
          </Card>
        ) : (
          <div className="flex flex-col gap-2">
            {filteredNotifications.map((notif) => (
              <NotificationRow key={notif.id} notification={notif} onAcknowledge={handleAcknowledge} />
            ))}
          </div>
        )}
      </div>

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

export default AlertsView;
