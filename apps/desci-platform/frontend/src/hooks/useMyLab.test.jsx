import { renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

let translate = (key) => key;
const showToast = vi.fn();

vi.mock('../services/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({
    walletAddress: null,
  }),
}));

vi.mock('../contexts/ToastContext', () => ({
  useToast: () => ({
    showToast,
  }),
}));

vi.mock('../contexts/LocaleContext', () => ({
  useLocale: () => ({
    t: translate,
  }),
}));

import client from '../services/api';
import { useMyLab } from './useMyLab';

describe('useMyLab', () => {
  beforeEach(() => {
    translate = (key) => key;
    showToast.mockReset();
    client.get.mockReset();
    client.get.mockResolvedValue({ data: [] });
  });

  it('does not refetch papers when translations change', async () => {
    const { rerender } = renderHook(() => useMyLab());

    await waitFor(() => {
      expect(client.get).toHaveBeenCalledTimes(1);
    });

    translate = (key) => `translated:${key}`;
    rerender();

    await waitFor(() => {
      expect(client.get).toHaveBeenCalledTimes(1);
    });
  });
});
