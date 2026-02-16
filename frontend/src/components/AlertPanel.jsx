/**
 * AlertPanel - Manage alert rules and view triggered notifications
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
import {
  ArrowLeftIcon,
  LoadingSpinner,
  BellIcon,
  TrashIcon,
  CheckCircleIcon,
  XCircleIcon,
} from './Icons';

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
  if (threshold === null || threshold === undefined) return '';
  if (ruleType.startsWith('confidence_') || ruleType === 'calibration_drop') return `${(threshold * 100).toFixed(0)}%`;
  return threshold.toString();
};

const formatRelativeTime = (isoString) => {
  if (!isoString) return '—';
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now - date;
  const diffMin = Math.floor(diffMs / 1000 / 60);
  const diffHr = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHr / 24);

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

/* ──────── Rule Card ──────── */
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
    <div className="glass-card-elevated rounded-xl p-4 transition-all">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <span
            className={`inline-block w-2 h-2 rounded-full ${
              rule.enabled ? 'bg-success-400 shadow-[0_0_6px_rgba(23,201,100,0.4)]' : 'bg-zinc-600'
            }`}
          />
          <div>
            <div className="flex items-center space-x-2">
              <span className="font-mono text-sm font-semibold">{rule.ticker}</span>
              <span className="text-[11px] text-gray-500 bg-dark-inset px-2 py-0.5 rounded border border-dark-border">
                {formatRuleType(rule.rule_type)}
              </span>
              {rule.threshold !== null && rule.threshold !== undefined && (
                <span className="text-[11px] font-mono text-accent-blue bg-accent-blue/10 px-1.5 py-0.5 rounded border border-accent-blue/20">
                  {formatThreshold(rule.rule_type, rule.threshold)}
                </span>
              )}
            </div>
            <div className="text-[11px] text-gray-500 mt-1">
              Created {formatRelativeTime(rule.created_at)}
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          <ToggleSwitch enabled={rule.enabled} onChange={handleToggle} disabled={toggling} />
          <button
            onClick={handleDelete}
            disabled={deleting}
            className="p-2 rounded-lg text-gray-600 hover:text-danger-400 hover:bg-danger/10 transition-all disabled:opacity-40"
            title="Delete rule"
          >
            <TrashIcon className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
};

