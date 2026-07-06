/* global describe, it, expect, vi, beforeEach, afterEach */
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import QRTokenManager from './QRTokenManager';
import {
  qrTokenAdminApi,
  getOperatorToken,
  setOperatorToken,
} from '../services/api';

vi.mock('../services/api', () => ({
  getOperatorToken: vi.fn(),
  setOperatorToken: vi.fn(),
  qrTokenAdminApi: {
    listByProduct: vi.fn(),
    reissue: vi.fn(),
    revoke: vi.fn(),
  },
}));

const tokenListResponse = {
  status: 'success',
  product_id: 'product-qr-1',
  items: [
    {
      id: 'token-active-1',
      product_id: 'product-qr-1',
      token_prefix: 'tok_active',
      batch_code: 'LOT-A',
      issued_at: '2026-06-01T00:00:00Z',
      expires_at: '2026-07-01T00:00:00Z',
      revoked_at: null,
      last_verified_at: '2026-06-02T03:04:00Z',
      scan_count: 12,
      is_active: true,
      status: 'active',
    },
    {
      id: 'token-revoked-1',
      product_id: 'product-qr-1',
      token_prefix: 'tok_revok',
      batch_code: 'LOT-R',
      issued_at: '2026-05-01T00:00:00Z',
      expires_at: '2026-06-01T00:00:00Z',
      revoked_at: '2026-05-15T00:00:00Z',
      last_verified_at: null,
      scan_count: 3,
      is_active: false,
      status: 'revoked',
    },
  ],
  total: 2,
  active_count: 1,
  revoked_count: 1,
  expired_count: 0,
  page: 1,
  page_size: 20,
  total_pages: 1,
};

