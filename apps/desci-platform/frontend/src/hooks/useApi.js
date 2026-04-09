/**
 * Custom API Hooks with SWR-like caching pattern.
 * Provides fetch + state + refetch + AbortController support.
 *
 * These hooks are a lightweight bridge until TanStack Query is adopted.
 */
import { useState, useEffect, useCallback, useRef } from 'react';
import client from '../services/api';

/**
 * Generic fetcher hook with caching, abort support, and refetch.
 *
 * @param {string} url - API endpoint path
 * @param {object} options
 * @param {object} options.params - Query parameters
 * @param {boolean} options.enabled - Whether to fetch (default: true)
 * @param {number} options.cacheTime - Cache TTL in ms (default: 60000)
 */

// Simple in-memory cache shared across hook instances
const cache = new Map();

function getCachedSnapshot(cacheKey, cacheTime) {
  const cached = cache.get(cacheKey);
  if (cached && Date.now() - cached.timestamp < cacheTime) {
    return cached.data;
  }
  return null;
}

export function useFetch(url, options = {}) {
  const { params = {}, enabled = true, cacheTime = 60_000 } = options;
  const paramsKey = JSON.stringify(params ?? {});
  const cacheKey = `${url}::${paramsKey}`;

  const [data, setData] = useState(() => getCachedSnapshot(cacheKey, cacheTime));
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(() => enabled && !!url && getCachedSnapshot(cacheKey, cacheTime) == null);
  const abortControllerRef = useRef(null);
  const requestIdRef = useRef(0);

  const fetchData = useCallback(async () => {
    if (!enabled || !url) {
      setData(null);
      setError(null);
      setLoading(false);
      return false;
    }

    const requestId = requestIdRef.current + 1;
    requestIdRef.current = requestId;

    // Abort previous in-flight request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    const controller = new AbortController();
    abortControllerRef.current = controller;

    setLoading(true);
    setError(null);

    try {
      const res = await client.get(url, {
        params,
        signal: controller.signal,
      });

      if (requestId !== requestIdRef.current || controller.signal.aborted) {
        return false;
      }

      const responseData = res.data;
      setData(responseData);

      // Update cache
      cache.set(cacheKey, { data: responseData, timestamp: Date.now() });
      return true;
    } catch (err) {
      // Don't set error state for aborted requests
      if (err.name === 'AbortError' || err.code === 'ERR_CANCELED' || controller.signal.aborted) {
        return false;
      }

      if (requestId === requestIdRef.current) {
        setError(err);
      }
      return false;
    } finally {
      if (requestId === requestIdRef.current && !controller.signal.aborted) {
        setLoading(false);
      }
    }
  }, [cacheKey, enabled, paramsKey, url]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const cached = getCachedSnapshot(cacheKey, cacheTime);

    if (!enabled || !url) {
      setData(null);
      setError(null);
      setLoading(false);
      return () => {
        requestIdRef.current += 1;
        if (abortControllerRef.current) {
          abortControllerRef.current.abort();
        }
      };
    }

    setData(cached);
    setError(null);
    setLoading(cached == null);
    fetchData();

    return () => {
      requestIdRef.current += 1;
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [cacheKey, cacheTime, enabled, fetchData, url]);

  const refetch = useCallback(() => {
    // Invalidate cache for this key
    cache.delete(cacheKey);
    return fetchData();
  }, [cacheKey, fetchData]);

  return { data, error, loading, refetch };
}

// --- Domain-Specific Hooks ---

/**
 * Fetch government grant notices.
 * @param {object} options - { source, limit }
 */
export function useNotices(options = {}) {
  const { source, limit = 30 } = options;
  const params = { limit };
  if (source) params.source = source;

  const result = useFetch('/notices', { params });

  return {
    notices: Array.isArray(result.data) ? result.data : [],
    loading: result.loading,
    error: result.error,
    refetch: result.refetch,
  };
}

/**
 * Fetch analysis results for a specific RFP.
 * @param {string|null} rfpId - RFP document ID
 */
export function useAnalysis(rfpId) {
  const result = useFetch(
    rfpId ? `/analysis/${rfpId}` : null,
    { enabled: !!rfpId }
  );

  return {
    analysis: result.data,
    loading: result.loading,
    error: result.error,
    refetch: result.refetch,
  };
}

/**
 * Fetch the current user's uploaded papers.
 */
export function usePapers() {
  const result = useFetch('/papers/me');

  return {
    papers: Array.isArray(result.data) ? result.data : [],
    loading: result.loading,
    error: result.error,
    refetch: result.refetch,
  };
}

/**
 * Utility to clear the entire fetch cache.
 */
export function clearApiCache() {
  cache.clear();
}
