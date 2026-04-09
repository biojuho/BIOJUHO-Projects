import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import client from '../services/api';
import { clearApiCache, useFetch } from './useApi';

vi.mock('../services/api', () => ({
  default: {
    get: vi.fn(),
  },
}));

function deferred() {
  let resolve;
  let reject;

  const promise = new Promise((res, rej) => {
    resolve = res;
    reject = rej;
  });

  return { promise, resolve, reject };
}

describe('useFetch', () => {
  beforeEach(() => {
    client.get.mockReset();
    clearApiCache();
  });

  it('keeps loading true until the most recent request finishes', async () => {
    const first = deferred();
    const second = deferred();

    client.get
      .mockImplementationOnce(() => first.promise)
      .mockImplementationOnce(() => second.promise);

    const { result } = renderHook(() => useFetch('/papers/me'));

    await waitFor(() => {
      expect(client.get).toHaveBeenCalledTimes(1);
    });

    act(() => {
      void result.current.refetch();
    });

    await waitFor(() => {
      expect(client.get).toHaveBeenCalledTimes(2);
    });

    await act(async () => {
      first.resolve({ data: ['stale-paper'] });
      await Promise.resolve();
    });

    expect(result.current.loading).toBe(true);
    expect(result.current.data).toBe(null);

    await act(async () => {
      second.resolve({ data: ['fresh-paper'] });
      await Promise.resolve();
    });

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
      expect(result.current.data).toEqual(['fresh-paper']);
      expect(result.current.error).toBe(null);
    });
  });

  it('clears stale state when the query key changes to a disabled request', async () => {
    client.get.mockResolvedValueOnce({ data: ['paper-a'] });

    const { result, rerender } = renderHook(
      ({ url, enabled }) => useFetch(url, { enabled }),
      {
        initialProps: { url: '/papers/me', enabled: true },
      },
    );

    await waitFor(() => {
      expect(result.current.data).toEqual(['paper-a']);
      expect(result.current.loading).toBe(false);
    });

    rerender({ url: '/analysis/next', enabled: false });

    await waitFor(() => {
      expect(result.current.data).toBe(null);
      expect(result.current.error).toBe(null);
      expect(result.current.loading).toBe(false);
    });
  });
});
