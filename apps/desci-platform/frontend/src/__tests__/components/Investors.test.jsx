/* global afterEach, beforeEach, describe, expect, it, vi */
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

const apiMock = vi.hoisted(() => ({
  get: vi.fn(),
}));

vi.mock('../../contexts/LocaleContext', () => ({
  useLocale: () => ({
    locale: 'en-US',
    t: (key, values = {}) => {
      const messages = {
        'investors.showingCount': `Showing ${values.shown} of ${values.total} investors`,
        'investors.emptyTitle': 'No investors match your filters',
        'investors.emptyDescription': 'Try clearing a filter or broadening the keyword search.',
        'investors.websiteUnavailable': 'Website unavailable',
        'investors.emailUnavailable': 'Email unavailable',
      };
      return messages[key] ?? key;
    },
  }),
}));

vi.mock('../../services/api', () => ({
  default: apiMock,
}));

import Investors from '../../components/Investors';

const SAMPLE = [
  {
    id: 'vc-test-001',
    name: 'Acme Bio Capital',
    country: 'KR',
    website: 'https://acme.example',
    investment_thesis: 'Investing in oncology and gene therapy platforms.',
    preferred_stages: ['Series A', 'Series B'],
    portfolio_keywords: ['Oncology', 'Gene Therapy'],
    contact_email: 'hello@acme.example',
  },
  {
    id: 'vc-test-002',
    name: 'Globex Health Fund',
    country: 'US',
    website: 'javascript:alert(1)',
    investment_thesis: 'Digital therapeutics and mobile health.',
    preferred_stages: ['Seed'],
    portfolio_keywords: ['Digital Health', 'Mobile App'],
    contact_email: 'javascript:alert(1)',
  },
];

function renderInvestors() {
  return render(
    <MemoryRouter initialEntries={['/investors']}>
      <Investors />
    </MemoryRouter>,
  );
}

describe('Investors', () => {
  beforeEach(() => {
    apiMock.get.mockReset();
    apiMock.get.mockResolvedValue({ data: SAMPLE });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('lists VCs returned from the API with a stable result count', async () => {
    renderInvestors();

    expect(await screen.findByText('Acme Bio Capital')).toBeInTheDocument();
    expect(screen.getByText('Globex Health Fund')).toBeInTheDocument();
    expect(screen.getByTestId('investors-result-count')).toHaveTextContent('Showing 2 of 2 investors');
    expect(screen.queryByTestId('investors-fallback-banner')).toBeNull();
  });

  it('filters by country, stage, and keyword without hiding the matching VC', async () => {
    renderInvestors();

    await screen.findByText('Acme Bio Capital');
    fireEvent.change(screen.getByTestId('investors-search'), { target: { value: 'oncology' } });
    fireEvent.change(screen.getByTestId('investors-country-filter'), { target: { value: 'KR' } });
    fireEvent.change(screen.getByTestId('investors-stage-filter'), { target: { value: 'Series A' } });

    expect(screen.getByText('Acme Bio Capital')).toBeInTheDocument();
    expect(screen.queryByText('Globex Health Fund')).toBeNull();
    expect(screen.getByTestId('investors-result-count')).toHaveTextContent('Showing 1 of 2 investors');
  });

  it('renders the launch seed directory when the API returns an empty list', async () => {
    apiMock.get.mockResolvedValueOnce({ data: [] });

    renderInvestors();

    expect(await screen.findByTestId('investors-fallback-banner')).toHaveTextContent('curated launch directory');
    expect(screen.getByTestId('investor-card-vc-kip-001')).toBeInTheDocument();
    expect(screen.getByText('Korea Investment Partners')).toBeInTheDocument();
    expect(screen.queryByText('No investors match your filters')).toBeNull();
    expect(screen.getByTestId('investors-result-count')).toHaveTextContent('Showing 5 of 5 investors');
  });

  it('renders the launch seed directory when the API request fails', async () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
    apiMock.get.mockRejectedValueOnce(new Error('network down'));

    renderInvestors();

    expect(await screen.findByTestId('investors-fallback-banner')).toHaveTextContent('curated launch directory');
    expect(screen.getByTestId('investor-card-vc-intervest-002')).toBeInTheDocument();
    expect(warnSpy).toHaveBeenCalledWith(
      expect.stringContaining('using launch directory fallback'),
      expect.any(Error),
    );
  });

  it('shows an empty state only when filters match no rendered investors', async () => {
    renderInvestors();

    await screen.findByText('Acme Bio Capital');
    fireEvent.change(screen.getByTestId('investors-search'), { target: { value: 'nonexistent-term-xyz' } });

    await waitFor(() => {
      expect(screen.getByText('No investors match your filters')).toBeInTheDocument();
    });
  });

  it('does not render links for unsafe investor website or email fields', async () => {
    renderInvestors();

    await screen.findByText('Globex Health Fund');

    expect(screen.getByTestId('investor-website-unavailable-vc-test-002')).toHaveTextContent('Website unavailable');
    expect(screen.getByTestId('investor-email-unavailable-vc-test-002')).toHaveTextContent('Email unavailable');
    expect(screen.queryByTestId('investor-website-vc-test-002')).toBeNull();
    expect(screen.queryByTestId('investor-email-vc-test-002')).toBeNull();
    expect(document.querySelectorAll('a[href="#"], a[href^="javascript:"]')).toHaveLength(0);
  });
});
