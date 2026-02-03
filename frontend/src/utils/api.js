/**
 * API utility functions for communicating with the backend
 */

import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

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
 * Health check
 */
export const healthCheck = async () => {
  const response = await api.get('/health');
  return response.data;
};

export default api;
