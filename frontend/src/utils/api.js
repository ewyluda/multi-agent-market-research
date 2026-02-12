/**
 * API utility functions for communicating with the backend
 */

import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

/**
 * Trigger analysis for a ticker
 */
export const analyzeTickerAPI = async (ticker) => {
  const response = await api.post(`/api/analyze/${ticker}`);
  return response.data;
};

/**
 * Get latest analysis for a ticker
 */
export const getLatestAnalysis = async (ticker) => {
  const response = await api.get(`/api/analysis/${ticker}/latest`);
  return response.data;
};

/**
 * Get analysis history for a ticker
 */
export const getAnalysisHistory = async (ticker, limit = 10) => {
  const response = await api.get(`/api/analysis/${ticker}/history`, {
    params: { limit },
  });
  return response.data;
};

/**
 * Get detailed/paginated analysis history for a ticker
 */
export const getDetailedHistory = async (ticker, { limit = 20, offset = 0, start_date, end_date, recommendation } = {}) => {
  const params = { limit, offset };
  if (start_date) params.start_date = start_date;
  if (end_date) params.end_date = end_date;
  if (recommendation) params.recommendation = recommendation;
  const response = await api.get(`/api/analysis/${ticker}/history/detailed`, { params });
  return response.data;
};

/**
 * Get all tickers that have been analyzed
 */
export const getAnalyzedTickers = async () => {
  const response = await api.get('/api/analysis/tickers');
  return response.data;
};

/**
 * Delete a specific analysis record
 */
export const deleteAnalysis = async (analysisId) => {
  const response = await api.delete(`/api/analysis/${analysisId}`);
  return response.data;
};

/**
 * Get full analysis with agent results
 */
export const getFullAnalysis = async (ticker, analysisId) => {
  const response = await api.get(`/api/analysis/${ticker}/latest`);
  return response.data;
};

// ─── Export API ──────────────────────────────────────────────────────

/**
 * Export analysis as PDF (triggers browser download)
 */
export const exportAnalysisPDF = async (ticker, analysisId) => {
  const params = analysisId ? { analysis_id: analysisId } : {};
  const response = await api.get(`/api/analysis/${ticker}/export/pdf`, {
    params,
    responseType: 'blob',
  });

  // Trigger browser download
  const url = window.URL.createObjectURL(new Blob([response.data], { type: 'application/pdf' }));
  const link = document.createElement('a');
  link.href = url;
  const filename = response.headers['content-disposition']?.match(/filename="(.+)"/)?.[1] || `${ticker}_analysis.pdf`;
  link.setAttribute('download', filename);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
};

// ─── Schedule API ────────────────────────────────────────────────────

/**
 * Get all schedules
 */
export const getSchedules = async () => {
  const response = await api.get('/api/schedules');
  return response.data;
};

/**
 * Create a new schedule
 */
export const createSchedule = async (ticker, intervalMinutes, agents = null) => {
  const body = { ticker, interval_minutes: intervalMinutes };
  if (agents) body.agents = agents;
  const response = await api.post('/api/schedules', body);
  return response.data;
};

/**
 * Get a schedule with its recent runs
 */
export const getScheduleWithRuns = async (scheduleId) => {
  const response = await api.get(`/api/schedules/${scheduleId}`);
  return response.data;
};

/**
 * Update a schedule (enable/disable, change interval, etc.)
 */
export const updateSchedule = async (scheduleId, updates) => {
  const response = await api.put(`/api/schedules/${scheduleId}`, updates);
  return response.data;
};

/**
 * Delete a schedule
 */
export const deleteSchedule = async (scheduleId) => {
  const response = await api.delete(`/api/schedules/${scheduleId}`);
  return response.data;
};

// ─── Watchlist API ───────────────────────────────────────────────────

/**
 * Get all watchlists
 */
export const getWatchlists = async () => {
  const response = await api.get('/api/watchlists');
  return response.data;
};

/**
 * Get a single watchlist with tickers and latest analyses
 */
export const getWatchlist = async (watchlistId) => {
  const response = await api.get(`/api/watchlists/${watchlistId}`);
  return response.data;
};

/**
 * Create a new watchlist
 */
export const createWatchlist = async (name) => {
  const response = await api.post('/api/watchlists', { name });
  return response.data;
};

/**
 * Rename a watchlist
 */
export const renameWatchlist = async (watchlistId, name) => {
  const response = await api.put(`/api/watchlists/${watchlistId}`, { name });
  return response.data;
};

/**
 * Delete a watchlist
 */
export const deleteWatchlist = async (watchlistId) => {
  const response = await api.delete(`/api/watchlists/${watchlistId}`);
  return response.data;
};

/**
 * Add a ticker to a watchlist
 */
export const addTickerToWatchlist = async (watchlistId, ticker) => {
  const response = await api.post(`/api/watchlists/${watchlistId}/tickers`, { ticker });
  return response.data;
};

/**
 * Remove a ticker from a watchlist
 */
export const removeTickerFromWatchlist = async (watchlistId, ticker) => {
  const response = await api.delete(`/api/watchlists/${watchlistId}/tickers/${ticker}`);
  return response.data;
};

// ─── Alert API ──────────────────────────────────────────────────────

/**
 * Get all alert rules (optionally filtered by ticker)
 */
export const getAlertRules = async (ticker = null) => {
  const params = ticker ? { ticker } : {};
  const response = await api.get('/api/alerts', { params });
  return response.data;
};

/**
 * Create a new alert rule
 */
export const createAlertRule = async (ticker, ruleType, threshold = null) => {
  const body = { ticker, rule_type: ruleType };
  if (threshold !== null) body.threshold = threshold;
  const response = await api.post('/api/alerts', body);
  return response.data;
};

/**
 * Get a specific alert rule
 */
export const getAlertRule = async (ruleId) => {
  const response = await api.get(`/api/alerts/${ruleId}`);
  return response.data;
};

/**
 * Update an alert rule
 */
export const updateAlertRule = async (ruleId, updates) => {
  const response = await api.put(`/api/alerts/${ruleId}`, updates);
  return response.data;
};

/**
 * Delete an alert rule
 */
export const deleteAlertRule = async (ruleId) => {
  const response = await api.delete(`/api/alerts/${ruleId}`);
  return response.data;
};

/**
 * Get alert notifications
 */
export const getAlertNotifications = async (unacknowledged = false, limit = 50) => {
  const params = { limit };
  if (unacknowledged) params.unacknowledged = true;
  const response = await api.get('/api/alerts/notifications', { params });
  return response.data;
};

/**
 * Get unacknowledged notification count (for badge)
 */
export const getUnacknowledgedCount = async () => {
  const response = await api.get('/api/alerts/notifications/count');
  return response.data;
};

/**
 * Acknowledge (mark as read) a notification
 */
export const acknowledgeAlert = async (notificationId) => {
  const response = await api.post(`/api/alerts/notifications/${notificationId}/acknowledge`);
  return response.data;
};

/**
 * Health check
 */
export const healthCheck = async () => {
  const response = await api.get('/health');
  return response.data;
};

export { API_BASE_URL };
export default api;
