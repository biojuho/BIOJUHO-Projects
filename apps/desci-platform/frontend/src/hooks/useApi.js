import { useQuery } from '@tanstack/react-query';
import { queryClient } from '../lib/queryClient';
import client from '../services/api';

export function useFetch(url, options = {}) {
  const { params = {}, enabled = true, cacheTime = 60_000 } = options;
  const active = Boolean(enabled && url);
  const queryKey = ['api', url, params];

  const query = useQuery({
    queryKey,
    enabled: active,
    staleTime: cacheTime,
    gcTime: cacheTime,
    retry: false,
    queryFn: async ({ signal }) => {
      const response = await client.get(url, { params, signal });
      return response.data;
    },
  });

  async function refetch() {
    if (!active) return false;
    await queryClient.cancelQueries({ queryKey, exact: true }, { silent: true });
    const result = await query.refetch({ cancelRefetch: true });
    return result.error == null;
  }

  return {
    data: query.data ?? null,
    error: query.error ?? null,
    loading: query.isLoading || (query.isFetching && query.data == null),
    refetch,
  };
}

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

export function usePapers() {
  const result = useFetch('/papers/me');

  return {
    papers: Array.isArray(result.data) ? result.data : [],
    loading: result.loading,
    error: result.error,
    refetch: result.refetch,
  };
}

export function clearApiCache() {
  queryClient.clear();
}
