import { QueryClient } from "@tanstack/react-query";

function shouldRetry(failureCount, error) {
  const status = error?.status ?? error?.response?.status;
  if (status === 401 || status === 403 || status === 404) return false;
  return failureCount < 1;
}

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,
      gcTime: 5 * 60_000,
      retry: shouldRetry,
      refetchOnWindowFocus: false,
    },
    mutations: {
      retry: false,
    },
  },
});
