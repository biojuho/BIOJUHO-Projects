/* global describe, it, expect, vi, beforeEach, afterEach */
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import SupplyChain from './SupplyChain';
import { productApi } from '../services/api';

vi.mock('../services/api', () => ({
  productApi: {
    getAll: vi.fn(),
  },
}));

const makeProducts = (count) =>
  Array.from({ length: count }, (_, index) => {
    const id = `product-${String(index + 1).padStart(2, '0')}`;
    return {
      id,
      name: `Product ${index + 1}`,
      origin: index % 2 === 0 ? 'Seoul Farm' : 'Busan Farm',
      tracking_history: [{ status: index % 3 === 0 ? 'IN_TRANSIT' : 'REGISTERED' }],
    };
  });

describe('SupplyChain', () => {
  beforeEach(() => {
    productApi.getAll.mockResolvedValue({ data: makeProducts(25) });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('paginates large product lists instead of rendering every card at once', async () => {
    render(<SupplyChain />);

    await waitFor(() => {
      expect(screen.getByText('Showing 1-20 of 25 products')).toBeInTheDocument();
    });

    expect(screen.getByText('Product 1')).toBeInTheDocument();
    expect(screen.getByText('Product 20')).toBeInTheDocument();
    expect(screen.queryByText('Product 21')).not.toBeInTheDocument();
    expect(screen.getByText('Page 1 / 2')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Next' }));

    expect(screen.getByText('Showing 21-25 of 25 products')).toBeInTheDocument();
    expect(screen.queryByText('Product 20')).not.toBeInTheDocument();
    expect(screen.getByText('Product 21')).toBeInTheDocument();
    expect(screen.getByText('Product 25')).toBeInTheDocument();
    expect(screen.getByText('Page 2 / 2')).toBeInTheDocument();
  });

  it('normalizes backend tracking labels before rendering current status', async () => {
    productApi.getAll.mockResolvedValueOnce({
      data: [
        {
          id: 'batch-verified',
          name: 'Verified Batch',
          origin: 'Seoul Farm',
          tracking_history: [
            { status: 'Delivered to Warehouse', timestamp: '2026-07-02T10:00:00Z' },
            { status: 'Quality Check Passed', timestamp: '2026-07-03T10:00:00Z' },
            { status: 'In Transit', timestamp: '2026-07-01T10:00:00Z' },
          ],
        },
      ],
    });

    render(<SupplyChain />);

    await waitFor(() => {
      expect(screen.getByText('Delivered & Available')).toBeInTheDocument();
    });

    expect(screen.queryByText('Unknown Status')).not.toBeInTheDocument();
  });
});
