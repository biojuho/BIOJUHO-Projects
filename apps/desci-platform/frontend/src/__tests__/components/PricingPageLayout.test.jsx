/* global describe, it, expect, vi */
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({
    user: null,
    walletAddress: null,
  }),
}));

vi.mock('../../contexts/LocaleContext', () => ({
  useLocale: () => ({
    locale: 'en',
    t: (key) => key,
  }),
}));

vi.mock('../../services/api', () => ({
  default: {
    get: vi.fn().mockResolvedValue({ data: {} }),
    post: vi.fn().mockResolvedValue({ data: {} }),
  },
}));

import PricingPage from '../../components/PricingPage';

describe('PricingPage layout', () => {
  it('keeps trust marker, billing toggle, and popular badge in normal layout flow', () => {
    render(<MemoryRouter><PricingPage /></MemoryRouter>);

    expect(screen.getByTestId('pricing-trust-marker-row')).toHaveStyle({ justifyContent: 'center' });
    expect(screen.getByTestId('pricing-billing-toggle')).toHaveStyle({ marginTop: '2rem' });
    expect(screen.getByTestId('pricing-popular-badge')).not.toHaveClass('absolute');
  });
});
