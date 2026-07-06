import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import ProductRegistry from './ProductRegistry';
import { productApi } from '../services/api';

vi.mock('../services/api', () => ({
  productApi: {
    create: vi.fn(),
  },
}));

describe('ProductRegistry', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
      configurable: true,
    });
    productApi.create.mockResolvedValue({
      data: {
        id: 'batch-1',
        qr_code: 'https://verify.agriguard.test/verify/public-token-1',
      },
    });
  });

  afterEach(() => {
    cleanup();
  });

  it('shows the issued public verify label after registration', async () => {
    render(<ProductRegistry />);

    expect(screen.getByTestId('registry-page')).toHaveClass('space-y-4');
    expect(screen.getByTestId('registry-page')).toHaveClass('sm:space-y-8');
    expect(screen.getByTestId('registry-card-content')).toHaveClass('p-3');
    expect(screen.getByTestId('registry-card-content')).toHaveClass('sm:p-8');
    expect(screen.getByTestId('registry-product-origin-grid')).toHaveClass('grid-cols-1');
    expect(screen.getByTestId('registry-product-origin-grid')).toHaveClass('sm:grid-cols-2');
    expect(screen.getByTestId('registry-product-origin-grid')).toHaveClass('gap-4');
    expect(screen.getByTestId('registry-harvest-chain-grid')).toHaveClass('grid-cols-1');
    expect(screen.getByTestId('registry-harvest-chain-grid')).toHaveClass('gap-4');
    expect(screen.getByTestId('registry-cold-chain-control')).toHaveClass('sm:mt-8');
    expect(screen.getByLabelText('Requires Cold Chain')).toHaveClass('absolute');
    expect(screen.getByLabelText('Requires Cold Chain')).toHaveClass('opacity-0');
    expect(screen.getByTestId('registry-cold-chain-checkbox')).toHaveClass('peer-checked:bg-primary');
    expect(screen.getByTestId('registry-cold-chain-checkbox')).toHaveClass('pointer-events-none');
    expect(screen.getByTestId('registry-cold-chain-checkbox')).toHaveClass('border-primary');
    expect(screen.getByTestId('registry-cold-chain-checkbox')).toHaveClass('bg-primary/10');
    expect(screen.getByText('Requires Cold Chain')).toHaveClass('whitespace-nowrap');
    expect(screen.getByLabelText('Description')).toHaveClass('h-16');
    expect(screen.getByLabelText('Description')).toHaveClass('min-h-11');
    expect(screen.getByLabelText('Description')).toHaveClass('sm:h-32');

    fireEvent.change(screen.getByLabelText('Crop Name'), {
      target: { value: 'Organic Tomatoes' },
    });
    fireEvent.change(screen.getByLabelText(/Owner ID/), {
      target: { value: 'farmer-001' },
    });
    fireEvent.click(screen.getByLabelText('Requires Cold Chain'));
    fireEvent.click(screen.getByRole('button', { name: /register harvest/i }));

    await waitFor(() => {
      expect(productApi.create).toHaveBeenCalledWith(
        expect.objectContaining({
          name: 'Organic Tomatoes',
          owner_id: 'farmer-001',
          requires_cold_chain: true,
          harvest_date: null,
        }),
      );
    });

    expect(await screen.findByText('Registration Successful!')).toBeInTheDocument();
    expect(screen.getByText('batch-1')).toBeInTheDocument();
    const batchId = screen.getByTestId('registry-success-batch-id');
    expect(batchId).toHaveAttribute('title', 'batch-1');
    expect(batchId).toHaveClass('truncate');
    expect(batchId).toHaveClass('max-w-full');
    expect(screen.getByText('Public verify label')).toBeInTheDocument();
    expect(screen.getByText('https://verify.agriguard.test/verify/public-token-1')).toBeInTheDocument();
    expect(screen.getByTestId('registry-success-content')).toHaveClass('min-w-0');
    expect(screen.getByTestId('registry-success-content')).toHaveClass('flex-1');
    const labelUrl = screen.getByTestId('registry-label-url');
    expect(labelUrl).toHaveAttribute('title', 'https://verify.agriguard.test/verify/public-token-1');
    expect(labelUrl).toHaveClass('overflow-x-auto');
    expect(labelUrl).toHaveClass('whitespace-nowrap');
    expect(labelUrl).not.toHaveClass('break-all');
    expect(screen.getByRole('button', { name: /Copy public verify label URL/i })).toHaveClass('min-h-11');
    fireEvent.click(screen.getByRole('button', { name: /Copy public verify label URL/i }));
    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith('https://verify.agriguard.test/verify/public-token-1');
    });
    expect(screen.getByRole('button', { name: /Copied public verify label URL/i })).toBeInTheDocument();
    expect(screen.queryByText(/^TX:/)).not.toBeInTheDocument();
  });
});
