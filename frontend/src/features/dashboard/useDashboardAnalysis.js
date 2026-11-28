import { useState, useEffect, useRef, useCallback } from 'react';
import { getWorkspaceAnalysis, isValidAnalysisPayload } from './dashboardService.js';

/**
 * Custom React hook to fetch and manage workspace analysis data.
 * Protects against race conditions (stale responses from older workspaces/accounts are discarded).
 *
 * @param {string|null} workspaceId - Current workspace UUID
 * @param {Object} [options]
 * @param {string|null} [options.userId] - Current authenticated user ID (invalidates on account switch)
 * @param {number} [options.financialEpoch=0] - Financial invalidation epoch (invalidates on deletion)
 * @param {boolean} [options.skip=false] - When true, bypasses automatic fetching
 */
export function useDashboardAnalysis(workspaceId, options = {}) {
  const { userId = null, financialEpoch = 0, skip = false } = options;

  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Request generation counter: incremented on every new request or context change
  const requestGenRef = useRef(0);

  const fetchAnalysis = useCallback(async () => {
    if (!workspaceId || skip) {
      setAnalysis(null);
      setLoading(false);
      setError(null);
      return;
    }

    const gen = ++requestGenRef.current;
    const controller = new AbortController();

    setLoading(true);
    setError(null);

    try {
      const data = await getWorkspaceAnalysis(workspaceId, controller.signal);

      // Discard if a newer request or context switch has started
      if (requestGenRef.current !== gen) return;

      if (!isValidAnalysisPayload(data)) {
        throw new Error('Received an unexpected analysis response format from the server.');
      }

      setAnalysis(data);
      setLoading(false);
      setError(null);
    } catch (err) {
      if (requestGenRef.current !== gen) return;

      // Ignore client-side aborts
      if (err.name === 'AbortError') return;

      let errorMsg;
      if (err.status === 404) {
        errorMsg = 'Workspace analysis not found. The workspace may have been removed or belongs to another account.';
      } else if (err.status === 409) {
        errorMsg = err.message || 'Document is not yet ready for analysis (document_not_ready).';
      } else if (err.status === 503) {
        errorMsg = 'Financial analysis database service is temporarily unavailable. Please retry shortly.';
      } else {
        errorMsg = err.message || 'Failed to load workspace analysis.';
      }

      setAnalysis(null);
      setLoading(false);
      setError(errorMsg);
    }
  }, [workspaceId, skip]);

  // Trigger load whenever workspaceId, userId, or financialEpoch changes
  useEffect(() => {
    fetchAnalysis();

    return () => {
      // Invalidate in-flight responses on unmount or re-render
      requestGenRef.current += 1;
    };
  }, [fetchAnalysis, userId, financialEpoch]);

  return {
    analysis,
    loading,
    error,
    reload: fetchAnalysis
  };
}

export default useDashboardAnalysis;
