/* global describe, it, expect, vi, beforeEach, afterEach */
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import Dashboard from './Dashboard';
import api from '../../services/api';

vi.mock('../../services/api', () => ({
  withOperatorAuth: (config = {}) => config,
  default: {
    get: vi.fn(),
  },
}));

vi.mock('../../contexts/ToastContext', () => ({
  useToast: () => ({
    showToast: vi.fn(),
  }),
}));

const dashboardSummary = {
  total_products: 4,
  certified_products: 3,
  cold_chain_products: 2,
  total_tracking_events: 8,
  status_distribution: {
    harvested: 3,
    shipped: 1,
  },
  origin_distribution: {
    Naju: 2,
    Andong: 2,
  },
};

const qrKpis = {
  status: 'success',
  hours: 24,
  variant_id: 'all',
  since: '2026-06-10T00:00:00Z',
  scan_start_sessions: 1250,
  scan_success_sessions: 1240,
  scan_failure_sessions: 10,
  verification_complete_sessions: 1240,
  consumer_scan_sessions: 1240,
  scan_success_rate: 0.992,
  target_scan_success_rate: 0.99,
  scan_success_status: 'on_track',
  target_daily_scans: 1000,
  daily_scan_progress: 1,
  daily_scan_status: 'on_track',
};

const qrTrend = {
  status: 'success',
  days: 7,
  variant_id: 'all',
  timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC',
  target_scan_success_rate: 0.99,
  target_daily_scans: 1000,
  items: [
    {
      date: '2026-06-10',
      scan_start_sessions: 1250,
      scan_success_sessions: 1240,
      verification_complete_sessions: 1240,
      scan_success_rate: 0.992,
      daily_scan_progress: 1,
      scan_success_status: 'on_track',
      daily_scan_status: 'on_track',
    },
  ],
};

describe('Dashboard', () => {
  beforeEach(() => {
    window.localStorage.clear();
    api.get.mockImplementation((url, config = {}) => {
      if (url === '/dashboard/summary') {
        return Promise.resolve({ data: dashboardSummary });
      }
      if (url === '/qr-events/kpis') {
        return Promise.resolve({ data: qrKpis });
      }
      if (url === '/qr-events/kpis/trend') {
        return Promise.resolve({
          data: {
            ...qrTrend,
            timezone: config.params?.timezone || qrTrend.timezone,
          },
        });
      }
      return Promise.reject(new Error(`unexpected URL ${url}`));
    });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('renders consumer QR KPI status from the KPI endpoint', async () => {
    const browserTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';

    render(<Dashboard />);

    expect(await screen.findByText('Consumer QR KPIs')).toBeInTheDocument();
    expect(screen.getByText('AgriGuard 공급망 현황')).toBeInTheDocument();
    expect(screen.getByText('전체 제품')).toBeInTheDocument();
    expect(screen.getByText('인증 제품')).toBeInTheDocument();
    expect(screen.getByText('콜드체인 제품')).toBeInTheDocument();
    expect(screen.getByText('추적 이벤트')).toBeInTheDocument();
    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith('/qr-events/kpis');
      expect(api.get).toHaveBeenCalledWith('/qr-events/kpis/trend', {
        params: { days: 7, timezone: browserTimezone },
      });
    });
    expect(screen.getAllByText('99.2%').length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText('1240')).toBeInTheDocument();
    expect(screen.getAllByText('On track').length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText(/Target 99%/)).toBeInTheDocument();
    expect(screen.getByText(/Target 1,000 scans in 24 hours/)).toBeInTheDocument();
    expect(screen.getByText('7-day QR trend')).toBeInTheDocument();
    expect(screen.getByText(`All variants / ${browserTimezone}`)).toBeInTheDocument();
    expect(screen.getByText('1,240 scans')).toBeInTheDocument();
  });

  it('refetches QR KPI trend when the reporting timezone changes', async () => {
    const browserTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
    const targetTimezone = browserTimezone === 'Asia/Seoul' ? 'UTC' : 'Asia/Seoul';

    render(<Dashboard />);

    const timezoneSelect = await screen.findByLabelText('Reporting day');
    expect(timezoneSelect).toHaveValue(browserTimezone);

    fireEvent.change(timezoneSelect, { target: { value: targetTimezone } });

    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith('/qr-events/kpis/trend', {
        params: { days: 7, timezone: targetTimezone },
      });
    });
    expect(timezoneSelect).toHaveValue(targetTimezone);
    expect(window.localStorage.getItem('agriguard.qrKpi.reportingTimezone')).toBe(targetTimezone);
  });

  it('classifies a protected dashboard summary as an operator auth issue', async () => {
    api.get.mockImplementation((url, config = {}) => {
      if (url === '/dashboard/summary') {
        return Promise.reject({
          message: 'Request failed with status code 401',
          response: { status: 401 },
        });
      }
      if (url === '/qr-events/kpis') {
        return Promise.resolve({ data: qrKpis });
      }
      if (url === '/qr-events/kpis/trend') {
        return Promise.resolve({
          data: {
            ...qrTrend,
            timezone: config.params?.timezone || qrTrend.timezone,
          },
        });
      }
      return Promise.reject(new Error(`unexpected URL ${url}`));
    });

    render(<Dashboard />);

    expect(await screen.findByText('Operator authentication required')).toBeInTheDocument();
    expect(screen.getByText('Save a Firebase/operator token in QR Tokens or Sensors, then reload the dashboard.')).toBeInTheDocument();
    expect(screen.queryByText('백엔드 연결 실패')).not.toBeInTheDocument();
    expect(screen.getByText('Request failed with status code 401')).toBeInTheDocument();
  });
});
