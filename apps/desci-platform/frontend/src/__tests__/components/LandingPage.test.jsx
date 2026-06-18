/* global describe, it, expect, vi */
import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../../contexts/LocaleContext', () => ({
  useLocale: () => ({ locale: 'en-US' }),
}));

vi.mock('../../components/ui/LocaleToggle', () => ({
  default: () => <button type="button">Locale</button>,
}));

vi.mock('framer-motion', async () => {
  const actual = await vi.importActual('framer-motion');
  return {
    ...actual,
    useInView: () => true,
  };
});

import LandingPage from '../../components/LandingPage';

function renderLanding() {
  return render(
    <MemoryRouter initialEntries={['/']}>
      <LandingPage />
    </MemoryRouter>,
  );
}

describe('LandingPage', () => {
  it('renders the hero copy and primary CTAs', () => {
    renderLanding();
    expect(screen.getByText(/Where researchers and capital/i)).toBeDefined();
    expect(screen.getByText(/meet on one surface/i)).toBeDefined();
    expect(screen.getByText(/Start as Researcher/i)).toBeDefined();
    expect(screen.getByText(/Explore Research/i)).toBeDefined();
  });

  it('points the Get started CTA at the login route', () => {
    renderLanding();
    const cta = screen.getByText(/Get started free/i).closest('a');
    expect(cta).toBeDefined();
    expect(cta.getAttribute('href')).toBe('/login?next=/dashboard');
  });

  it('points the Explore CTA at the public research feed', () => {
    renderLanding();
    const cta = screen.getByText(/Explore Research/i).closest('a');
    expect(cta.getAttribute('href')).toBe('/explore');
  });

  it('renders all four headline stat labels', () => {
    renderLanding();
    expect(screen.getByText(/Papers Indexed/i)).toBeDefined();
    expect(screen.getByText(/Partner VCs/i)).toBeDefined();
    expect(screen.getByText(/Grants Tracked/i)).toBeDefined();
    expect(screen.getByText(/DSCI Rewarded/i)).toBeDefined();
  });

  it('renders the AI Matching Engine feature card', () => {
    const { container } = renderLanding();
    expect(within(container).getByText('AI Matching Engine')).toBeDefined();
  });
});
