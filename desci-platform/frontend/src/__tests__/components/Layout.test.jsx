import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

// Mocks must come before component imports
vi.mock('framer-motion', () => ({
  motion: {
    div: ({ children, ...props }) => {
      const {
        variants, initial, animate, exit, transition,
        whileHover, whileTap, layoutId, ...rest
      } = props;
      return <div {...rest}>{children}</div>;
    },
  },
  AnimatePresence: ({ children }) => <>{children}</>,
}));

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

vi.mock('../../contexts/ToastContext', () => ({
  useToast: () => ({ showToast: vi.fn() }),
}));

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
    // The desktop logo renders "DSCI" as an h1
    const logos = screen.getAllByText('DSCI');
    expect(logos.length).toBeGreaterThanOrEqual(1);
  });

  it('renders the DecentBio subtitle', () => {
    renderLayout();
    expect(screen.getByText('DecentBio')).toBeDefined();
  });

  it('renders all sidebar navigation links', () => {
    renderLayout();
    const navItems = [
      'Dashboard',
      'BioLinker',
      'Paper Upload',
      'My Lab',
      'Notices',
      'VC Portal',
      'AI Lab',
      'Peer Review',
      'Wallet',
    ];
    navItems.forEach((name) => {
      expect(screen.getByText(name)).toBeDefined();
    });
  });

  it('renders navigation links with correct hrefs', () => {
    renderLayout();
    const dashboardLink = screen.getByText('Dashboard').closest('a');
    expect(dashboardLink.getAttribute('href')).toBe('/dashboard');

    const biolinkerLink = screen.getByText('BioLinker').closest('a');
    expect(biolinkerLink.getAttribute('href')).toBe('/biolinker');

    const noticesLink = screen.getByText('Notices').closest('a');
    expect(noticesLink.getAttribute('href')).toBe('/notices');

    const walletLink = screen.getByText('Wallet').closest('a');
    expect(walletLink.getAttribute('href')).toBe('/wallet');
  });

  it('renders the Sign Out button', () => {
    renderLayout();
    expect(screen.getByText('Sign Out')).toBeDefined();
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
    expect(screen.getByText('Connect Wallet')).toBeDefined();
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
    // Footer renders company info
    expect(screen.getByText(/Joolife/i)).toBeDefined();
  });
});
