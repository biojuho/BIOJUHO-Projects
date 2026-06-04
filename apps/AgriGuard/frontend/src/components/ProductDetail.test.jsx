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
  qr_code: 'QR-12345',
  requires_cold_chain: true,
  description: 'Fresh organic apples',
};

const mockHistory = [
  {
    block: 1,
    data: { action: 'REGISTERED', location: 'Farm' },
    timestamp: new Date().toISOString(),
    tx_hash: '0x1234567890',
  },
];

describe('ProductDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks();
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
      expect(screen.getByText('Seoul Farm')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Add Tracking Event/i })).toBeDisabled();
      expect(screen.getByRole('button', { name: /Add Certification/i })).toBeDisabled();
      expect(screen.getByText('Operator updates locked')).toBeInTheDocument();
    });
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
