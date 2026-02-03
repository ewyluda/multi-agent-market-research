/**
 * Custom hook for triggering and managing analysis
 */

import { useState, useCallback } from 'react';
import { useAnalysisContext } from '../context/AnalysisContext';
import { analyzeTickerAPI, getLatestAnalysis } from '../utils/api';
import { useWebSocket } from './useWebSocket';

export const useAnalysis = () => {
  const {
    currentTicker,
    setCurrentTicker,
    analysis,
    setAnalysis,
    loading,
    setLoading,
    error,
    setError,
    setProgress,
    setStage,
    resetAnalysis,
  } = useAnalysisContext();

  const [wsConnected, setWsConnected] = useState(false);

  // Handle WebSocket updates
  const handleWSUpdate = useCallback((update) => {
    console.log('Progress update:', update);

    if (update.stage) {
      setStage(update.stage);
    }

    if (update.progress !== undefined) {
      setProgress(update.progress);
    }

    // If analysis is complete, it will be fetched by the API call
  }, [setStage, setProgress]);

  // Initialize WebSocket connection
  const { sendMessage } = useWebSocket(currentTicker, handleWSUpdate);

  // Trigger new analysis
  const runAnalysis = useCallback(async (ticker) => {
    try {
      setCurrentTicker(ticker);
      setLoading(true);
      setError(null);
      resetAnalysis();
      setProgress(0);
      setStage('starting');

      console.log(`Starting analysis for ${ticker}...`);

      // Trigger analysis via API
      const result = await analyzeTickerAPI(ticker);

      console.log('Analysis result:', result);

      if (result.success) {
        setAnalysis(result);
        setProgress(100);
        setStage('complete');
      } else {
        throw new Error(result.error || 'Analysis failed');
      }

      return result;
    } catch (err) {
      console.error('Analysis error:', err);
      setError(err.message || 'Failed to run analysis');
      setStage('error');
      throw err;
    } finally {
      setLoading(false);
    }
  }, [
    setCurrentTicker,
    setLoading,
    setError,
    setAnalysis,
    setProgress,
    setStage,
    resetAnalysis,
  ]);

  // Fetch latest analysis without triggering new one
  const fetchLatest = useCallback(async (ticker) => {
    try {
      setLoading(true);
      setError(null);

      const result = await getLatestAnalysis(ticker);
      setAnalysis(result);
      setCurrentTicker(ticker);

      return result;
    } catch (err) {
      console.error('Fetch error:', err);
      setError(err.message || 'Failed to fetch analysis');
      throw err;
    } finally {
      setLoading(false);
    }
  }, [setLoading, setError, setAnalysis, setCurrentTicker]);

  return {
    currentTicker,
    analysis,
    loading,
    error,
    runAnalysis,
    fetchLatest,
    resetAnalysis,
  };
};
