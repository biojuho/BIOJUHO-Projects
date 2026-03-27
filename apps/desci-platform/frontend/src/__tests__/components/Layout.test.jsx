/* global describe, it, expect, vi */
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

// framer-motion and ToastContext — provided by global setup.jsx

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({
    user: {
      email: 'researcher@desci.io',
      displayName: 'Dr. Researcher',
      photoURL: null,
    },
    logout: vi.fn(),
    walletAddress: null,
    connectWallet: vi.fn().mockResolvedValue({ success: true, address: '0xABCD' }),
  }),
}));

vi.mock('../../contexts/LocaleContext', async () => {
  const { LAYOUT_MESSAGES, createLocaleMock } = await import('../mocks/locale-messages.js');
  return createLocaleMock(LAYOUT_MESSAGES);
});

import Layout from '../../components/Layout';

function renderLayout(children = <div>Test Content</div>) {
  return render(
    <MemoryRouter initialEntries={['/dashboard']}>
      <Layout>{children}</Layout>
    </MemoryRouter>
  );
}

describe('Layout', () => {
  it('renders the DSCI logo text', () => {
    renderLayout();
    const logos = screen.getAllByText('DSCI');
    expect(logos.length).toBeGreaterThanOrEqual(1);
  });

  it('renders the marketplace subtitle', () => {
    renderLayout();
    expect(screen.getByText('The decentralized science marketplace')).toBeDefined();
  });

  it('renders all sidebar navigation links', () => {
    renderLayout();
    const navItems = [
      'Marketplace Overview',
      'Match Studio',
      'Research Submission',
      'Research Vault',
      'Funding Radar',
      'Investor View',
      'AI Workbench',
      'Peer Review',
      'Rewards Wallet',
      'Asset Library',
      'Governance Hub',
    ];
    navItems.forEach((name) => {
      expect(screen.getByText(name)).toBeDefined();
    });
  });

  it('renders navigation links with correct hrefs', () => {
    renderLayout();
    const dashboardLink = screen.getByText('Marketplace Overview').closest('a');
    expect(dashboardLink.getAttribute('href')).toBe('/dashboard');

    const biolinkerLink = screen.getByText('Match Studio').closest('a');
    expect(biolinkerLink.getAttribute('href')).toBe('/biolinker');

    const noticesLink = screen.getByText('Funding Radar').closest('a');
    expect(noticesLink.getAttribute('href')).toBe('/notices');

    const walletLink = screen.getByText('Rewards Wallet').closest('a');
    expect(walletLink.getAttribute('href')).toBe('/wallet');
  });

  it('renders the Sign Out button', () => {
    renderLayout();
    expect(screen.getByText('Sign out')).toBeDefined();
  });

  it('renders the user display name', () => {
    renderLayout();
    expect(screen.getByText('Dr. Researcher')).toBeDefined();
  });

  it('renders the user email', () => {
    renderLayout();
    expect(screen.getByText('researcher@desci.io')).toBeDefined();
  });

  it('renders the Connect Wallet button when no wallet is connected', () => {
    renderLayout();
    expect(screen.getByText('Connect wallet')).toBeDefined();
  });

  it('renders children content', () => {
    renderLayout(<div>My Custom Content</div>);
    expect(screen.getByText('My Custom Content')).toBeDefined();
  });

  it('renders the mobile menu toggle button', () => {
    renderLayout();
    const menuButton = screen.getByLabelText('Open menu');
    expect(menuButton).toBeDefined();
  });

  it('renders the footer content', () => {
    renderLayout();
    expect(screen.getAllByText(/Joolife/i).length).toBeGreaterThan(0);
  });
});
