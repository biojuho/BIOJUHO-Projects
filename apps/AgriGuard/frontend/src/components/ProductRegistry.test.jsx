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

    fireEvent.change(screen.getByPlaceholderText('e.g. Organic Tomatoes'), {
      target: { value: 'Organic Tomatoes' },
    });
    fireEvent.change(screen.getByPlaceholderText('e.g. farmer-001'), {
      target: { value: 'farmer-001' },
    });
    fireEvent.click(screen.getByRole('button', { name: /register harvest/i }));

    await waitFor(() => {
      expect(productApi.create).toHaveBeenCalledWith(
        expect.objectContaining({
          name: 'Organic Tomatoes',
          owner_id: 'farmer-001',
          harvest_date: null,
        }),
      );
    });

    expect(await screen.findByText('Registration Successful!')).toBeInTheDocument();
    expect(screen.getByText('batch-1')).toBeInTheDocument();
    expect(screen.getByText('Public verify label')).toBeInTheDocument();
    expect(screen.getByText('https://verify.agriguard.test/verify/public-token-1')).toBeInTheDocument();
    expect(screen.queryByText(/^TX:/)).not.toBeInTheDocument();
  });
});
