/* global describe, it, expect, vi */
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

// framer-motion, ToastContext, jest-dom matchers — provided by global setup.jsx

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({
    user: { email: 'alice@desci.io', displayName: 'Alice Researcher', uid: 'uid-abc12345', providerData: [{ providerId: 'google.com' }] },
    walletAddress: '0x1234567890abcdef1234567890abcdef12345678',
    logout: vi.fn(),
    connectWallet: vi.fn(),
  }),
}));

vi.mock('../../contexts/LocaleContext', async () => {
  const { DASHBOARD_MESSAGES, createLocaleMock } = await import('../mocks/locale-messages.js');
  return createLocaleMock(DASHBOARD_MESSAGES);
});

vi.mock('../../services/api', () => ({
  default: {
    get: vi.fn().mockResolvedValue({ data: [] }),
    post: vi.fn().mockResolvedValue({ data: {} }),
  },
}));

// Mock child components to isolate Dashboard unit tests
vi.mock('../../components/dashboard/RecommendationList', () => ({
  default: () => <div data-testid="recommendation-list">RecommendationList</div>,
}));

vi.mock('../../components/dashboard/VCMatchList', () => ({
  default: () => <div data-testid="vc-match-list">VCMatchList</div>,
}));

import Dashboard from '../../components/Dashboard';

function renderDashboard() {
  return render(
    <MemoryRouter initialEntries={['/dashboard']}>
      <Dashboard />
    </MemoryRouter>
  );
}

describe('Dashboard', () => {
  it('renders the welcome heading with user first name', () => {
    renderDashboard();
    const heading = screen.getByRole('heading', { level: 1 });
    expect(heading.textContent).toMatch(/Welcome back/i);
    expect(heading.textContent).toMatch(/Alice/i);
  });

  it('renders all four KPI stat cards', () => {
    renderDashboard();
    expect(screen.getByText('Papers Uploaded')).toBeDefined();
    expect(screen.getByText('Vector Index')).toBeDefined();
    expect(screen.getByText('Pending Reviews')).toBeDefined();
    expect(screen.getByText('Token Balance')).toBeDefined();
  });

  it('renders the Account Status section', () => {
    renderDashboard();
    expect(screen.getByText('Account Status')).toBeDefined();
  });

  it('displays the user email in identity section', () => {
    renderDashboard();
    expect(screen.getByText('alice@desci.io')).toBeDefined();
  });

  it('renders Quick Actions links', () => {
    renderDashboard();
    expect(screen.getByText('Upload Paper')).toBeDefined();
    expect(screen.getByText('Find Grants')).toBeDefined();
    expect(screen.getByText('VC Portal')).toBeDefined();
  });

  it('renders the Quick Actions links with correct hrefs', () => {
    renderDashboard();
    const uploadLink = screen.getByText('Upload Paper').closest('a');
    expect(uploadLink).toBeDefined();
    expect(uploadLink.getAttribute('href')).toBe('/upload');

    const grantsLink = screen.getByText('Find Grants').closest('a');
    expect(grantsLink.getAttribute('href')).toBe('/biolinker');
  });

  it('renders the VC Match section with child component', () => {
    renderDashboard();
    expect(screen.getByText('Strategic VC Partners')).toBeDefined();
    expect(screen.getByTestId('vc-match-list')).toBeDefined();
  });

  it('displays the Network Active badge', () => {
    renderDashboard();
    expect(screen.getByText('Network Active')).toBeDefined();
  });
});
