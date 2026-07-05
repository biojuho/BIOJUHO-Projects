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
            connectivity_status: 'online',
            device_count: 1,
            online_count: 1,
            stale_count: 0,
            offline_count: 0,
            latest_seen_at: '2026-04-09T01:05:00Z',
            sensors: [],
          },
        ],
        overall_status: 'normal',
        connectivity_status: 'online',
        total_readings: 1,
        device_count: 1,
        stale_sensor_count: 0,
        offline_sensor_count: 0,
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
            connectivity_status: 'online',
            device_count: 1,
            online_count: 1,
            stale_count: 0,
            offline_count: 0,
            latest_seen_at: '2026-04-09T01:05:00Z',
            sensors: [],
          },
        ],
        overall_status: 'normal',
        connectivity_status: 'online',
        total_readings: 1,
        device_count: 1,
        stale_sensor_count: 0,
        offline_sensor_count: 0,
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
            connectivity_status: 'online',
            device_count: 1,
            online_count: 1,
            stale_count: 0,
            offline_count: 0,
            latest_seen_at: '2026-04-09T01:05:00Z',
            sensors: [],
          },
        ],
        overall_status: 'alert',
        connectivity_status: 'online',
        total_readings: 4,
        device_count: 1,
        stale_sensor_count: 0,
        offline_sensor_count: 0,
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

  it('surfaces stale and offline sensor state from backend status', async () => {
    globalThis.fetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        zones: [
          {
            zone: 'Cold Storage A',
            avg_temp: -18,
            avg_humidity: 50,
            min_temp: -18.5,
            max_temp: -17.5,
            alert_count: 0,
            readings_count: 2,
            connectivity_status: 'stale',
            device_count: 2,
            online_count: 1,
            stale_count: 1,
            offline_count: 0,
            latest_seen_at: '2026-04-09T01:05:00Z',
            sensors: [
              {
                sensor_id: 'stale-sensor',
                status: 'stale',
                age_minutes: 12,
                last_seen_at: '2026-04-09T00:53:00Z',
              },
            ],
          },
          {
            zone: 'Transport Unit 1',
            avg_temp: -17,
            avg_humidity: 49,
            min_temp: -17,
            max_temp: -17,
            alert_count: 0,
            readings_count: 1,
            connectivity_status: 'offline',
            device_count: 1,
            online_count: 0,
            stale_count: 0,
            offline_count: 1,
            latest_seen_at: '2026-04-09T00:25:00Z',
            sensors: [
              {
                sensor_id: 'offline-sensor',
                status: 'offline',
                age_minutes: 40,
                last_seen_at: '2026-04-09T00:25:00Z',
              },
            ],
          },
        ],
        overall_status: 'alert',
        connectivity_status: 'offline',
        total_readings: 3,
        device_count: 3,
        online_sensor_count: 1,
        stale_sensor_count: 1,
        offline_sensor_count: 1,
        device_watch_hours: 24,
      }),
    });

    render(<ColdChainMonitor />);

    expect((await screen.findAllByText('Sensor offline')).length).toBeGreaterThan(0);
    expect(screen.getByText('1 offline and 1 stale across 3 devices')).toBeInTheDocument();
    expect(screen.getByText('Sensor Health')).toBeInTheDocument();
    expect(screen.getAllByText('1 offline / 1 stale').length).toBeGreaterThan(0);
    expect(screen.getByText('stale-sensor')).toBeInTheDocument();
    expect(screen.getByText('offline-sensor')).toBeInTheDocument();
  });

  it('allows long sensor health values to wrap instead of truncating on mobile cards', async () => {
    globalThis.fetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        zones: [],
        overall_status: 'alert',
        connectivity_status: 'offline',
        total_readings: 0,
        device_count: 79,
        online_sensor_count: 0,
        stale_sensor_count: 0,
        offline_sensor_count: 79,
        device_watch_hours: 24,
      }),
    });

    render(<ColdChainMonitor />);

    const sensorHealthValue = await screen.findByTestId('cold-chain-stat-sensor-health');
    const sensorHealthCard = screen.getByTestId('cold-chain-stat-card-sensor-health');

    expect(sensorHealthValue).toHaveTextContent('79 offline / 0 stale');
    expect(sensorHealthValue).toHaveClass('text-wrap');
    expect(sensorHealthValue).toHaveClass('min-h-8');
    expect(sensorHealthValue).toHaveClass('sm:min-h-12');
    expect(sensorHealthValue).toHaveClass('text-lg');
    expect(sensorHealthValue).toHaveClass('sm:text-xl');
    expect(sensorHealthValue).not.toHaveClass('truncate');
    expect(screen.getByTestId('cold-chain-stat-grid')).toHaveClass('grid-cols-2');
    expect(screen.getByTestId('cold-chain-stat-grid')).toHaveClass('gap-3');
    expect(screen.getByTestId('cold-chain-stat-grid')).toHaveClass('sm:gap-4');
    expect(sensorHealthCard).toHaveClass('col-span-2');
    expect(sensorHealthCard).toHaveClass('lg:col-span-1');
  });

  it('keeps registered silent zones visible when aggregate temperatures are empty', async () => {
    socketState.data = [];
    globalThis.fetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        zones: [
          {
            zone: 'Cold Storage B',
            avg_temp: null,
            avg_humidity: null,
            min_temp: null,
            max_temp: null,
            alert_count: 0,
            readings_count: 0,
            connectivity_status: 'offline',
            device_count: 1,
            online_count: 0,
            stale_count: 0,
            offline_count: 1,
            latest_seen_at: '2026-04-07T00:00:00Z',
            sensors: [
              {
                sensor_id: 'registered-silent-sensor',
                status: 'offline',
                age_minutes: 2880,
                registered: true,
                last_seen_at: '2026-04-07T00:00:00Z',
              },
            ],
          },
        ],
        overall_status: 'alert',
        connectivity_status: 'offline',
        total_readings: 0,
        device_count: 1,
        online_sensor_count: 0,
        stale_sensor_count: 0,
        offline_sensor_count: 1,
        device_watch_hours: 24,
      }),
    });

    render(<ColdChainMonitor />);

    expect(await screen.findByText('Cold Storage B')).toBeInTheDocument();
    expect(screen.getByText('registered-silent-sensor')).toBeInTheDocument();
    expect(screen.getByText('0 readings')).toBeInTheDocument();
    expect(screen.getAllByText('--').length).toBeGreaterThan(0);
  });
});
