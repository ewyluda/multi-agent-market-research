/**
 * Custom hook for triggering and managing analysis
 */

import { useCallback, useRef } from 'react';
import { useAnalysisContext } from '../context/AnalysisContext';
import { getLatestAnalysis } from '../utils/api';
import { useSSE } from './useSSE';
import { normalizeAnalysis } from '../utils/normalizeAnalysis';

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

  const { startStream, cancelStream } = useSSE();
  const activeAnalysisRef = useRef(null);

  // Trigger new analysis via SSE stream
  const runAnalysis = useCallback((ticker) => {
    cancelStream();

    setCurrentTicker(ticker);
    setLoading(true);
    setError(null);
    // Don't call resetAnalysis() — keep old analysis visible during loading
    // so the page doesn't snap to the welcome screen if SSE drops
    setProgress(0);
    setStage('starting');

    activeAnalysisRef.current = ticker;

    return new Promise((resolve, reject) => {
      startStream(ticker, {
        onProgress: (update) => {
          if (activeAnalysisRef.current !== ticker) return;

          if (update.stage) {
            setStage(update.stage);
          }
          if (update.progress !== undefined) {
            setProgress(update.progress);
          }
        },

        onResult: (result) => {
          if (activeAnalysisRef.current !== ticker) return;

          if (result.success) {
            setAnalysis(normalizeAnalysis(result));
            setProgress(100);
            setStage('complete');
          } else {
            setError(result.error || 'Analysis failed');
            setStage('error');
          }
          setLoading(false);
          resolve(result);
        },

        onError: (errorMessage) => {
          if (activeAnalysisRef.current !== ticker) return;

          console.error('Analysis error:', errorMessage);
          setError(errorMessage);
          setStage('error');
          setLoading(false);
          reject(new Error(errorMessage));
        },

        onClose: () => {
          if (activeAnalysisRef.current === ticker) {
            setLoading(false);
          }
        },
      });
    });
  }, [
    cancelStream,
    startStream,
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

      const result = normalizeAnalysis(await getLatestAnalysis(ticker));
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
