import { act, cleanup, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useThrottledWebSocket } from './useThrottledWebSocket';

const sockets = [];

class MockWebSocket {
  constructor(url) {
    this.url = url;
    sockets.push(this);
  }

  close() {
    this.onclose?.();
  }

  emitOpen() {
    this.onopen?.();
  }

  emitClose() {
    this.onclose?.();
  }

  emitMessage(payload) {
    this.onmessage?.({ data: payload });
  }
}

describe('useThrottledWebSocket', () => {
  beforeEach(() => {
    sockets.length = 0;
    vi.useFakeTimers();
    vi.stubGlobal('WebSocket', MockWebSocket);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    cleanup();
  });

  it('ignores malformed frames and flushes valid messages', async () => {
    const onAlert = vi.fn();
    const { result } = renderHook(() =>
      useThrottledWebSocket('ws://example.test/iot', {
        throttleMs: 25,
        maxItems: 2,
        onAlert,
      }),
    );

    const socket = sockets[0];

    act(() => {
      socket.emitOpen();
      socket.emitMessage('not-json');
      socket.emitMessage(JSON.stringify({
        sensor_id: 'sensor-1',
        alerts: ['temperature alert'],
        status: 'alert',
      }));
    });

    expect(result.current.connected).toBe(true);
    expect(onAlert).toHaveBeenCalledWith('temperature alert');

    await act(async () => {
      await vi.advanceTimersByTimeAsync(25);
    });

    expect(result.current.data).toEqual([
      {
        sensor_id: 'sensor-1',
        alerts: ['temperature alert'],
        status: 'alert',
      },
    ]);
  });

  it('reconnects after an unexpected disconnect', async () => {
    const { result } = renderHook(() =>
      useThrottledWebSocket('ws://example.test/iot', {
        throttleMs: 25,
        maxItems: 2,
      }),
    );

    const firstSocket = sockets[0];

    act(() => {
      firstSocket.emitOpen();
    });
    expect(result.current.connected).toBe(true);

    act(() => {
      firstSocket.emitClose();
    });
    expect(result.current.connected).toBe(false);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });

    expect(sockets).toHaveLength(2);

    act(() => {
      sockets[1].emitOpen();
    });
    expect(result.current.connected).toBe(true);
  });
});
