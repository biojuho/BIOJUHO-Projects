import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

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

vi.mock('../../contexts/LocaleContext', () => ({
  useLocale: () => ({
    t: (key, values = {}) => {
      const messages = {
        'uploadPaper.statusPreparing': 'Upload processing...',
        'uploadPaper.validationRequired': 'All required fields must be filled.',
        'uploadPaper.validationTerms': 'Please agree to the copyright and open access policy.',
        'uploadPaper.statusUploading': 'Uploading paper to IPFS...',
        'uploadPaper.statusMinting': 'Minting IP-NFT...',
        'uploadPaper.statusRewarding': 'Distributing DSCI rewards...',
        'uploadPaper.rewardSuccess': ' Rewards delivered.',
        'uploadPaper.rewardDelayed': ' Reward transaction delayed.',
        'uploadPaper.rewardSkipped': ' Reward skipped.',
        'uploadPaper.uploadSuccess': `Paper uploaded successfully!${values.rewardMessage ?? ''}`,
        'uploadPaper.uploadFailed': 'Upload failed.',
        'uploadPaper.title': 'Research Upload',
        'uploadPaper.subtitle': 'Register a new research paper in the DeSci ecosystem.',
        'uploadPaper.fileDropTitle': 'Click here or drag a PDF file to upload',
        'uploadPaper.fileDropDescription': 'Up to 50MB, PDF only',
        'uploadPaper.titleLabel': 'Paper Title',
        'uploadPaper.titlePlaceholder': 'Ex) A novel approach to targeted CRISPR-Cas9...',
        'uploadPaper.authorsLabel': 'Authors',
        'uploadPaper.authorsPlaceholder': 'Ex) John Doe, Jane Smith (comma separated)',
        'uploadPaper.abstractLabel': 'Abstract',
        'uploadPaper.abstractPlaceholder': 'Summarize the key findings...',
        'uploadPaper.agreementLabel': '[Required] Creative Commons (CC) license and open access agreement',
        'uploadPaper.agreementDescription': 'Agree to permanent open access storage on IPFS.',
        'uploadPaper.submit': 'Store on IPFS and register paper',
        'assetManager.loadFailed': 'Failed to load assets.',
        'assetManager.uploadSuccess': 'Asset uploaded successfully.',
        'assetManager.uploadFailed': 'Failed to upload asset.',
        'assetManager.title': 'Asset Management',
        'assetManager.uploadTitle': 'Upload Company Asset',
        'assetManager.uploadDescription': 'PDF, TXT supported. Max 10MB.',
        'assetManager.selectFile': 'Select File',
        'assetManager.uploading': 'Uploading...',
        'assetManager.myAssets': 'My Assets',
        'assetManager.empty': 'No assets uploaded yet.',
        'assetManager.typeIr': 'IR Deck / Pitch',
        'assetManager.typePaper': 'Technical Paper',
        'assetManager.typePatent': 'Patent Doc',
        'assetManager.typeGeneral': 'Other',
        'assetManager.pinned': 'Pinned',
        'assetManager.pending': 'Pending...',
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
    expect(screen.getByText(/Asset Management/i)).toBeDefined();
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

