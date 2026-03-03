import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

// Component-level mocks
vi.mock('framer-motion', () => ({
  motion: { div: (props) => <div {...props} /> },
  AnimatePresence: ({ children }) => <>{children}</>,
}));
vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({
    user: { email: 'test@desci.io', displayName: 'Researcher' },
    walletAddress: '0xABCD',
    logout: vi.fn(),
    connectWallet: vi.fn(),
  }),
}));
vi.mock('../../contexts/ToastContext', () => ({
  useToast: () => ({ showToast: vi.fn() }),
}));
vi.mock('../../services/api', () => ({
  default: {
    get: vi.fn().mockResolvedValue({ data: [] }),
    post: vi.fn().mockResolvedValue({ data: {} }),
  },
}));

// Components under test
import UploadPaper from '../../components/UploadPaper';
import AssetManager from '../../components/AssetManager';

describe('UploadPaper', () => {
  it('renders upload form with title input', () => {
    render(
      <MemoryRouter>
        <UploadPaper />
      </MemoryRouter>
    );
    expect(screen.getByPlaceholderText(/novel approach/i)).toBeDefined();
  });

  it('renders legal agreement checkbox', () => {
    render(
      <MemoryRouter>
        <UploadPaper />
      </MemoryRouter>
    );
    expect(screen.getByLabelText(/크리에이티브 커먼즈/i)).toBeDefined();
  });

  it('submit button is disabled without file and terms', () => {
    render(
      <MemoryRouter>
        <UploadPaper />
      </MemoryRouter>
    );
    const submitBtn = screen.getByRole('button', { name: /IPFS/i });
    expect(submitBtn.disabled).toBe(true);
  });
});

describe('AssetManager', () => {
  it('renders asset management heading', () => {
    render(
      <MemoryRouter>
        <AssetManager />
      </MemoryRouter>
    );
    expect(screen.getByText(/Asset Management/i)).toBeDefined();
  });

  it('renders file type selector', () => {
    render(
      <MemoryRouter>
        <AssetManager />
      </MemoryRouter>
    );
    expect(screen.getByText(/IR Deck/i)).toBeDefined();
  });
});
