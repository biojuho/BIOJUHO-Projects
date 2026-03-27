/* global describe, it, expect, vi */
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

// framer-motion and ToastContext — provided by global setup.jsx

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({
    user: { email: 'test@desci.io', displayName: 'Researcher' },
    walletAddress: '0xABCD',
    logout: vi.fn(),
    connectWallet: vi.fn(),
  }),
}));

vi.mock('../../contexts/LocaleContext', async () => {
  const { UPLOAD_MESSAGES, createLocaleMock } = await import('../mocks/locale-messages.js');
  return createLocaleMock(UPLOAD_MESSAGES);
});

vi.mock('../../services/api', () => ({
  default: {
    get: vi.fn().mockResolvedValue({ data: [] }),
    post: vi.fn().mockResolvedValue({ data: {} }),
  },
}));

import UploadPaper from '../../components/UploadPaper';
import AssetManager from '../../components/AssetManager';

describe('UploadPaper', () => {
  it('renders upload form with title input', () => {
    render(
      <MemoryRouter>
        <UploadPaper />
      </MemoryRouter>,
    );
    expect(screen.getByPlaceholderText(/novel approach/i)).toBeDefined();
  });

  it('renders legal agreement checkbox', () => {
    render(
      <MemoryRouter>
        <UploadPaper />
      </MemoryRouter>,
    );
    expect(screen.getByLabelText(/Creative Commons/i)).toBeDefined();
  });

  it('submit button is disabled without file and terms', () => {
    render(
      <MemoryRouter>
        <UploadPaper />
      </MemoryRouter>,
    );
    const submitButton = screen.getByRole('button', { name: /Store on IPFS/i });
    expect(submitButton.disabled).toBe(true);
  });
});

describe('AssetManager', () => {
  it('renders asset management heading', () => {
    render(
      <MemoryRouter>
        <AssetManager />
      </MemoryRouter>,
    );
    expect(screen.getByText(/Asset Library/i)).toBeDefined();
  });

  it('renders file type selector', () => {
    render(
      <MemoryRouter>
        <AssetManager />
      </MemoryRouter>,
    );
    expect(screen.getByText(/IR Deck/i)).toBeDefined();
  });
});
