/* global describe, it, expect, vi, beforeEach, afterEach */
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import ProductDetail from './ProductDetail';
import { hasOperatorToken, productApi } from '../services/api';
import { trackQrEvent } from '../services/qrAnalytics';

vi.mock('../services/api', () => ({
  hasOperatorToken: vi.fn(() => false),
  productApi: {
    getById: vi.fn(),
    getHistory: vi.fn(),
    addTracking: vi.fn(),
    addCertification: vi.fn(),
  },
}));

vi.mock('../services/qrAnalytics', () => ({
  trackQrEvent: vi.fn(() => Promise.resolve(true)),
}));

const renderWithRouter = (ui, { route = '/product/1' } = {}) =>
  render(
    <MemoryRouter initialEntries={[route]}>
      <Routes>
        <Route path="/product/:id" element={ui} />
      </Routes>
    </MemoryRouter>,
  );

const mockProduct = {
  id: '1',
  name: 'Organic Apples',
  category: 'Fruit',
  origin: 'Seoul Farm',
  harvest_date: '2026-06-01T00:00:00Z',
  qr_code: 'QR-12345',
  requires_cold_chain: true,
  description: 'Fresh organic apples',
};

const timelineIsoTimestamp = '2026-07-05T23:47:51.279659+00:00';
const timelineLocalizedTimestamp = new Intl.DateTimeFormat('en-US', {
  year: 'numeric',
  month: 'short',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  timeZoneName: 'short',
}).format(new Date(timelineIsoTimestamp));

const mockHistory = [
  {
    block: 1,
    data: {
      action: 'REGISTERED',
      status: 'IN_TRANSIT',
      timestamp: timelineIsoTimestamp,
      location: 'Farm',
      handler_id: 'HANDLER-VERY-LONG-1234567890',
    },
    timestamp: timelineIsoTimestamp,
    tx_hash: '0x1234567890',
  },
];

