import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import client, { buildApiUrl } from '../services/api';
import { useJobProgress } from './useJobProgress';

vi.mock('../services/api', () => ({
  default: {
    get: vi.fn(),
  },
  buildApiUrl: vi.fn((path) => `http://api.test${path}`),
}));

class FakeEventSource {
  constructor(url) {
    this.url = url;
    this.close = vi.fn();
    FakeEventSource.instances.push(this);
  }

  emit(snapshot) {
    this.onmessage?.({ data: JSON.stringify(snapshot) });
  }

  fail() {
    this.onerror?.(new Event('error'));
  }
}

FakeEventSource.instances = [];

describe('useJobProgress', () => {
  beforeEach(() => {
    client.get.mockReset();
    buildApiUrl.mockClear();
    FakeEventSource.instances = [];
    globalThis.EventSource = FakeEventSource;
  });

  afterEach(() => {
    delete globalThis.EventSource;
  });

  it('streams job progress with EventSource and resolves on success', async () => {
    const onSuccess = vi.fn();
    const { result } = renderHook(() => useJobProgress({ onSuccess }));

    let promise;
    await act(async () => {
      promise = result.current.watchJob({ id: 'job-1', status: 'queued', progress: 0 });
    });

    await waitFor(() => {
      expect(FakeEventSource.instances).toHaveLength(1);
    });

    expect(buildApiUrl).toHaveBeenCalledWith('/jobs/job-1/events');
    expect(FakeEventSource.instances[0].url).toBe('http://api.test/jobs/job-1/events');

    await act(async () => {
      FakeEventSource.instances[0].emit({
        id: 'job-1',
        status: 'running',
        partial: true,
        progress: 55,
        message: 'Working',
      });
    });

    expect(result.current.job.progress).toBe(55);
    expect(result.current.isRunning).toBe(true);

    await act(async () => {
      FakeEventSource.instances[0].emit({
        id: 'job-1',
        status: 'succeeded',
        partial: false,
        progress: 100,
        result: { ok: true },
      });
      await expect(promise).resolves.toEqual({ ok: true });
    });

    expect(onSuccess).toHaveBeenCalledWith(
      { ok: true },
      expect.objectContaining({ id: 'job-1', status: 'succeeded' }),
    );
    expect(result.current.isRunning).toBe(false);
  });

  it('falls back to polling when EventSource is unavailable', async () => {
    delete globalThis.EventSource;
    client.get.mockResolvedValueOnce({
      data: {
        id: 'job-2',
        status: 'succeeded',
        progress: 100,
        result: { collected: 3 },
      },
    });

    const { result } = renderHook(() => useJobProgress());

    let promise;
    await act(async () => {
      promise = result.current.watchJob({ id: 'job-2', status: 'queued', progress: 0 });
    });

    await waitFor(() => {
      expect(client.get).toHaveBeenCalledWith('/jobs/job-2', { timeout: 10_000 });
    });

    await expect(promise).resolves.toEqual({ collected: 3 });
  });

  it('falls back to polling when EventSource ends before the terminal snapshot', async () => {
    client.get.mockResolvedValueOnce({
      data: {
        id: 'job-3',
        status: 'succeeded',
        progress: 100,
        result: { matched: 2 },
      },
    });

    const onSuccess = vi.fn();
    const { result } = renderHook(() => useJobProgress({ onSuccess }));

    let promise;
    await act(async () => {
      promise = result.current.watchJob({ id: 'job-3', status: 'queued', progress: 0 });
    });

    await waitFor(() => {
      expect(FakeEventSource.instances).toHaveLength(1);
    });

    await act(async () => {
      FakeEventSource.instances[0].emit({
        id: 'job-3',
        status: 'running',
        progress: 65,
        message: 'Still working',
      });
    });

    expect(result.current.job.progress).toBe(65);

    await act(async () => {
      FakeEventSource.instances[0].fail();
    });

    await waitFor(() => {
      expect(client.get).toHaveBeenCalledWith('/jobs/job-3', { timeout: 10_000 });
    });

    await expect(promise).resolves.toEqual({ matched: 2 });
    expect(onSuccess).toHaveBeenCalledWith(
      { matched: 2 },
      expect.objectContaining({ id: 'job-3', status: 'succeeded' }),
    );
    expect(FakeEventSource.instances[0].close).toHaveBeenCalled();
  });
});