/* ──────── Notification Row ──────── */
const NotificationRow = ({ notification, onAcknowledge }) => {
  const [acknowledging, setAcknowledging] = useState(false);
  const changeItems = notification.change_summary?.material_changes || [];
  const triggerContext = notification.trigger_context || {};

  const handleAck = async () => {
    setAcknowledging(true);
    await onAcknowledge(notification.id);
    setAcknowledging(false);
  };

  return (
    <div
      className={`flex items-center justify-between px-4 py-3.5 rounded-lg transition-all ${
        notification.acknowledged ? 'opacity-50' : 'glass-card-elevated'
      }`}
    >
      <div className="flex items-center space-x-3 flex-1 min-w-0">
        <BellIcon
          className={`w-4 h-4 flex-shrink-0 ${
            notification.acknowledged ? 'text-gray-600' : 'text-warning-400'
          }`}
        />
        <div className="min-w-0">
          <div className="flex items-center space-x-2">
            <span className="font-mono text-xs font-semibold">{notification.ticker}</span>
            <span className="text-[11px] text-gray-400 truncate">{notification.message}</span>
          </div>

          {triggerContext.rule_type && (
            <div className="mt-1 text-[10px] text-gray-500">
              Rule: <span className="text-gray-400">{formatRuleType(triggerContext.rule_type)}</span>
              {triggerContext.threshold !== null && triggerContext.threshold !== undefined && (
                <span> - Threshold: <span className="text-gray-400">{formatThreshold(triggerContext.rule_type, triggerContext.threshold)}</span></span>
              )}
            </div>
          )}

          <div className="flex items-center space-x-3 mt-0.5">
            {notification.previous_value && (
              <span className="text-[10px] text-gray-500">
                From: <span className="text-gray-400">{notification.previous_value}</span>
              </span>
            )}
            {notification.current_value && (
              <span className="text-[10px] text-gray-500">
                To: <span className="text-gray-400">{notification.current_value}</span>
              </span>
            )}
            <span className="text-[10px] text-gray-600">{formatRelativeTime(notification.created_at)}</span>
          </div>

          {notification.suggested_action && (
            <div className="mt-2 p-2 rounded-md border border-accent-blue/20 bg-accent-blue/10">
              <div className="text-[10px] uppercase tracking-wider text-accent-blue mb-1">Playbook Action</div>
              <div className="text-[11px] text-gray-200 leading-relaxed">{notification.suggested_action}</div>
            </div>
          )}

          {changeItems.length > 0 && (
            <div className="mt-1.5 space-y-1">
              {changeItems.slice(0, 2).map((change, idx) => (
                <div key={`${change.type}-${idx}`} className="text-[10px] text-gray-500">
                  - {change.label}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
      {!notification.acknowledged && (
        <button
          onClick={handleAck}
          disabled={acknowledging}
          className="flex items-center space-x-1.5 px-2.5 py-1.5 text-[11px] font-medium text-success-400 bg-success/10 border border-success/20 rounded-md hover:bg-success/20 transition-all disabled:opacity-40 ml-2"
        >
          {acknowledging ? (
            <LoadingSpinner size={10} />
          ) : (
            <CheckCircleIcon className="w-3 h-3" />
          )}
          <span>Ack</span>
        </button>
      )}
    </div>
  );
};

/* ──────── Main AlertPanel component ──────── */
const AlertPanel = ({ onBack }) => {
  const [rules, setRules] = useState([]);
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Form state
  const [tickerInput, setTickerInput] = useState('');
  const [ruleType, setRuleType] = useState('recommendation_change');
  const [threshold, setThreshold] = useState('');
  const [creating, setCreating] = useState(false);

  // Notification filter
  const [showUnacknowledgedOnly, setShowUnacknowledgedOnly] = useState(false);

  const selectedRuleOption = RULE_TYPE_OPTIONS.find((o) => o.value === ruleType);
  const needsThreshold = selectedRuleOption?.needsThreshold ?? false;

  // Load data
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

  // Create rule
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

  // Toggle enable/disable
  const handleToggle = async (ruleId, enabled) => {
    setError(null);
    try {
      await updateAlertRule(ruleId, { enabled });
      setRules((prev) =>
        prev.map((r) => (r.id === ruleId ? { ...r, enabled } : r))
      );
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to update rule');
    }
  };

  // Delete rule
  const handleDelete = async (ruleId) => {
    setError(null);
    try {
      await deleteAlertRule(ruleId);
      setRules((prev) => prev.filter((r) => r.id !== ruleId));
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to delete rule');
    }
  };

  // Acknowledge notification
  const handleAcknowledge = async (notificationId) => {
    setError(null);
    try {
      await acknowledgeAlert(notificationId);
      setNotifications((prev) =>
        prev.map((n) => (n.id === notificationId ? { ...n, acknowledged: true } : n))
      );
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to acknowledge alert');
    }
  };

  const filteredNotifications = showUnacknowledgedOnly
    ? notifications.filter((n) => !n.acknowledged)
    : notifications;

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
            <BellIcon className="w-5 h-5 text-warning-400" />
            <h2 className="text-lg font-bold tracking-tight">Alerts</h2>
          </div>
        </div>
        <span className="text-xs text-gray-500">
          {rules.filter((r) => r.enabled).length} active rules / {notifications.filter((n) => !n.acknowledged).length} unread
        </span>
      </div>

      {/* Create rule form */}
      <div className="glass-card-elevated rounded-xl p-5 mb-6">
        <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
          New Alert Rule
        </h3>
        <form onSubmit={handleCreate} className="flex items-end space-x-4">
          <div className="w-32">
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
            <label className="text-xs font-medium text-gray-500 mb-1 block">Rule Type</label>
            <select
              value={ruleType}
              onChange={(e) => setRuleType(e.target.value)}
              className="w-full px-3 py-2 bg-dark-inset border border-dark-border rounded-lg text-sm focus:outline-none focus:ring-1 focus:ring-primary/30 focus:border-primary/40 transition-all appearance-none cursor-pointer"
              disabled={creating}
            >
              {RULE_TYPE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
          {needsThreshold && (
            <div className="w-32">
              <label className="text-xs font-medium text-gray-500 mb-1 block">Threshold</label>
              <input
                type="number"
                step="any"
                value={threshold}
                onChange={(e) => setThreshold(e.target.value)}
                placeholder={
                  ruleType.startsWith('confidence_') || ruleType === 'calibration_drop'
                    ? '0.0 - 1.0'
                    : ruleType.includes('quality')
                      ? '0 - 100'
                      : '-100 to 100'
                }
                className="w-full px-3 py-2 bg-dark-inset border border-dark-border rounded-lg text-sm focus:outline-none focus:ring-1 focus:ring-primary/30 focus:border-primary/40 transition-all"
                disabled={creating}
              />
            </div>
          )}
          <button
            type="submit"
            disabled={creating || !tickerInput.trim() || (needsThreshold && threshold === '')}
            className="flex items-center space-x-1.5 px-5 py-2 bg-gradient-to-r from-primary-600 to-primary hover:from-primary hover:to-primary-400 disabled:from-zinc-700 disabled:to-zinc-700 disabled:cursor-not-allowed rounded-lg text-sm font-medium transition-all"
          >
            {creating ? (
              <><LoadingSpinner size={14} /><span>Creating...</span></>
            ) : (
              <><BellIcon className="w-3.5 h-3.5" /><span>Create</span></>
            )}
          </button>
        </form>
      </div>

      {/* Alert Rules */}
      <div className="mb-8">
        <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
          Alert Rules
        </h3>
        {loading && rules.length === 0 ? (
          <div className="glass-card-elevated rounded-xl p-12 text-center">
            <LoadingSpinner size={20} className="text-gray-500 mx-auto" />
          </div>
        ) : rules.length === 0 ? (
          <div className="glass-card-elevated rounded-xl p-12 text-center">
            <BellIcon className="w-10 h-10 text-gray-600 mx-auto mb-3" />
            <p className="text-sm text-gray-500">No alert rules yet.</p>
            <p className="text-xs text-gray-600 mt-1">Create one above to get started.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {rules.map((rule) => (
              <RuleCard
                key={rule.id}
                rule={rule}
                onToggle={handleToggle}
                onDelete={handleDelete}
              />
            ))}
          </div>
        )}
      </div>

      {/* Notifications */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
            Notifications
          </h3>
          <button
            onClick={() => setShowUnacknowledgedOnly((prev) => !prev)}
            className={`text-[11px] font-medium px-3 py-1.5 rounded-lg border transition-all ${
              showUnacknowledgedOnly
                ? 'bg-warning/15 text-warning-400 border-warning/25'
                : 'text-gray-500 border-white/5 hover:text-gray-300'
            }`}
          >
            {showUnacknowledgedOnly ? 'Showing unread' : 'Show unread only'}
          </button>
        </div>
        {filteredNotifications.length === 0 ? (
          <div className="glass-card-elevated rounded-xl p-8 text-center">
            <CheckCircleIcon className="w-8 h-8 text-gray-600 mx-auto mb-2" />
            <p className="text-sm text-gray-500">
              {showUnacknowledgedOnly ? 'No unread notifications.' : 'No notifications yet.'}
            </p>
            <p className="text-xs text-gray-600 mt-1">
              Alerts will appear here when triggered by an analysis.
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {filteredNotifications.map((notif) => (
              <NotificationRow
                key={notif.id}
                notification={notif}
                onAcknowledge={handleAcknowledge}
              />
            ))}
          </div>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="mt-4 p-3 bg-danger/10 border border-danger/30 rounded-lg text-danger-400 text-sm animate-fade-in">
          {error}
        </div>
      )}
    </div>
  );
};

export default AlertPanel;
