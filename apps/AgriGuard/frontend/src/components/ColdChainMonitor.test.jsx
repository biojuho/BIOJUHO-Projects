import { render, screen } from '@testing-library/react';
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

    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve({
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
        }),
      ),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('keeps zone status in sync with live websocket readings', async () => {
    render(<ColdChainMonitor />);

    expect(await screen.findByText('1 alerts')).toBeInTheDocument();
    expect(screen.getAllByText('Cold Storage A').length).toBeGreaterThan(0);
  });
});
