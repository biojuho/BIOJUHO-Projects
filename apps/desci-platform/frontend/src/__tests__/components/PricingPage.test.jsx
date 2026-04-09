/* global describe, it, expect, vi, beforeEach */
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({
    user: { uid: 'user-123' },
  }),
}));

vi.mock('../../services/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

import PricingPage from '../../components/PricingPage';
import api from '../../services/api';

describe('PricingPage', () => {
  beforeEach(() => {
    api.get.mockReset();
    api.post.mockReset();
  });

  it('loads the current subscription tier through the shared api client', async () => {
    api.get.mockResolvedValue({ data: { tier: 'pro' } });

    render(<PricingPage />);

    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith('/subscription/tier');
    });
  });

  it('starts checkout through the shared api client', async () => {
    api.get.mockResolvedValue({ data: { tier: 'free' } });
    api.post.mockResolvedValue({ data: {} });

    render(<PricingPage />);

    const proCard = await screen.findByRole('heading', { name: 'Pro' });
    const proButton = proCard.closest('div').querySelector('button');

    fireEvent.click(proButton);

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/subscription/checkout', {
        tier: 'pro',
        billing: 'monthly',
      });
    });
  });
});
