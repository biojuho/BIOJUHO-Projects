/* global describe, it, expect, vi */
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

// framer-motion, ToastContext, jest-dom matchers — provided by global setup.jsx

const localeState = { prefix: '' };

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({
    user: { email: 'alice@desci.io', displayName: 'Alice Researcher', uid: 'uid-abc12345', providerData: [{ providerId: 'google.com' }] },
    walletAddress: '0x1234567890abcdef1234567890abcdef12345678',
    logout: vi.fn(),
    connectWallet: vi.fn(),
  }),
}));

vi.mock('../../contexts/LocaleContext', async () => {
  const { DASHBOARD_MESSAGES } = await import('../mocks/locale-messages.js');

  const translate = (key, values = {}) => {
    const entry = DASHBOARD_MESSAGES[key] ?? key;
    const text = typeof entry === 'string'
      ? entry.replace(/\{(\w+)\}/g, (_, token) => String(values[token] ?? ''))
      : String(entry);
    return localeState.prefix ? `${localeState.prefix}:${text}` : text;
  };

  return {
    useLocale: () => ({
      locale: 'en',
      setLocale: vi.fn(),
      t: translate,
    }),
  };
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
import api from '../../services/api';

async function renderDashboard() {
  const rendered = render(
    <MemoryRouter initialEntries={['/dashboard']}>
      <Dashboard />
    </MemoryRouter>
  );
  await waitFor(() => {
    expect(api.get.mock.calls.length).toBeGreaterThanOrEqual(4);
  });
  return rendered;
}

describe('Dashboard', () => {
  it('does not refetch dashboard data when translations change', async () => {
    localeState.prefix = '';
    const rendered = await renderDashboard();

    expect(api.get).toHaveBeenCalledTimes(4);

    localeState.prefix = 'ko';
    rendered.rerender(
      <MemoryRouter initialEntries={['/dashboard']}>
        <Dashboard />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(api.get).toHaveBeenCalledTimes(4);
    });
  });

  it('renders the welcome heading with user first name', async () => {
    localeState.prefix = '';
    await renderDashboard();
    const heading = screen.getByRole('heading', { level: 1 });
    expect(heading.textContent).toMatch(/Welcome back/i);
    expect(heading.textContent).toMatch(/Alice/i);
  });

  it('renders all four KPI stat cards', async () => {
    localeState.prefix = '';
    await renderDashboard();
    expect(screen.getByText('Papers Uploaded')).toBeDefined();
    expect(screen.getByText('Vector Index')).toBeDefined();
    expect(screen.getByText('Pending Reviews')).toBeDefined();
    expect(screen.getByText('DSCI Balance')).toBeDefined();
  });

  it('renders the Account Status section', async () => {
    localeState.prefix = '';
    await renderDashboard();
    expect(screen.getByText('Account Status')).toBeDefined();
  });

  it('displays the user email in identity section', async () => {
    localeState.prefix = '';
    await renderDashboard();
    expect(screen.getByText('alice@desci.io')).toBeDefined();
  });

  it('renders Quick Actions links', async () => {
    localeState.prefix = '';
    await renderDashboard();
    expect(screen.getByText('Submit new research')).toBeDefined();
    expect(screen.getByText('Open Funding Radar')).toBeDefined();
    expect(screen.getByText('Open Investor View')).toBeDefined();
    expect(screen.getByText('Run Match Studio')).toBeDefined();
  });

  it('renders the Quick Actions links with correct hrefs', async () => {
    localeState.prefix = '';
    await renderDashboard();
    const uploadLink = screen.getByText('Submit new research').closest('a');
    expect(uploadLink).toBeDefined();
    expect(uploadLink.getAttribute('href')).toBe('/upload');

    const grantsLink = screen.getByText('Open Funding Radar').closest('a');
    expect(grantsLink.getAttribute('href')).toBe('/notices');

    const matchLink = screen.getByText('Run Match Studio').closest('a');
    expect(matchLink.getAttribute('href')).toBe('/biolinker');
  });

  it('renders the VC Match section with child component', async () => {
    localeState.prefix = '';
    await renderDashboard();
    expect(screen.getByText('Strategic Investor Matches')).toBeDefined();
    expect(screen.getByTestId('vc-match-list')).toBeDefined();
  });

  it('displays the Network Active badge', async () => {
    localeState.prefix = '';
    await renderDashboard();
    expect(screen.getByText('Network Active')).toBeDefined();
  });
});
