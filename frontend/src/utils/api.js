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
export const getDetailedHistory = async (
  ticker,
  {
    limit = 20,
    offset = 0,
    start_date,
    end_date,
    recommendation,
    min_ev_score,
    max_ev_score,
    min_confidence_calibrated,
    max_confidence_calibrated,
    min_data_quality_score,
    regime_label,
  } = {},
) => {
  const params = { limit, offset };
  if (start_date) params.start_date = start_date;
  if (end_date) params.end_date = end_date;
  if (recommendation) params.recommendation = recommendation;
  if (min_ev_score != null) params.min_ev_score = min_ev_score;
  if (max_ev_score != null) params.max_ev_score = max_ev_score;
  if (min_confidence_calibrated != null) params.min_confidence_calibrated = min_confidence_calibrated;
  if (max_confidence_calibrated != null) params.max_confidence_calibrated = max_confidence_calibrated;
  if (min_data_quality_score != null) params.min_data_quality_score = min_data_quality_score;
  if (regime_label) params.regime_label = regime_label;
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

// ─── Portfolio API ────────────────────────────────────────────────────

export const getPortfolio = async () => {
  const response = await api.get('/api/portfolio');
  return response.data;
};

export const updatePortfolioProfile = async (updates) => {
  const response = await api.put('/api/portfolio/profile', updates);
  return response.data;
};

export const createPortfolioHolding = async (holding) => {
  const response = await api.post('/api/portfolio/holdings', holding);
  return response.data;
};

export const updatePortfolioHolding = async (holdingId, updates) => {
  const response = await api.put(`/api/portfolio/holdings/${holdingId}`, updates);
  return response.data;
};

export const deletePortfolioHolding = async (holdingId) => {
  const response = await api.delete(`/api/portfolio/holdings/${holdingId}`);
  return response.data;
};

export const getPortfolioRiskSummary = async () => {
  const response = await api.get('/api/portfolio/risk-summary');
  return response.data;
};

// ─── Macro / Calibration API ──────────────────────────────────────────

export const getMacroEvents = async ({ from, to } = {}) => {
  const params = {};
  if (from) params.from = from;
  if (to) params.to = to;
  const response = await api.get('/api/macro-events', { params });
  return response.data;
};

export const getCalibrationSummary = async (windowDays = 180) => {
  const response = await api.get('/api/calibration/summary', {
    params: { window_days: windowDays },
  });
  return response.data;
};

export const getCalibrationReliability = async (horizonDays = 7) => {
  const response = await api.get('/api/calibration/reliability', {
    params: { horizon_days: horizonDays },
  });
  return response.data;
};

export const getTickerCalibration = async (ticker, limit = 100) => {
  const response = await api.get(`/api/calibration/ticker/${ticker}`, {
    params: { limit },
  });
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

export const getWatchlistOpportunities = async (
  watchlistId,
  { limit = 20, min_quality = null, min_ev = null } = {},
) => {
  const params = { limit };
  if (min_quality != null) params.min_quality = min_quality;
  if (min_ev != null) params.min_ev = min_ev;
  const response = await api.get(`/api/watchlists/${watchlistId}/opportunities`, { params });
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

export { API_BASE_URL };
export default api;
