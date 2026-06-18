/* global describe, it, expect, vi, beforeEach */
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({
    user: { uid: 'user-123' },
  }),
}));

vi.mock('../../contexts/LocaleContext', async () => {
  const { createLocaleMock } = await import('../mocks/locale-messages.js');
  return createLocaleMock({
    'locale.switchLabel': 'Switch language',
    'locale.shortKo': 'KO',
    'locale.shortEn': 'EN',
  });
});

vi.mock('../../services/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

import PricingPage from '../../components/PricingPage';
import api from '../../services/api';

function renderPricingPage() {
  return render(
    <MemoryRouter initialEntries={['/pricing']}>
      <PricingPage />
    </MemoryRouter>
  );
}

describe('PricingPage', () => {
  beforeEach(() => {
    api.get.mockReset();
    api.post.mockReset();
  });

  it('loads the current subscription tier through the shared api client', async () => {
    api.get.mockResolvedValue({ data: { tier: 'pro' } });

    renderPricingPage();

    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith('/subscription/tier');
    });
  });

  it('starts checkout through the shared api client', async () => {
    api.get.mockResolvedValue({ data: { tier: 'free' } });
    api.post.mockResolvedValue({ data: {} });

    renderPricingPage();

    await screen.findByRole('heading', { name: 'Pro' });
    const proButton = screen.getByRole('button', { name: 'Upgrade to Pro' });

    fireEvent.click(proButton);

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith(
        '/subscription/checkout',
        { tier: 'pro', billing: 'monthly' },
        { suppressErrorLog: true },
      );
    });
  });
});
