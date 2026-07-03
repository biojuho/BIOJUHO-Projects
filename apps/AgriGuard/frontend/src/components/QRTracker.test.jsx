import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import QRTracker from './QRTracker';

afterEach(() => {
  cleanup();
});

describe('QRTracker', () => {
  it('renders an accessible QR for explicit verification values', () => {
    render(<QRTracker value="AGRI-VERIFY-123" ariaLabel="Batch verification QR" />);

    expect(screen.getByRole('img', { name: 'Batch verification QR' })).toBeInTheDocument();
    expect(screen.getByText('SCAN TO VERIFY')).toBeInTheDocument();
    expect(document.querySelector('svg')).toBeInTheDocument();
  });

  it('fails closed when no QR value or product id is available', () => {
    render(<QRTracker />);

    expect(screen.getByRole('status', { name: 'Product verification QR unavailable' })).toHaveTextContent(
      'QR UNAVAILABLE',
    );
    expect(screen.queryByRole('img', { name: 'Product verification QR' })).not.toBeInTheDocument();
    expect(screen.queryByText('/product/undefined')).not.toBeInTheDocument();
    expect(document.querySelector('svg')).toBeNull();
  });
});
