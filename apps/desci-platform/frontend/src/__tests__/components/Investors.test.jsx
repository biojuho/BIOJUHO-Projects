/* global describe, it, expect, vi, beforeEach, afterEach */
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../../services/api', () => ({
  default: {
    get: vi.fn(),
  },
}));

vi.mock('framer-motion', async () => {
  const actual = await vi.importActual('framer-motion');
  return { ...actual, useInView: () => true };
});

import client from '../../services/api';
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
    website: 'https://globex.example',
    investment_thesis: 'Digital therapeutics and mobile health.',
    preferred_stages: ['Seed'],
    portfolio_keywords: ['Digital Health', 'Mobile App'],
    contact_email: 'team@globex.example',
  },
];

function renderInvestors() {
  return render(
    <MemoryRouter initialEntries={['/investors']}>
      <Investors />
    </MemoryRouter>,
  );
}

describe('Investors page', () => {
  beforeEach(() => {
    client.get.mockReset();
    client.get.mockResolvedValue({ data: SAMPLE, status: 200, headers: new Headers(), ok: true });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('renders the investor directory headline', async () => {
    renderInvestors();
    expect(screen.getByText(/Investor directory/i)).toBeDefined();
  });

  it('lists VCs returned from the API', async () => {
    renderInvestors();
    await waitFor(() => {
      expect(screen.getByText('Acme Bio Capital')).toBeDefined();
      expect(screen.getByText('Globex Health Fund')).toBeDefined();
    });
  });

  it('filters by country', async () => {
    renderInvestors();
    await waitFor(() => expect(screen.getByText('Acme Bio Capital')).toBeDefined());

    const countrySelect = screen.getByLabelText(/Filter by country/i);
    fireEvent.change(countrySelect, { target: { value: 'US' } });

    await waitFor(() => {
      expect(screen.queryByText('Acme Bio Capital')).toBeNull();
      expect(screen.getByText('Globex Health Fund')).toBeDefined();
    });
  });

  it('filters by keyword across name and thesis', async () => {
    renderInvestors();
    await waitFor(() => expect(screen.getByText('Acme Bio Capital')).toBeDefined());

    const searchInput = screen.getByPlaceholderText(/Search name, thesis, or keyword/i);
    fireEvent.change(searchInput, { target: { value: 'oncology' } });

    await waitFor(() => {
      expect(screen.getByText('Acme Bio Capital')).toBeDefined();
      expect(screen.queryByText('Globex Health Fund')).toBeNull();
    });
  });

  it('shows an empty state when filters match nothing', async () => {
    renderInvestors();
    await waitFor(() => expect(screen.getByText('Acme Bio Capital')).toBeDefined());

    const searchInput = screen.getByPlaceholderText(/Search name, thesis, or keyword/i);
    fireEvent.change(searchInput, { target: { value: 'nonexistent-term-xyz' } });

    await waitFor(() =>
      expect(screen.getByText(/No investors match your filters/i)).toBeDefined(),
    );
  });

  it('shows an error banner when the request fails', async () => {
    client.get.mockRejectedValueOnce(new Error('network down'));
    renderInvestors();
    await waitFor(() =>
      expect(screen.getByText(/Could not load investor directory/i)).toBeDefined(),
    );
  });

  it('renders mailto and website links per card', async () => {
    renderInvestors();
    await waitFor(() => expect(screen.getByText('Acme Bio Capital')).toBeDefined());

    const mailto = screen.getByText('hello@acme.example').closest('a');
    expect(mailto.getAttribute('href')).toBe('mailto:hello@acme.example');

    const websiteAnchor = document.querySelector('a[href="https://acme.example"]');
    expect(websiteAnchor).not.toBeNull();
    expect(websiteAnchor.getAttribute('target')).toBe('_blank');
    expect(websiteAnchor.getAttribute('rel')).toContain('noopener');
  });
});