describe('ProductDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
      configurable: true,
    });
    hasOperatorToken.mockReturnValue(false);
    vi.useRealTimers();
  });

  afterEach(() => {
    cleanup();
  });

  it('renders product details after loading', async () => {
    productApi.getById.mockResolvedValueOnce({ data: mockProduct });
    productApi.getHistory.mockResolvedValueOnce({ data: { history: mockHistory } });

    renderWithRouter(<ProductDetail />);

    expect(screen.queryByRole('button', { hidden: true })).toBeNull();

    await waitFor(() => {
      expect(screen.getByText('Organic Apples')).toBeInTheDocument();
      expect(screen.getByTestId('product-detail-card-content')).toHaveClass('p-4');
      expect(screen.getByTestId('product-detail-card-content')).toHaveClass('sm:p-8');
      expect(screen.getByTestId('product-detail-qr-card')).toHaveClass('w-full');
      expect(screen.getByTestId('product-detail-qr-card')).toHaveClass('max-w-xs');
      expect(screen.getByTestId('product-detail-qr-card')).toHaveClass('self-center');
      expect(screen.getByTestId('product-detail-qr-card')).not.toHaveClass('min-w-[200px]');
      expect(screen.getByTestId('product-detail-qr-card')).toHaveClass('md:min-w-[200px]');
      expect(screen.getByTestId('product-detail-qr-card-content')).toHaveClass('p-3');
      expect(screen.getByTestId('product-detail-qr-card-content')).toHaveClass('sm:p-4');
      expect(screen.getByTestId('product-detail-evidence-grid')).toHaveClass('mt-4');
      expect(screen.getByTestId('product-detail-evidence-grid')).toHaveClass('grid-cols-3');
      expect(screen.getByTestId('product-detail-evidence-grid')).toHaveClass('md:mt-8');
      expect(screen.getByTestId('product-detail-heading')).toHaveClass('text-2xl');
      expect(screen.getByTestId('product-detail-heading')).toHaveClass('sm:text-3xl');
      expect(screen.getByTestId('product-detail-actions')).toHaveClass('grid');
      expect(screen.getByTestId('product-detail-actions')).toHaveClass('grid-cols-2');
      expect(screen.getByTestId('product-detail-actions')).toHaveClass('mt-4');
      expect(screen.getByTestId('product-detail-actions')).toHaveClass('gap-2');
      expect(screen.getByTestId('product-detail-actions')).toHaveClass('sm:flex');
      expect(screen.getByTestId('product-detail-card-content')).toContainElement(screen.getByTestId('product-detail-actions'));
      expect(screen.getByText('Seoul Farm')).toBeInTheDocument();
      expect(screen.getByRole('img', { name: 'Product verification QR' })).toBeInTheDocument();
      const qrValue = screen.getByTestId('product-detail-qr-value');
      expect(qrValue).toHaveTextContent('QR-12345');
      expect(qrValue).toHaveAttribute('title', 'QR-12345');
      expect(qrValue).toHaveClass('break-all');
      expect(qrValue).toHaveClass('select-all');
      expect(screen.getByTestId('product-detail-id')).toHaveTextContent('1');
      expect(screen.getByTestId('product-detail-id')).toHaveAttribute('title', '1');
      expect(screen.getByTestId('product-detail-id')).toHaveClass('truncate');
      expect(screen.getByTestId('product-detail-id')).toHaveClass('select-all');
      expect(screen.getByTestId('product-detail-id')).not.toHaveClass('break-all');
      expect(screen.getByText('Jun 1, 2026')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Copy product ID/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Copy public verify label URL/i })).toBeInTheDocument();
      expect(screen.queryByAltText('QR Code')).not.toBeInTheDocument();
      expect(document.querySelector('img[src*="api.qrserver.com"]')).toBeNull();
      expect(screen.getByRole('button', { name: /Add Tracking Event/i })).toBeDisabled();
      expect(screen.getByRole('button', { name: /Add Certification/i })).toBeDisabled();
      expect(screen.getByRole('button', { name: /Add Tracking Event/i })).toHaveClass('w-full');
      expect(screen.getByRole('button', { name: /Add Tracking Event/i })).toHaveClass('text-xs');
      expect(screen.getByRole('button', { name: /Add Tracking Event/i })).toHaveClass('sm:text-sm');
      expect(screen.getByRole('button', { name: /Add Tracking Event/i })).toHaveClass('sm:w-auto');
      expect(screen.getByRole('button', { name: /Add Certification/i })).toHaveClass('w-full');
      expect(screen.getByRole('button', { name: /Add Certification/i })).toHaveClass('text-xs');
      expect(screen.getByRole('button', { name: /Add Certification/i })).toHaveClass('sm:text-sm');
      expect(screen.getByText('Operator updates locked')).toBeInTheDocument();
      expect(
        screen.getByTestId('product-detail-actions').compareDocumentPosition(screen.getByText('Fresh organic apples'))
        & Node.DOCUMENT_POSITION_FOLLOWING,
      ).toBeTruthy();
      expect(screen.getByText('Registered')).toBeInTheDocument();
      expect(screen.getByTestId('timeline-block-number')).toHaveAttribute('title', 'Block 1');
      expect(screen.getByTestId('timeline-block-number')).toHaveClass('select-all');
      expect(screen.getByTestId('timeline-event-label')).toHaveAttribute('title', 'Registered');
      expect(screen.getByTestId('timeline-event-label')).toHaveClass('select-all');
      expect(screen.getByTestId('timeline-event-date')).toHaveTextContent(timelineLocalizedTimestamp);
      expect(screen.getByTestId('timeline-event-date')).toHaveAttribute('title', timelineLocalizedTimestamp);
      expect(screen.getByTestId('timeline-event-date')).toHaveClass('break-words');
      expect(screen.getByTestId('timeline-event-date')).toHaveClass('max-w-full');
      expect(screen.getByTestId('timeline-event-date')).toHaveClass('select-all');
      expect(screen.getByTestId('timeline-data-value-status')).toHaveTextContent('In Transit');
      expect(screen.queryByText('IN_TRANSIT')).not.toBeInTheDocument();
      expect(screen.getByTestId('timeline-data-value-timestamp')).toHaveTextContent(timelineLocalizedTimestamp);
      expect(document.body).not.toHaveTextContent('년');
      expect(screen.queryByText(timelineIsoTimestamp)).not.toBeInTheDocument();
      expect(screen.getByTestId('timeline-data-value-handler_id')).toHaveTextContent('HANDLER-VERY-LONG-1234567890');
      expect(screen.getByTestId('timeline-data-value-handler_id')).toHaveClass('break-all');
      expect(screen.getByTestId('timeline-data-value-handler_id')).not.toHaveClass('truncate');
      expect(screen.getByTestId('timeline-tx-hash')).toHaveTextContent('TX: 0x1234567890');
      expect(screen.getByTestId('timeline-tx-hash')).toHaveClass('break-all');
      expect(screen.getByTestId('timeline-tx-hash')).not.toHaveClass('truncate');
      expect(screen.getByTestId('timeline-tx-status')).toHaveTextContent('TX recorded');
      expect(screen.queryByText('Verify Link')).not.toBeInTheDocument();
    });
  });

  it('copies the product ID from the detail header', async () => {
    productApi.getById.mockResolvedValueOnce({ data: mockProduct });
    productApi.getHistory.mockResolvedValueOnce({ data: { history: mockHistory } });

    renderWithRouter(<ProductDetail />);

    const copyButton = await screen.findByRole('button', { name: /Copy product ID/i });
    fireEvent.click(copyButton);

    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith('1');
    });
    expect(screen.getByRole('button', { name: /Copied product ID/i })).toBeInTheDocument();
  });

  it('copies the public verify label from the QR card', async () => {
    productApi.getById.mockResolvedValueOnce({ data: mockProduct });
    productApi.getHistory.mockResolvedValueOnce({ data: { history: mockHistory } });

    renderWithRouter(<ProductDetail />);

    const copyButton = await screen.findByRole('button', { name: /Copy public verify label URL/i });
    fireEvent.click(copyButton);

    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith('QR-12345');
    });
    expect(screen.getByRole('button', { name: /Copied public verify label URL/i })).toBeInTheDocument();
  });

  it('renders a real explorer link when history includes one', async () => {
    productApi.getById.mockResolvedValueOnce({ data: mockProduct });
    productApi.getHistory.mockResolvedValueOnce({
      data: {
        history: [{
          ...mockHistory[0],
          explorer_url: 'https://sepolia.etherscan.io/tx/0x1234567890',
        }],
      },
    });

    renderWithRouter(<ProductDetail />);

    const explorerLink = await screen.findByRole('link', { name: /Verify link/i });

    expect(explorerLink).toHaveAttribute('href', 'https://sepolia.etherscan.io/tx/0x1234567890');
    expect(screen.queryByTestId('timeline-tx-status')).not.toBeInTheDocument();
  });

  it('shows the tracking form when an operator token is available', async () => {
    hasOperatorToken.mockReturnValue(true);
    productApi.getById.mockResolvedValueOnce({ data: mockProduct });
    productApi.getHistory.mockResolvedValueOnce({ data: { history: mockHistory } });

    renderWithRouter(<ProductDetail />);

    await waitFor(() => {
      expect(screen.getByText('Organic Apples')).toBeInTheDocument();
    });

    expect(screen.queryByPlaceholderText(/Location/i)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Add Tracking Event/i }));

    expect(screen.getByPlaceholderText(/Location/i)).toBeInTheDocument();
  });

  it('shows an inline auth notice when a protected tracking update is rejected', async () => {
    hasOperatorToken.mockReturnValue(true);
    productApi.getById.mockResolvedValueOnce({ data: mockProduct });
    productApi.getHistory.mockResolvedValueOnce({ data: { history: mockHistory } });
    productApi.addTracking.mockRejectedValueOnce({ response: { status: 401 } });

    renderWithRouter(<ProductDetail />);

    await waitFor(() => {
      expect(screen.getByText('Organic Apples')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /Add Tracking Event/i }));
    fireEvent.change(screen.getByPlaceholderText(/Location/i), {
      target: { value: 'Seoul Distribution Center' },
    });
    fireEvent.change(screen.getByPlaceholderText(/Handler ID/i), {
      target: { value: 'QA-1' },
    });
    fireEvent.click(screen.getByRole('button', { name: /^Add Event$/i }));

    await waitFor(() => {
      expect(screen.getByText('Operator authentication required to save chain updates.')).toBeInTheDocument();
    });
    expect(productApi.addTracking).toHaveBeenCalledWith('1', {
      status: 'IN_TRANSIT',
      location: 'Seoul Distribution Center',
      handler_id: 'QA-1',
    });
  });

  it('renders the not found fallback when product loading fails', async () => {
    productApi.getById.mockRejectedValueOnce(new Error('Not Found'));
    productApi.getHistory.mockRejectedValueOnce(new Error('Not Found'));

    renderWithRouter(<ProductDetail />);

    await waitFor(() => {
      expect(screen.getByText('Product Not Found')).toBeInTheDocument();
      expect(screen.getByText(/Back to Dashboard/i)).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /Add Tracking Event/i })).not.toBeInTheDocument();
    });
  });

  it('keeps the product visible when only history loading fails', async () => {
    productApi.getById.mockResolvedValueOnce({ data: mockProduct });
    productApi.getHistory.mockRejectedValueOnce(new Error('History unavailable'));

    renderWithRouter(<ProductDetail />);

    await waitFor(() => {
      expect(screen.getByText('Organic Apples')).toBeInTheDocument();
      expect(screen.queryByText('Product Not Found')).not.toBeInTheDocument();
    });
  });

  it('retries verification analytics until the event is captured', async () => {
    trackQrEvent.mockResolvedValueOnce(false).mockResolvedValueOnce(true);
    productApi.getById.mockResolvedValueOnce({ data: mockProduct });
    productApi.getHistory.mockResolvedValueOnce({ data: { history: mockHistory } });
    const originalSetTimeout = window.setTimeout.bind(window);
    const setTimeoutSpy = vi.spyOn(window, 'setTimeout').mockImplementation((callback, delay, ...args) => {
      if (delay === 3000 && typeof callback === 'function') {
        callback(...args);
        return 0;
      }
      return originalSetTimeout(callback, delay, ...args);
    });

    renderWithRouter(<ProductDetail />, {
      route: '/product/1?scan_source=qr_reader&scan_session=session-1&scan_variant=qr_page_v2',
    });

    await waitFor(() => {
      expect(screen.getByText('Organic Apples')).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(trackQrEvent).toHaveBeenCalledTimes(1);
    });

    expect(trackQrEvent).toHaveBeenCalledWith(
      expect.objectContaining({
        session_id: 'session-1',
        event_type: 'verification_complete',
        variant_id: 'qr_page_v2',
      }),
    );

    await waitFor(() => {
      expect(trackQrEvent).toHaveBeenCalledTimes(2);
    });

    setTimeoutSpy.mockRestore();
  });
});
