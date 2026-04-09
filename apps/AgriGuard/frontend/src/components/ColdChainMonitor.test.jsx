import { act, cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import ColdChainMonitor from './ColdChainMonitor';

const socketState = {
  data: [],
  connected: true,
};

vi.mock('../contexts/ToastContext', () => ({
  useToast: () => ({
    showToast: vi.fn(),
  }),
}));

vi.mock('../hooks/useThrottledWebSocket', () => ({
  useThrottledWebSocket: () => socketState,
}));

vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }) => <div>{children}</div>,
  LineChart: ({ children }) => <div>{children}</div>,
  Line: () => <div />,
  XAxis: () => <div />,
  YAxis: () => <div />,
  Tooltip: () => <div />,
  CartesianGrid: () => <div />,
  ReferenceLine: () => <div />,
}));

describe('ColdChainMonitor', () => {
  beforeEach(() => {
    vi.useRealTimers();
    socketState.connected = true;
    socketState.data = [
      {
        sensor_id: 'sensor-a',
        timestamp: '2026-04-09T01:00:00Z',
        temperature: -17,
        humidity: 50,
        zone: 'Cold Storage A',
        status: 'normal',
        alerts: [],
      },
      {
        sensor_id: 'sensor-b',
        timestamp: '2026-04-09T01:05:00Z',
        temperature: 12,
        humidity: 55,
        zone: 'Cold Storage A',
        status: 'alert',
        alerts: ['Temperature too high: 12C'],
      },
    ];

    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    cleanup();
  });

  it('renders zone status from backend aggregates instead of chart buffer samples', async () => {
    globalThis.fetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        zones: [
          {
            zone: 'Cold Storage A',
            avg_temp: -17,
            avg_humidity: 50,
            min_temp: -17,
            max_temp: -17,
            alert_count: 0,
            readings_count: 1,
          },
        ],
        overall_status: 'normal',
        total_readings: 1,
      }),
    });

    render(<ColdChainMonitor />);

    expect(await screen.findByText('Zone Overview')).toBeInTheDocument();
    expect(screen.getAllByText('Cold Storage A').length).toBeGreaterThan(0);
    expect(screen.queryByText('1 alerts')).not.toBeInTheDocument();
  });

  it('refreshes backend aggregate status on the polling interval', async () => {
    vi.useFakeTimers();
    const responses = [
      {
        zones: [
          {
            zone: 'Cold Storage A',
            avg_temp: -17,
            avg_humidity: 50,
            min_temp: -17,
            max_temp: -17,
            alert_count: 0,
            readings_count: 1,
          },
        ],
        overall_status: 'normal',
        total_readings: 1,
      },
      {
        zones: [
          {
            zone: 'Cold Storage A',
            avg_temp: -15,
            avg_humidity: 52,
            min_temp: -18,
            max_temp: 12,
            alert_count: 1,
            readings_count: 4,
          },
        ],
        overall_status: 'alert',
        total_readings: 4,
      },
    ];
    let fetchCount = 0;
    globalThis.fetch.mockImplementation(() => {
      const index = fetchCount >= 2 ? 1 : 0;
      fetchCount += 1;
      return Promise.resolve({
        ok: true,
        json: async () => responses[index],
      });
    });

    render(<ColdChainMonitor />);

    await act(async () => {
      await Promise.resolve();
    });

    expect(screen.getAllByText('Zone Overview').length).toBeGreaterThan(0);
    expect(screen.queryByText('1 alerts')).not.toBeInTheDocument();
    const initialFetchCount = globalThis.fetch.mock.calls.length;

    await act(async () => {
      await vi.advanceTimersByTimeAsync(15000);
    });

    expect(globalThis.fetch.mock.calls.length).toBeGreaterThan(initialFetchCount);
    expect(screen.getByText('1 alerts')).toBeInTheDocument();
  });
});
