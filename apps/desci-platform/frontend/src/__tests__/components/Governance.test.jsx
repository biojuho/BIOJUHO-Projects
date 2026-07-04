/* global describe, it, expect, vi, beforeEach */
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

const mockUseAuth = vi.fn();

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => mockUseAuth(),
}));

vi.mock('../../contexts/ToastContext', () => ({
  useToast: () => ({
    showToast: vi.fn(),
  }),
}));

const messages = {
  'governance.title': 'Governance Hub',
  'governance.subtitle': 'Manage proposals, votes, and execution states from one surface.',
  'governance.newProposal': 'New proposal',
  'governance.createTitle': 'Create proposal',
  'governance.proposalTitle': 'Proposal title',
  'governance.proposalDescription': 'Proposal description',
  'governance.submitProposal': 'Submit proposal',
  'governance.requiresTokens': 'Proposal creation requires a minimum DSCI balance.',
  'governance.walletRequiredTitle': 'Wallet required',
  'governance.walletRequired': 'Governance actions require a connected wallet before creating proposals or voting.',
  'governance.noProposals': 'No proposals yet.',
  'governance.noProposalsHint': 'Be the first to create a governance proposal.',
  'governance.loadFailed': 'Failed to load proposals.',
  'governance.validation': 'Title and description are required.',
  'governance.createSuccess': 'Proposal created successfully.',
  'governance.createFailed': 'Failed to create proposal.',
  'governance.voteFor': 'For',
  'governance.voteAgainst': 'Against',
  'governance.voteSuccessFor': 'Vote cast: For',
  'governance.voteSuccessAgainst': 'Vote cast: Against',
  'governance.voteFailed': 'Vote failed.',
  'governance.statePending': 'Pending',
  'governance.stateActive': 'Active',
  'governance.statePassed': 'Passed',
  'governance.stateRejected': 'Rejected',
  'governance.stateQueued': 'Queued',
  'governance.stateExecuted': 'Executed',
  'governance.votesFor': 'For',
  'governance.votesAgainst': 'Against',
  'governance.endDate': 'Ends',
  'governance.receiptTitle': 'Governance action confirmed',
  'governance.receiptProposal': 'Proposal',
  'governance.receiptVote': 'Vote',
  'governance.receiptProposalBody': 'Proposal created: {title}',
  'governance.receiptVoteBody': 'Vote recorded: {support} on {title}',
  'governance.receiptWallet': 'Wallet: {wallet}',
  'layout.trust': 'Trust',
};

vi.mock('../../contexts/LocaleContext', () => ({
  useLocale: () => ({
    locale: 'en-US',
    t: (key, values = {}) => {
      let message = messages[key] ?? key;
      Object.entries(values).forEach(([name, value]) => {
        message = message.replace(`{${name}}`, value);
      });
      return message;
    },
  }),
}));

vi.mock('../../services/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

vi.mock('../../lib/support', () => ({
  formatSupportError: (_error, fallback) => fallback,
}));

import api from '../../services/api';
import Governance from '../../components/Governance';

function renderGovernance() {
  return render(
    <MemoryRouter>
      <Governance />
    </MemoryRouter>
  );
}

describe('Governance', () => {
  beforeEach(() => {
    mockUseAuth.mockReturnValue({
      walletAddress: '0x1234',
      user: null,
    });
    api.get.mockReset();
    api.post.mockReset();
    api.get.mockResolvedValue({ data: [] });
  });

  it('renders queued and executed proposal states using the DAO enum', async () => {
    api.get.mockResolvedValueOnce({
      data: [
        {
          id: 'proposal-1',
          title: 'Queued proposal',
          description: 'Waiting for timelock',
          for_votes: '200',
          against_votes: '50',
          state: 4,
          end_time: '2026-05-14T00:00:00Z',
        },
        {
          id: 'proposal-2',
          title: 'Executed proposal',
          description: 'Already executed',
          for_votes: '300',
          against_votes: '100',
          state: 5,
          end_time: '2026-05-10T00:00:00Z',
        },
      ],
    });

    renderGovernance();

    await waitFor(() => expect(api.get).toHaveBeenCalledWith('/governance/proposals'));
    expect(await screen.findByText('Queued')).toBeInTheDocument();
    expect(screen.getByText('Executed')).toBeInTheDocument();
  });

  it('shows vote actions only for active proposals and handles string vote counts', async () => {
    api.get.mockResolvedValueOnce({
      data: [
        {
          id: 'proposal-3',
          title: 'Active proposal',
          description: 'Open for voting',
          for_votes: '9007199254740993',
          against_votes: '7',
          state: '1',
          end_time: '2026-05-20T00:00:00Z',
        },
        {
          id: 'proposal-4',
          title: 'Rejected proposal',
          description: 'Closed',
          for_votes: '10',
          against_votes: '20',
          state: 3,
          end_time: '2026-05-10T00:00:00Z',
        },
      ],
    });

    renderGovernance();

    expect(await screen.findByText('For: 9007199254740993')).toBeInTheDocument();
    expect(screen.getByText('Against: 7')).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: 'For' })).toHaveLength(1);
    expect(screen.getAllByRole('button', { name: 'Against' })).toHaveLength(1);
  });

  it('announces wallet-required governance guidance and disables governance actions without a wallet', async () => {
    mockUseAuth.mockReturnValue({
      walletAddress: null,
      user: null,
    });
    api.get.mockResolvedValueOnce({
      data: [
        {
          id: 'proposal-5',
          title: 'Active wallet guard proposal',
          description: 'Open for no-wallet action checks',
          for_votes: '42',
          against_votes: '8',
          state: '1',
          end_time: '2026-05-20T00:00:00Z',
        },
      ],
    });

    renderGovernance();

    const guidance = await screen.findByTestId('governance-wallet-required');
    expect(guidance).toHaveAttribute('role', 'status');
    expect(guidance).toHaveAttribute('aria-atomic', 'true');
    expect(guidance).toHaveTextContent('Wallet required');
    expect(guidance).toHaveTextContent('Governance actions require a connected wallet before creating proposals or voting.');
    expect(await screen.findByRole('button', { name: 'For' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Against' })).toBeDisabled();

    fireEvent.click(screen.getByRole('button', { name: 'New proposal' }));

    expect(await screen.findByRole('button', { name: 'Submit proposal' })).toBeDisabled();
  });
});
