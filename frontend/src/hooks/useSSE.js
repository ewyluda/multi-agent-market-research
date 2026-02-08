/**
 * SSE hook for streaming analysis progress and results
 */

import { useRef, useCallback } from 'react';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

/**
 * Hook to stream analysis via Server-Sent Events.
 *
 * Returns a `startStream` function that opens an SSE connection for a given
 * ticker and calls the provided callbacks as events arrive.
 */
export const useSSE = () => {
  const eventSourceRef = useRef(null);

  const cancelStream = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
  }, []);

  /**
   * Open an SSE connection for analysis.
   *
   * @param {string} ticker - Stock ticker symbol
   * @param {Object} callbacks
   * @param {Function} callbacks.onProgress - Called with progress update object
   * @param {Function} callbacks.onResult  - Called with final analysis result
   * @param {Function} callbacks.onError   - Called with error string
   * @param {Function} callbacks.onClose   - Called when stream ends
   * @param {string} [agents] - Optional comma-separated agent list
   */
  const startStream = useCallback((ticker, { onProgress, onResult, onError, onClose }, agents) => {
    cancelStream();

    let url = `${API_BASE_URL}/api/analyze/${ticker}/stream`;
    if (agents) {
      url += `?agents=${encodeURIComponent(agents)}`;
    }

    const eventSource = new EventSource(url);
    eventSourceRef.current = eventSource;

    eventSource.addEventListener('progress', (event) => {
      try {
        const data = JSON.parse(event.data);
        if (onProgress) onProgress(data);
      } catch (err) {
        console.error('Failed to parse progress event:', err);
      }
    });

    eventSource.addEventListener('result', (event) => {
      try {
        const data = JSON.parse(event.data);
        if (onResult) onResult(data);
      } catch (err) {
        console.error('Failed to parse result event:', err);
      }
      eventSource.close();
      eventSourceRef.current = null;
      if (onClose) onClose();
    });

    eventSource.addEventListener('error', (event) => {
      // EventSource fires 'error' for both our custom error events and connection errors
      if (event.data) {
        // Our custom SSE error event with data
        try {
          const data = JSON.parse(event.data);
          if (onError) onError(data.error || 'Analysis failed');
        } catch (err) {
          if (onError) onError('Analysis failed');
        }
      } else if (eventSource.readyState === EventSource.CLOSED) {
        // Server closed the connection (normal after result)
        if (onClose) onClose();
        eventSourceRef.current = null;
        return;
      } else {
        // Connection error (server down, network issue)
        if (onError) onError('Connection to server lost');
      }

      eventSource.close();
      eventSourceRef.current = null;
      if (onClose) onClose();
    });
  }, [cancelStream]);

  return { startStream, cancelStream };
};
