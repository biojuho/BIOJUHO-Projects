import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import QRTracker from './QRTracker';

afterEach(() => {
  cleanup();
});

describe('QRTracker', () => {
  it('renders an accessible QR for explicit verification values', () => {
    render(<QRTracker value="AGRI-VERIFY-123" ariaLabel="Batch verification QR" />);

    const qrShell = screen.getByRole('img', { name: 'Batch verification QR' });

    expect(qrShell).toBeInTheDocument();
    expect(qrShell).toHaveClass('w-full');
    expect(qrShell).toHaveClass('max-w-[184px]');
    expect(qrShell).not.toHaveClass('min-w-[184px]');
    expect(screen.getByText('SCAN TO VERIFY')).toBeInTheDocument();
    expect(document.querySelector('svg')).toBeInTheDocument();
  });

  it('fails closed when no QR value or product id is available', () => {
    render(<QRTracker />);

    const fallback = screen.getByRole('status', { name: 'Product verification QR unavailable' });

    expect(fallback).toHaveTextContent(
      'QR UNAVAILABLE',
    );
    expect(fallback).toHaveClass('w-full');
    expect(fallback).toHaveClass('max-w-[184px]');
    expect(fallback).toHaveClass('min-w-0');
    expect(fallback).not.toHaveClass('min-w-[184px]');
    expect(screen.getByText('QR')).toHaveClass('w-full');
    expect(screen.getByText('QR')).toHaveClass('max-w-32');
    expect(screen.queryByRole('img', { name: 'Product verification QR' })).not.toBeInTheDocument();
    expect(screen.queryByText('/product/undefined')).not.toBeInTheDocument();
    expect(document.querySelector('svg')).toBeNull();
  });
});
