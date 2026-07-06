/* global describe, it, expect, vi, beforeEach, afterEach */
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import SupplyChain from './SupplyChain';
import { productApi } from '../services/api';

vi.mock('../services/api', () => ({
  productApi: {
    getPage: vi.fn(),
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
    const products = makeProducts(25);
    productApi.getPage.mockImplementation(({ page, pageSize, search = '' }) => {
      const normalizedSearch = search.toLowerCase();
      const filteredProducts = normalizedSearch
        ? products.filter(
            (product) =>
              product.id.toLowerCase().includes(normalizedSearch) ||
              product.name.toLowerCase().includes(normalizedSearch) ||
              product.origin.toLowerCase().includes(normalizedSearch)
          )
        : products;
      const start = (page - 1) * pageSize;
      const items = filteredProducts.slice(start, start + pageSize);
      return Promise.resolve({
        data: {
          items,
          total: filteredProducts.length,
          page,
          page_size: pageSize,
          total_pages: Math.max(1, Math.ceil(filteredProducts.length / pageSize)),
        },
      });
    });
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

    expect(screen.getByTestId('supply-chain-heading')).toHaveClass('text-2xl');
    expect(screen.getByTestId('supply-chain-heading')).toHaveClass('sm:text-3xl');
    expect(screen.getByLabelText(/Search products or locations/i)).toHaveAttribute('type', 'text');
    expect(screen.getByText('Product 1')).toBeInTheDocument();
    expect(screen.getByText('Product 20')).toBeInTheDocument();
    expect(screen.queryByText('Product 21')).not.toBeInTheDocument();
    expect(screen.getAllByTestId('supply-chain-product-info')[0]).toHaveClass('min-w-0');
    const productIds = screen.getAllByTestId('supply-chain-product-id');
    expect(productIds[0]).toHaveTextContent('ID: product-01');
    expect(productIds[0]).toHaveAttribute('title', 'product-01');
    expect(productIds[0]).toHaveClass('max-w-full');
    expect(productIds[0]).toHaveClass('truncate');
    expect(productIds[0]).not.toHaveClass('break-all');
    expect(screen.getByText('Page 1 / 2')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Next' }));

    await waitFor(() => {
      expect(screen.getByText('Showing 21-25 of 25 products')).toBeInTheDocument();
    });

    expect(screen.queryByText('Product 20')).not.toBeInTheDocument();
    expect(screen.getByText('Product 21')).toBeInTheDocument();
    expect(screen.getByText('Product 25')).toBeInTheDocument();
    expect(screen.getByText('Page 2 / 2')).toBeInTheDocument();
  });

  it('resets to the first server page when search changes', async () => {
    render(<SupplyChain />);

    await waitFor(() => {
      expect(screen.getByText('Showing 1-20 of 25 products')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Next' }));

    await waitFor(() => {
      expect(screen.getByText('Showing 21-25 of 25 products')).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText(/Search products or locations/i), {
      target: { value: 'product-01' },
    });

    await waitFor(() => {
      expect(screen.getByText('Showing 1-1 of 1 products')).toBeInTheDocument();
    });

    expect(screen.getByText('Product 1')).toBeInTheDocument();
    expect(screen.getByText('Page 1 / 1')).toBeInTheDocument();
    expect(productApi.getPage).toHaveBeenLastCalledWith({ page: 1, pageSize: 20, search: 'product-01' });

    fireEvent.click(screen.getByRole('button', { name: 'Clear supply chain search' }));

    await waitFor(() => {
      expect(screen.getByText('Showing 1-20 of 25 products')).toBeInTheDocument();
    });

    expect(screen.getByLabelText(/Search products or locations/i)).toHaveValue('');
    expect(productApi.getPage).toHaveBeenLastCalledWith({ page: 1, pageSize: 20, search: '' });
  });

  it('normalizes backend tracking labels before rendering current status', async () => {
    productApi.getPage.mockResolvedValueOnce({
      data: {
        items: [
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
        total: 1,
        page: 1,
        page_size: 20,
        total_pages: 1,
      },
    });

    render(<SupplyChain />);

    await waitFor(() => {
      expect(screen.getByText('Delivered & Available')).toBeInTheDocument();
    });

    expect(screen.queryByText('Unknown Status')).not.toBeInTheDocument();
  });
});
