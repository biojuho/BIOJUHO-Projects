/* global describe, it, expect, vi, beforeEach */
import { render, screen, waitFor } from '@testing-library/react';

vi.mock('../../contexts/LocaleContext', () => ({
  useLocale: () => ({
    t: (key) => ({
      'recommendation.loading': 'Calculating recommendations.',
      'recommendation.loadFailed': 'Recommendation data is unavailable.',
      'recommendation.emptyTitle': 'No recommendations yet.',
      'recommendation.emptyDescription': 'As more papers and assets arrive, recommendation quality improves.',
      'recommendation.matchSuffix': 'match',
      'recommendation.viewDetails': 'Open source',
      'recommendation.sourceUnavailable': 'Source link unavailable',
      'vcMatch.loadFailed': 'Failed to load VC matches.',
      'vcMatch.emptyTitle': 'No VC matches yet.',
      'vcMatch.emptyDescription': 'As more assets and papers arrive, investor recommendations will appear here.',
      'vcMatch.global': 'Global',
      'vcMatch.matchLabel': 'fit',
    }[key] ?? key),
  }),
}));

vi.mock('../../services/api', () => ({
  default: {
    get: vi.fn(),
  },
}));

import api from '../../services/api';
import RecommendationList from '../../components/dashboard/RecommendationList';
import VCMatchList from '../../components/dashboard/VCMatchList';

describe('Dashboard data lists', () => {
  beforeEach(() => {
    api.get.mockReset();
  });

  it('loads strategic investor matches from the existing VC directory endpoint', async () => {
    api.get.mockResolvedValueOnce({
      data: [
        {
          id: 'vc-1',
          name: 'Bio VC',
          country: 'US',
          investment_thesis: 'Backs translational oncology platforms.',
          portfolio_keywords: ['oncology', 'platform biology'],
        },
      ],
    });

    render(<VCMatchList />);

    await waitFor(() => expect(api.get).toHaveBeenCalledWith('/vcs', {
      params: { limit: 3 },
      suppressErrorLog: true,
    }));
    expect(api.get).toHaveBeenCalledTimes(1);
    expect(await screen.findByText('Bio VC')).toBeDefined();
    expect(screen.getByText(/Backs translational oncology/)).toBeDefined();
    expect(screen.getByText(/Focus areas: oncology/)).toBeDefined();
  });

  it('shows the localized VC fallback when the backend cannot be reached', async () => {
    api.get.mockRejectedValueOnce(new TypeError('Failed to fetch'));

    render(<VCMatchList />);

    expect(await screen.findByText('Failed to load VC matches.')).toBeDefined();
    expect(screen.queryByText('Failed to fetch')).toBeNull();
  });

  it('keeps VC API response details and support ids for server errors', async () => {
    api.get.mockRejectedValueOnce({
      response: {
        data: {
          detail: 'VC directory unavailable',
          request_id: 'support-vc-123',
        },
      },
    });

    render(<VCMatchList />);

    expect(await screen.findByText('VC directory unavailable (support id: support-vc-123)')).toBeDefined();
  });

  it('loads recommendation cards from collected notices instead of a missing route', async () => {
    api.get.mockResolvedValueOnce({
      data: [
        {
          id: 'notice-1',
          title: 'AI Drug Discovery Grant',
          source: 'KDDF',
          body_text: 'Funding for translational AI drug discovery.',
          deadline: '2026-07-31',
          url: 'https://example.test/notice',
        },
      ],
    });

    render(<RecommendationList />);

    await waitFor(() => expect(api.get).toHaveBeenCalledWith('/notices', {
      params: { limit: 3 },
      suppressErrorLog: true,
    }));
    expect(await screen.findByText('AI Drug Discovery Grant')).toBeDefined();
    expect(screen.getByText(/Funding for translational AI/)).toBeDefined();
    expect(screen.getByText(/KDDF opportunity available/)).toBeDefined();
    expect(screen.getByTestId('recommendation-source-link-0')).toHaveAttribute('href', 'https://example.test/notice');
    expect(screen.getByTestId('recommendation-source-link-0')).toHaveAttribute('target', '_blank');
    expect(screen.getByTestId('recommendation-source-link-0')).toHaveAttribute('rel', 'noopener noreferrer');
  });

  it('does not render broken source links when notice URLs are missing or unsafe', async () => {
    api.get.mockResolvedValueOnce({
      data: [
        {
          id: 'notice-missing-url',
          title: 'Missing Source Grant',
          source: 'NTIS',
          body_text: 'Funding notice without a canonical source URL.',
        },
        {
          id: 'notice-unsafe-url',
          title: 'Unsafe Source Grant',
          source: 'KDDF',
          body_text: 'Funding notice with an unsafe source URL.',
          url: 'javascript:alert(1)',
        },
      ],
    });

    render(<RecommendationList />);

    expect(await screen.findByText('Missing Source Grant')).toBeDefined();
    expect(screen.getByText('Unsafe Source Grant')).toBeDefined();
    expect(screen.getByTestId('recommendation-source-unavailable-0')).toHaveTextContent('Source link unavailable');
    expect(screen.getByTestId('recommendation-source-unavailable-1')).toHaveTextContent('Source link unavailable');
    expect(screen.queryByTestId('recommendation-source-link-0')).toBeNull();
    expect(screen.queryByTestId('recommendation-source-link-1')).toBeNull();
  });

  it('shows an actionable recommendation fallback when notices cannot be reached', async () => {
    api.get.mockRejectedValueOnce(new TypeError('Failed to fetch'));

    render(<RecommendationList />);

    expect(await screen.findByText('Recommendation data is unavailable.')).toBeDefined();
    expect(screen.queryByText('No recommendations yet.')).toBeNull();
    expect(screen.queryByText('Failed to fetch')).toBeNull();
  });

  it('keeps recommendation API response details and support ids for server errors', async () => {
    api.get.mockRejectedValueOnce({
      response: {
        data: {
          detail: 'Funding recommendation service unavailable',
          request_id: 'support-rec-456',
        },
      },
    });

    render(<RecommendationList />);

    expect(
      await screen.findByText('Funding recommendation service unavailable (support id: support-rec-456)')
    ).toBeDefined();
  });
});
