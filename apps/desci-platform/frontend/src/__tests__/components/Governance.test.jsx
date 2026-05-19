/* global describe, it, expect, vi, beforeEach */
import { render, screen, waitFor } from '@testing-library/react';

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({
    walletAddress: '0x1234',
  }),
}));

vi.mock('../../contexts/LocaleContext', () => ({
  useLocale: () => ({
    locale: 'en-US',
    t: (key) => ({
      'governance.title': 'Governance Hub',
      'governance.subtitle': 'Manage proposals, votes, and execution states from one surface.',
      'governance.newProposal': 'New proposal',
      'governance.createTitle': 'Create proposal',
      'governance.proposalTitle': 'Proposal title',
      'governance.proposalDescription': 'Proposal description',
      'governance.submitProposal': 'Submit proposal',
      'governance.requiresTokens': 'Proposal creation requires a minimum DSCI balance.',
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
      'layout.trust': 'Trust',
    }[key] ?? key),
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

describe('Governance', () => {
  beforeEach(() => {
    api.get.mockReset();
    api.post.mockReset();
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

    render(<Governance />);

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

    render(<Governance />);

    expect(await screen.findByText('For: 9007199254740993')).toBeInTheDocument();
    expect(screen.getByText('Against: 7')).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: 'For' })).toHaveLength(1);
    expect(screen.getAllByRole('button', { name: 'Against' })).toHaveLength(1);
  });
});
