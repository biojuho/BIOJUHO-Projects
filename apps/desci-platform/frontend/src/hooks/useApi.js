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

function getCacheKey(url, params) {
  return `${url}::${JSON.stringify(params ?? {})}`;
}

export function useFetch(url, options = {}) {
  const { params = {}, enabled = true, cacheTime = 60_000 } = options;

  const [data, setData] = useState(() => {
    const key = getCacheKey(url, params);
    const cached = cache.get(key);
    if (cached && Date.now() - cached.timestamp < cacheTime) {
      return cached.data;
    }
    return null;
  });
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(!data);
  const abortControllerRef = useRef(null);

  const fetchData = useCallback(async () => {
    if (!enabled || !url) return;

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

      const responseData = res.data;
      setData(responseData);

      // Update cache
      const key = getCacheKey(url, params);
      cache.set(key, { data: responseData, timestamp: Date.now() });
    } catch (err) {
      // Don't set error state for aborted requests
      if (err.name !== 'AbortError' && err.code !== 'ERR_CANCELED') {
        setError(err);
      }
    } finally {
      setLoading(false);
    }
  }, [url, JSON.stringify(params), enabled]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    fetchData();

    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [fetchData]);

  const refetch = useCallback(() => {
    // Invalidate cache for this key
    const key = getCacheKey(url, params);
    cache.delete(key);
    return fetchData();
  }, [fetchData, url, params]);

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
