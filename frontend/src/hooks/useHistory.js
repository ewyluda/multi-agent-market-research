/**
 * Custom hook for analysis history state management
 */

import { useState, useCallback } from 'react';
import { getAnalyzedTickers, getDetailedHistory, deleteAnalysis } from '../utils/api';

export const useHistory = () => {
  const [tickers, setTickers] = useState([]);
  const [tickersLoading, setTickersLoading] = useState(false);
  const [selectedTicker, setSelectedTicker] = useState(null);
  const [history, setHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [totalCount, setTotalCount] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState({
    recommendation: null,
    start_date: null,
    end_date: null,
  });
  const [page, setPage] = useState(0);
  const pageSize = 15;

  // Fetch all analyzed tickers
  const fetchTickers = useCallback(async () => {
    setTickersLoading(true);
    setError(null);
    try {
      const data = await getAnalyzedTickers();
      setTickers(data.tickers || []);
      return data.tickers || [];
    } catch (err) {
      console.error('Failed to fetch tickers:', err);
      setError(err.message || 'Failed to fetch analyzed tickers');
      return [];
    } finally {
      setTickersLoading(false);
    }
  }, []);

  // Fetch history for a specific ticker
  const fetchHistory = useCallback(async (ticker, pageNum = 0, currentFilters = filters) => {
    if (!ticker) return;
    setHistoryLoading(true);
    setError(null);
    try {
      const data = await getDetailedHistory(ticker, {
        limit: pageSize,
        offset: pageNum * pageSize,
        recommendation: currentFilters.recommendation,
        start_date: currentFilters.start_date,
        end_date: currentFilters.end_date,
      });
      setHistory(data.items || []);
      setTotalCount(data.total_count || 0);
      setHasMore(data.has_more || false);
      setPage(pageNum);
    } catch (err) {
      console.error('Failed to fetch history:', err);
      setError(err.message || 'Failed to fetch analysis history');
      setHistory([]);
      setTotalCount(0);
      setHasMore(false);
    } finally {
      setHistoryLoading(false);
    }
  }, [filters]);

  // Select a ticker and load its history
  const selectTicker = useCallback(async (ticker) => {
    setSelectedTicker(ticker);
    setPage(0);
    setFilters({ recommendation: null, start_date: null, end_date: null });
    await fetchHistory(ticker, 0, { recommendation: null, start_date: null, end_date: null });
  }, [fetchHistory]);

  // Apply filters and refresh
  const applyFilters = useCallback(async (newFilters) => {
    const merged = { ...filters, ...newFilters };
    setFilters(merged);
    setPage(0);
    if (selectedTicker) {
      await fetchHistory(selectedTicker, 0, merged);
    }
  }, [filters, selectedTicker, fetchHistory]);

  // Navigate pages
  const goToPage = useCallback(async (pageNum) => {
    if (selectedTicker) {
      await fetchHistory(selectedTicker, pageNum, filters);
    }
  }, [selectedTicker, filters, fetchHistory]);

  // Delete an analysis and refresh
  const removeAnalysis = useCallback(async (analysisId) => {
    try {
      await deleteAnalysis(analysisId);
      // Refresh current view
      if (selectedTicker) {
        await fetchHistory(selectedTicker, page, filters);
        // Also refresh tickers list (count may have changed)
        await fetchTickers();
      }
      return true;
    } catch (err) {
      console.error('Failed to delete analysis:', err);
      setError(err.message || 'Failed to delete analysis');
      return false;
    }
  }, [selectedTicker, page, filters, fetchHistory, fetchTickers]);

  return {
    // Tickers
    tickers,
    tickersLoading,
    fetchTickers,
    // Selected ticker
    selectedTicker,
    selectTicker,
    // History
    history,
    historyLoading,
    totalCount,
    hasMore,
    // Pagination
    page,
    pageSize,
    goToPage,
    // Filters
    filters,
    applyFilters,
    // Actions
    removeAnalysis,
    // Error
    error,
  };
};
