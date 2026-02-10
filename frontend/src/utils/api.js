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

/**
 * Health check
 */
export const healthCheck = async () => {
  const response = await api.get('/health');
  return response.data;
};

export { API_BASE_URL };
export default api;