describe('QRTokenManager', () => {
  beforeEach(() => {
    window.HTMLElement.prototype.scrollIntoView = vi.fn();
    getOperatorToken.mockReturnValue('operator-token');
    qrTokenAdminApi.listByProduct.mockResolvedValue({ data: tokenListResponse });
    qrTokenAdminApi.reissue.mockResolvedValue({
      data: {
        status: 'success',
        product_id: 'product-qr-1',
        qr_code: 'https://verify.agriguard.test/verify/new-public-token',
        token: 'new-public-token',
        token_summary: {
          id: 'token-new-1',
          token_prefix: 'new-public',
          status: 'active',
          is_active: true,
        },
        revoked_token_ids: ['token-active-1'],
      },
    });
    qrTokenAdminApi.revoke.mockResolvedValue({ data: { status: 'success' } });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('loads product QR tokens and renders redacted state summaries', async () => {
    render(<QRTokenManager />);

    expect(screen.getByTestId('qr-token-heading')).toHaveClass('text-2xl');
    expect(screen.getByTestId('qr-token-heading')).toHaveClass('sm:text-3xl');

    fireEvent.change(screen.getByLabelText('Product ID'), { target: { value: 'product-qr-1' } });
    fireEvent.click(screen.getByRole('button', { name: /load tokens/i }));

    await waitFor(() => {
      expect(screen.getByText('tok_active')).toBeInTheDocument();
    });

    expect(qrTokenAdminApi.listByProduct).toHaveBeenCalledWith('product-qr-1', {
      tokenStatus: 'all',
      page: 1,
      pageSize: 20,
    });
    expect(screen.getAllByText('Active').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Revoked').length).toBeGreaterThan(0);
    expect(screen.getByText('Showing 2 of 2 matching tokens for product-qr-1')).toBeInTheDocument();
    expect(screen.queryByText('new-public-token')).not.toBeInTheDocument();
  });

  it('renders QR token rows as mobile-first action cards', async () => {
    render(<QRTokenManager />);

    fireEvent.change(screen.getByLabelText('Product ID'), { target: { value: 'product-qr-1' } });
    fireEvent.click(screen.getByRole('button', { name: /load tokens/i }));

    await screen.findByText('tok_active');

    const table = screen.getByTestId('qr-token-table');
    expect(table).not.toHaveClass('min-w-[760px]');
    expect(table).toHaveClass('md:min-w-[760px]');

    const rows = screen.getAllByTestId('qr-token-row');
    expect(rows[0]).toHaveClass('block');
    expect(rows[0]).toHaveClass('md:table-row');
    expect(within(rows[0]).getByText('Action')).toBeInTheDocument();
    expect(within(rows[0]).getByRole('button', { name: /revoke/i })).toBeInTheDocument();
  });

  it('keeps the mobile QR token controls compact above the token workspace', () => {
    render(<QRTokenManager />);

    const operatorTokenInput = screen.getByLabelText('Operator bearer token');
    const tokenControls = operatorTokenInput.parentElement;
    expect(screen.getByTestId('qr-token-operator-token-card')).toHaveClass('w-full');
    expect(operatorTokenInput).toHaveAttribute('autocomplete', 'off');
    expect(operatorTokenInput).toHaveAttribute('spellcheck', 'false');
    expect(tokenControls).toHaveClass('grid');
    expect(tokenControls).toHaveClass('grid-cols-[minmax(0,1fr)_5rem]');

    const filterForm = screen.getByTestId('qr-token-filter-panel').querySelector('form');
    expect(filterForm).toHaveClass('grid-cols-2');
    expect(screen.getByLabelText('Product ID').parentElement).toHaveClass('col-span-2');
    expect(screen.getByLabelText('Product ID').parentElement).toHaveClass('lg:col-span-1');
    expect(screen.getByRole('button', { name: /load tokens/i })).toHaveClass('min-h-10');
  });

  it('saves an operator token for API calls', () => {
    getOperatorToken.mockReturnValue('');

    render(<QRTokenManager />);

    expect(screen.getByText('No token saved. Protected actions will return 401.')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Operator bearer token'), { target: { value: 'saved-token' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    expect(setOperatorToken).toHaveBeenCalledWith('saved-token');
    expect(screen.getByText('Operator token saved for this browser.')).toBeInTheDocument();
    expect(screen.getByText('A token is saved locally for operator API calls.')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /clear token/i }));

    expect(setOperatorToken).toHaveBeenLastCalledWith('');
    expect(screen.getByLabelText('Operator bearer token')).toHaveValue('');
    expect(screen.getByText('Operator token cleared.')).toBeInTheDocument();
    expect(screen.getByText('No token saved. Protected actions will return 401.')).toBeInTheDocument();
  });

  it('requires inline confirmation before revoking an active token', async () => {
    render(<QRTokenManager />);

    fireEvent.change(screen.getByLabelText('Product ID'), { target: { value: 'product-qr-1' } });
    fireEvent.click(screen.getByRole('button', { name: /load tokens/i }));

    await screen.findByText('tok_active');
    fireEvent.click(screen.getAllByRole('button', { name: 'Revoke' })[0]);

    expect(screen.getByText('Confirm token revocation')).toBeInTheDocument();
    expect(qrTokenAdminApi.revoke).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: /confirm/i }));

    await waitFor(() => {
      expect(qrTokenAdminApi.revoke).toHaveBeenCalledWith('token-active-1');
    });
    expect(screen.getByText('Token tok_active revoked.')).toBeInTheDocument();
  });

  it('confirms reissue and shows the one-time QR label URL', async () => {
    render(<QRTokenManager />);

    fireEvent.change(screen.getByLabelText('Product ID'), { target: { value: 'product-qr-1' } });
    fireEvent.click(screen.getByRole('button', { name: /load tokens/i }));

    await screen.findByText('tok_active');
    fireEvent.click(screen.getByRole('button', { name: /reissue label/i }));
    fireEvent.click(screen.getByRole('button', { name: /confirm/i }));

    await waitFor(() => {
      expect(qrTokenAdminApi.reissue).toHaveBeenCalledWith('product-qr-1', { revokeExisting: true });
    });
    expect(screen.getByText('New label URL ready')).toBeInTheDocument();
    expect(screen.getByText('https://verify.agriguard.test/verify/new-public-token')).toBeInTheDocument();
    expect(screen.getByTestId('qr-token-reissue-url')).toHaveClass('overflow-x-auto');
    expect(screen.getByTestId('qr-token-reissue-url')).toHaveClass('whitespace-nowrap');
    expect(screen.getByTestId('qr-token-reissue-result')).toHaveClass('scroll-mt-24');
    await waitFor(() => {
      expect(window.HTMLElement.prototype.scrollIntoView).toHaveBeenCalledWith({ block: 'start', behavior: 'auto' });
    });
  });

  it('announces load errors through the status region', async () => {
    qrTokenAdminApi.listByProduct.mockRejectedValue({
      response: { data: { detail: 'QR token administration requires an operator role.' } },
    });

    render(<QRTokenManager />);

    fireEvent.change(screen.getByLabelText('Product ID'), { target: { value: 'product-qr-1' } });
    fireEvent.click(screen.getByRole('button', { name: /load tokens/i }));

    expect(await screen.findByRole('status')).toHaveTextContent('QR token administration requires an operator role.');
  });
});
