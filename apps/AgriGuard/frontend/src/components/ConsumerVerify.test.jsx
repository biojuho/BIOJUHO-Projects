/* global describe, it, expect, vi, beforeEach, afterEach */
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import ConsumerVerify from './ConsumerVerify';
import { qrVerifyApi } from '../services/api';

const toastMocks = vi.hoisted(() => ({
  hideToast: vi.fn(),
}));

vi.mock('../services/api', () => ({
  qrVerifyApi: {
    verify: vi.fn(),
  },
}));

vi.mock('../services/qrAnalytics', () => ({
  createQrSessionId: () => 'generated-session-1',
}));

vi.mock('../contexts/ToastContext', () => ({
  useToast: () => toastMocks,
}));

function renderVerify(route = '/verify/product-1?scan_session=session-1&scan_variant=qr_consumer_c') {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <Routes>
        <Route path="/verify/:qrToken" element={<ConsumerVerify />} />
        <Route path="/scan" element={<div>Scanner</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

function safePayload() {
  return {
    status: 'success',
    is_valid: true,
    verified_at: '2026-06-09T05:00:00Z',
    last_verified_at: '2026-06-09T05:00:00Z',
    trust_badge: {
      status: 'Safe',
      label: 'Verified batch',
      reason: 'The batch is operator-verified and recent temperature data is acceptable.',
    },
    product: {
      name: 'Hallabong',
      category: 'Fruit',
      origin: 'Jeju',
    },
    batch: {
      batch_code: 'AG-1234567890',
      harvest_date: '2026-06-01T00:00:00Z',
      cold_chain_required: true,
      recall_status: 'not_reported',
    },
    route: [
      {
        timestamp: '2026-06-09T03:00:00Z',
        status: 'PACKED',
        location: 'Jeju Packhouse',
      },
    ],
    temperature_summary: {
      status: 'safe',
      message: 'Recent cold-chain readings are within the expected range.',
      min_celsius: 2.1,
      max_celsius: 3.4,
      average_celsius: 2.8,
      readings_count: 2,
      last_reading_at: '2026-06-09T04:58:00Z',
      is_stale: false,
    },
    blockchain_proof: {
      status: 'anchored',
      message: 'Audit evidence is anchored in the AgriGuard chain.',
      record_count: 1,
      latest_tx_hash: '0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef',
      evidence_hash: 'hash-123',
      records: [
        {
          tx_hash: '0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef',
          block: '12',
          timestamp: '2026-06-09T03:01:00Z',
          event_type: 'REGISTER',
        },
      ],
    },
    consumer_notice: 'Only public traceability fields are shown.',
  };
}

describe('ConsumerVerify', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    toastMocks.hideToast.mockClear();
  });

  afterEach(() => {
    cleanup();
  });

  it('renders the mobile consumer verification summary and noindex meta', async () => {
    qrVerifyApi.verify.mockResolvedValue({ data: safePayload() });

    renderVerify();

    expect(await screen.findByText('Verified batch')).toBeInTheDocument();
    expect(screen.getByTestId('consumer-trust-badge')).toHaveTextContent('Safe');
    expect(screen.getByTestId('consumer-trust-heading')).toHaveClass('text-xl');
    expect(screen.getByTestId('consumer-trust-heading')).toHaveClass('sm:text-2xl');
    expect(screen.getByText('Hallabong')).toBeInTheDocument();
    expect(screen.getByText('Jeju')).toBeInTheDocument();
    expect(screen.getByText('AG-1234567890')).toBeInTheDocument();
    expect(screen.getByText('Last verified')).toBeInTheDocument();
    expect(screen.queryByText('Last checked')).not.toBeInTheDocument();
    expect(screen.getByText('Evidence hash: hash-123')).toBeInTheDocument();
    expect(screen.getByTestId('consumer-proof-tx')).toHaveTextContent(
      'TX 0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef',
    );
    expect(screen.getByTestId('consumer-proof-tx')).toHaveClass('break-all');
    expect(document.querySelector('meta[name="robots"]')).toHaveAttribute('content', 'noindex,nofollow');
    expect(toastMocks.hideToast).toHaveBeenCalled();

    expect(qrVerifyApi.verify).toHaveBeenCalledWith('product-1', {
      sessionId: 'session-1',
      variantId: 'qr_consumer_c',
      source: 'consumer_verify_page',
    });
  });

  it('renders the invalid QR fallback without product fields', async () => {
    qrVerifyApi.verify.mockResolvedValue({
      data: {
        ...safePayload(),
        status: 'unknown',
        is_valid: false,
        trust_badge: {
          status: 'Unknown',
          label: 'QR not verified',
          reason: 'This code is invalid, expired, fake, or not issued by AgriGuard.',
        },
        product: null,
        batch: null,
        route: [],
        consumer_notice: 'Do not rely on this QR code.',
      },
    });

    renderVerify('/verify/fake-token');

    expect(await screen.findByText('QR not verified')).toBeInTheDocument();
    expect(screen.getByTestId('consumer-trust-badge')).toHaveTextContent('Not verified');
    expect(screen.getByText('Unverified AgriGuard QR')).toBeInTheDocument();
    expect(screen.getAllByText('Not verified')).toHaveLength(2);
    expect(screen.getByText('Last checked')).toBeInTheDocument();
    expect(screen.queryByText('Last verified')).not.toBeInTheDocument();

    await waitFor(() => {
      expect(qrVerifyApi.verify).toHaveBeenCalledWith('fake-token', {
        sessionId: 'generated-session-1',
        variantId: 'qr_consumer_v1',
        source: 'consumer_verify_page',
      });
    });
  });

  it('labels registered QR codes with incomplete public evidence as pending', async () => {
    qrVerifyApi.verify.mockResolvedValue({
      data: {
        ...safePayload(),
        status: 'success',
        is_valid: true,
        trust_badge: {
          status: 'Unknown',
          label: 'Needs more evidence',
          reason: 'The QR is registered, but public evidence is incomplete or delayed.',
        },
      },
    });

    renderVerify('/verify/pending-token');

    expect(await screen.findByText('Needs more evidence')).toBeInTheDocument();
    expect(screen.getByTestId('consumer-trust-badge')).toHaveTextContent('Evidence pending');
    expect(screen.getByText('Last checked')).toBeInTheDocument();
    expect(screen.queryByText('Last verified')).not.toBeInTheDocument();
  });
});
