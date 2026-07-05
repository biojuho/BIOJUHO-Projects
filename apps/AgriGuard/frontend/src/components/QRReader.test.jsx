/* global describe, it, expect, vi, beforeEach, afterEach */
import { StrictMode } from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import QRReader from './QRReader';
import { ToastProvider } from '../contexts/ToastContext';
import { trackQrEvent } from '../services/qrAnalytics';

const navigateMock = vi.fn();
let scannerApi;

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => navigateMock,
  };
});

vi.mock('@yudiel/react-qr-scanner', () => ({
  Scanner: ({ onScan, onError, components }) => {
    scannerApi = {
      components,
      triggerSuccess: () => onScan([{ rawValue: 'https://agriguard.test/product/prod-1' }]),
      triggerAgriVerify: () => onScan([{ rawValue: 'agri://verify/prod-2' }]),
      triggerPublicVerifyUrl: () => onScan([{ rawValue: 'https://verify.agriguard.test/verify/prod-3?utm=label' }]),
      triggerInvalid: () => onScan([{ rawValue: 'not-a-valid-qr' }]),
      triggerError: () => onError(new Error('permission denied')),
    };

    return (
      <div data-testid="scanner-mock">
        <button type="button" onClick={scannerApi.triggerSuccess}>
        trigger-success
        </button>
        <button type="button" onClick={scannerApi.triggerAgriVerify}>
        trigger-agri-verify
        </button>
        <button type="button" onClick={scannerApi.triggerPublicVerifyUrl}>
        trigger-public-verify-url
        </button>
        <button type="button" onClick={scannerApi.triggerInvalid}>
        trigger-invalid
        </button>
        <button type="button" onClick={scannerApi.triggerError}>
        trigger-error
        </button>
      </div>
    );
  },
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

function renderReader({ strict = false } = {}) {
  const tree = (
    <ToastProvider>
      <MemoryRouter>
        <QRReader />
      </MemoryRouter>
    </ToastProvider>
  );

  if (strict) {
    return render(<StrictMode>{tree}</StrictMode>);
  }

  return render(
    tree,
  );
}

function scanStartCalls() {
  return trackQrEvent.mock.calls.filter(
    ([event]) => event?.event_type === 'scan_start',
  );
}

describe('QRReader', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    scannerApi = undefined;
  });

  afterEach(() => {
    vi.useRealTimers();
    cleanup();
  });

  it('exposes the scanner page title as the primary heading', () => {
    renderReader();

    expect(screen.getByRole('heading', { level: 1, name: /Scan Product QR/i })).toBeInTheDocument();
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

  it('keeps the scan frame free of the built-in camera toggle control', () => {
    renderReader();

    expect(screen.getByTestId('scanner-frame')).toHaveClass('max-w-[248px]');
    expect(screen.getByTestId('scanner-frame')).toHaveClass('sm:max-w-none');
    expect(scannerApi.components).toEqual(expect.objectContaining({
      audio: false,
      finder: true,
      onOff: false,
      torch: true,
      zoom: true,
    }));
  });

  it('tracks one scan start per attempt under StrictMode effect replay', async () => {
    renderReader({ strict: true });

    await waitFor(() => {
      expect(scanStartCalls()).toHaveLength(1);
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
      '/verify/prod-1?scan_source=qr_reader&scan_session=qr-session-1234&scan_variant=qr_page_v1',
    );
  });

  it('accepts registered agri verify QR values', async () => {
    vi.useFakeTimers();
    renderReader();

    fireEvent.click(screen.getByRole('button', { name: 'trigger-agri-verify' }));
    await act(async () => {
      await vi.runAllTimersAsync();
    });

    expect(navigateMock).toHaveBeenCalledWith(
      '/verify/prod-2?scan_source=qr_reader&scan_session=qr-session-1234&scan_variant=qr_page_v1',
    );
  });

  it('accepts public verify URLs generated for QR labels', async () => {
    vi.useFakeTimers();
    renderReader();

    fireEvent.click(screen.getByRole('button', { name: 'trigger-public-verify-url' }));
    await act(async () => {
      await vi.runAllTimersAsync();
    });

    expect(navigateMock).toHaveBeenCalledWith(
      '/verify/prod-3?scan_source=qr_reader&scan_session=qr-session-1234&scan_variant=qr_page_v1',
    );
  });

  it('navigates with a manual token when camera scanning is unavailable', async () => {
    renderReader();

    fireEvent.change(screen.getByLabelText(/Manual verification code/i), {
      target: { value: ' mock-0 ' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Verify code/i }));

    await waitFor(() => {
      expect(navigateMock).toHaveBeenCalledWith(
        '/verify/mock-0?scan_source=qr_reader&scan_session=qr-session-1234&scan_variant=qr_page_v1',
      );
    });
    expect(trackQrEvent).toHaveBeenCalledWith(
      expect.objectContaining({
        event_type: 'scan_recovery',
        recovery_method: 'manual_entry',
        qr_value: 'mock-0',
      }),
    );
  });

  it('ignores late camera errors after manual recovery starts', async () => {
    renderReader();

    fireEvent.change(screen.getByLabelText(/Manual verification code/i), {
      target: { value: ' late-error-token ' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Verify code/i }));

    await waitFor(() => {
      expect(navigateMock).toHaveBeenCalledWith(
        '/verify/late-error-token?scan_source=qr_reader&scan_session=qr-session-1234&scan_variant=qr_page_v1',
      );
    });

    act(() => {
      scannerApi.triggerError();
    });

    await waitFor(() => {
      expect(screen.queryByText('Camera access failed')).not.toBeInTheDocument();
      expect(screen.queryByText(/Camera error:/i)).not.toBeInTheDocument();
    });
  });

  it('navigates with URL-safe manual tokens that start with a dash', async () => {
    renderReader();

    fireEvent.change(screen.getByLabelText(/Manual verification code/i), {
      target: { value: ' -mock_0 ' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Verify code/i }));

    await waitFor(() => {
      expect(navigateMock).toHaveBeenCalledWith(
        '/verify/-mock_0?scan_source=qr_reader&scan_session=qr-session-1234&scan_variant=qr_page_v1',
      );
    });
  });

  it('navigates with a full public verify URL entered manually', async () => {
    renderReader();

    fireEvent.change(screen.getByLabelText(/Manual verification code/i), {
      target: { value: ' https://verify.agriguard.test/verify/manual-token?utm=label ' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Verify code/i }));

    await waitFor(() => {
      expect(navigateMock).toHaveBeenCalledWith(
        '/verify/manual-token?scan_source=qr_reader&scan_session=qr-session-1234&scan_variant=qr_page_v1',
      );
    });
  });

  it('rejects malformed manual entries before navigation', async () => {
    renderReader();

    fireEvent.change(screen.getByLabelText(/Manual verification code/i), {
      target: { value: '###' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Verify code/i }));

    await waitFor(() => {
      expect(trackQrEvent).toHaveBeenCalledWith(
        expect.objectContaining({ event_type: 'scan_failure', error_code: 'manual_qr_format' }),
      );
    });
    expect(navigateMock).not.toHaveBeenCalled();
  });

  it('does not schedule duplicate navigation for repeated scan callbacks', async () => {
    vi.useFakeTimers();
    renderReader();

    act(() => {
      scannerApi.triggerSuccess();
      scannerApi.triggerSuccess();
    });

    await act(async () => {
      await vi.runAllTimersAsync();
    });

    expect(navigateMock).toHaveBeenCalledTimes(1);
  });

  it('clears pending navigation when unmounted', async () => {
    vi.useFakeTimers();
    const { unmount } = renderReader();

    fireEvent.click(screen.getByRole('button', { name: 'trigger-success' }));
    unmount();

    await act(async () => {
      await vi.runAllTimersAsync();
    });

    expect(navigateMock).not.toHaveBeenCalled();
  });
});
