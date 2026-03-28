/* global describe, it, expect, vi, beforeEach, afterEach */
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import QRReader from './QRReader';
import { ToastProvider } from '../contexts/ToastContext';
import { trackQrEvent } from '../services/qrAnalytics';

const navigateMock = vi.fn();

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => navigateMock,
  };
});

vi.mock('@yudiel/react-qr-scanner', () => ({
  Scanner: ({ onScan, onError }) => (
    <div data-testid="scanner-mock">
      <button type="button" onClick={() => onScan([{ rawValue: 'https://agriguard.test/product/prod-1' }])}>
        trigger-success
      </button>
      <button type="button" onClick={() => onScan([{ rawValue: 'not-a-valid-qr' }])}>
        trigger-invalid
      </button>
      <button type="button" onClick={() => onError(new Error('permission denied'))}>
        trigger-error
      </button>
    </div>
  ),
}));

vi.mock('framer-motion', () => ({
  motion: {
    div: ({ children, ...props }) => <div {...props}>{children}</div>,
  },
  AnimatePresence: ({ children }) => <>{children}</>,
}));

vi.mock('../services/qrAnalytics', () => ({
  QR_EXPERIMENT_VARIANT: 'qr_page_v1',
  createQrSessionId: () => 'qr-session-1234',
  normalizeScannerError: (error) => ({
    error_code: 'camera_permission_denied',
    error_message: error.message,
  }),
  trackQrEvent: vi.fn(() => Promise.resolve(true)),
}));

function renderReader() {
  return render(
    <ToastProvider>
      <MemoryRouter>
        <QRReader />
      </MemoryRouter>
    </ToastProvider>,
  );
}

describe('QRReader', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('tracks scan failure and recovery', async () => {
    renderReader();

    await waitFor(() => {
      expect(trackQrEvent).toHaveBeenCalledWith(
        expect.objectContaining({ event_type: 'scan_start', session_id: 'qr-session-1234' }),
      );
    });

    fireEvent.click(screen.getByRole('button', { name: 'trigger-invalid' }));

    await waitFor(() => {
      expect(trackQrEvent).toHaveBeenCalledWith(
        expect.objectContaining({ event_type: 'scan_failure', error_code: 'invalid_qr_format' }),
      );
    });

    fireEvent.click(screen.getByRole('button', { name: /Retry scan/i }));

    await waitFor(() => {
      expect(trackQrEvent).toHaveBeenCalledWith(
        expect.objectContaining({ event_type: 'scan_recovery', recovery_method: 'retry_button' }),
      );
    });
  });

  it('navigates to the verification page after a successful scan', async () => {
    vi.useFakeTimers();
    renderReader();

    fireEvent.click(screen.getByRole('button', { name: 'trigger-success' }));
    await act(async () => {
      await vi.runAllTimersAsync();
    });

    expect(navigateMock).toHaveBeenCalledWith(
      '/product/prod-1?scan_source=qr_reader&scan_session=qr-session-1234&scan_variant=qr_page_v1',
    );
  });
});
