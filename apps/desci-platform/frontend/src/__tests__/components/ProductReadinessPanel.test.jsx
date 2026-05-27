/* global describe, it, expect, vi, beforeEach */
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

vi.mock('../../contexts/LocaleContext', () => ({
  useLocale: () => ({ locale: 'en', t: (key) => key }),
}));

vi.mock('../../services/api', () => ({
  default: { get: vi.fn() },
}));

vi.mock('../../lib/support', () => ({
  formatSupportError: (_err, fallback) => fallback,
}));

import client from '../../services/api';
import ProductReadinessPanel from '../../components/ProductReadinessPanel';

const READY_PAYLOAD = {
  status: 'ready',
  summary: { ready_count: 3, total: 3, required_ready_count: 2, required_total: 2 },
  checks: [
    { id: 'api', status: 'pass', required: true },
    { id: 'auth', status: 'pass', required: true },
    { id: 'redis', status: 'pass', required: false },
  ],
  checked_at: '2026-05-11T10:00:00Z',
};

describe('ProductReadinessPanel', () => {
  beforeEach(() => {
    client.get.mockReset();
  });

  it('renders the readiness summary from /ready', async () => {
    client.get.mockResolvedValueOnce({ data: READY_PAYLOAD });
    render(<ProductReadinessPanel />);

    await waitFor(() => expect(client.get).toHaveBeenCalledWith('/ready', { timeout: 10_000 }));
    expect(await screen.findByText('100%')).toBeDefined();
    expect(screen.getByText('3/3 checks ready', { exact: false }) ||
      screen.getByText(/3.*3/)).toBeDefined();
  });

  it('falls back to the unavailable state when /ready fails', async () => {
    client.get.mockRejectedValueOnce(new Error('network down'));
    render(<ProductReadinessPanel />);

    await waitFor(() => expect(client.get).toHaveBeenCalled());
    expect(await screen.findByText('Readiness API is unavailable. Check backend connectivity before demo or launch.')).toBeDefined();
  });

  it('re-fetches when Refresh is clicked', async () => {
    client.get.mockResolvedValue({ data: READY_PAYLOAD });
    render(<ProductReadinessPanel />);
    await waitFor(() => expect(client.get).toHaveBeenCalledTimes(1));

    const button = screen.getByRole('button', { name: /Refresh/i });
    fireEvent.click(button);
    await waitFor(() => expect(client.get).toHaveBeenCalledTimes(2));
  });
});
