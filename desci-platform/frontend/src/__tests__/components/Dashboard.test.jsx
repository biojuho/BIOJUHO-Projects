import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

// Mocks must come before component imports
vi.mock('framer-motion', () => ({
  motion: {
    div: ({ children, ...props }) => {
      // Strip framer-motion-specific props to avoid React warnings
      const {
        variants: _variants,
        initial: _initial,
        animate: _animate,
        exit: _exit,
        transition: _transition,
        whileHover: _whileHover,
        whileTap: _whileTap,
        layoutId: _layoutId,
        ...rest
      } = props;
      return <div {...rest}>{children}</div>;
    },
  },
  AnimatePresence: ({ children }) => <>{children}</>,
}));

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({
    user: { email: 'alice@desci.io', displayName: 'Alice Researcher', uid: 'uid-abc12345', providerData: [{ providerId: 'google.com' }] },
    walletAddress: '0x1234567890abcdef1234567890abcdef12345678',
    logout: vi.fn(),
    connectWallet: vi.fn(),
  }),
}));

vi.mock('../../contexts/ToastContext', () => ({
  useToast: () => ({ showToast: vi.fn() }),
}));

vi.mock('../../contexts/LocaleContext', () => ({
  useLocale: () => ({
    t: (key, values = {}) => {
      const messages = {
        'dashboard.overview': 'Overview',
        'dashboard.welcomeBack': 'Welcome back',
        'dashboard.researcherFallback': 'Researcher',
        'dashboard.networkActive': 'Network Active',
        'dashboard.papersUploaded': 'Papers Uploaded',
        'dashboard.vectorIndex': 'Vector Index',
        'dashboard.pendingReviews': 'Pending Reviews',
        'dashboard.tokenBalance': 'Token Balance',
        'dashboard.statLoading': 'Loading',
        'dashboard.statDocuments': 'Documents',
        'dashboard.statComingSoon': 'Coming soon',
        'dashboard.statIndexed': `${values.count} indexed`,
        'dashboard.statUploadToStart': 'Upload to start',
        'dashboard.accountStatus': 'Account Status',
        'dashboard.identity': 'Identity',
        'dashboard.email': 'Email',
        'dashboard.provider': 'Provider',
        'dashboard.uid': 'UID',
        'dashboard.systemStatus': 'System Status',
        'dashboard.backendConnectionFailed': 'Backend connection failed',
        'dashboard.node': 'Node',
        'dashboard.online': 'Online',
        'dashboard.role': 'Role',
        'dashboard.rolePrincipalInvestigator': 'Principal Investigator',
        'dashboard.sync': 'Sync',
        'dashboard.automated': 'Automated',
        'dashboard.quickActions': 'Quick Actions',
        'dashboard.quickUploadTitle': 'Upload Paper',
        'dashboard.quickUploadSubtitle': 'Mint IP-NFT',
        'dashboard.quickGrantTitle': 'Find Grants',
        'dashboard.quickGrantSubtitle': 'AI Matching',
        'dashboard.quickVcTitle': 'VC Portal',
        'dashboard.quickVcSubtitle': 'Strategic Partners',
        'dashboard.strategicPartners': 'Strategic VC Partners',
        'dashboard.beta': 'Beta',
      };
      return messages[key] || key;
    },
  }),
}));

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
    expect(screen.getByText(/Welcome back/i)).toBeDefined();
    expect(screen.getByText(/Alice/i)).toBeDefined();
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
