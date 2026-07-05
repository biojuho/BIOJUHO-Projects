import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import Toast from './Toast';

vi.mock('framer-motion', () => ({
  AnimatePresence: ({ children }) => children,
  motion: {
    div: ({ children, ...props }) => {
      delete props.variants;
      delete props.initial;
      delete props.animate;
      delete props.exit;

      return <div {...props}>{children}</div>;
    },
  },
}));

describe('Toast', () => {
  it('uses mobile snackbar placement without covering the fixed app nav', () => {
    render(<Toast message="Operator token saved." type="success" duration={0} />);

    const toast = screen.getByRole('alert');
    expect(toast).toHaveClass('bottom-4');
    expect(toast).toHaveClass('sm:bottom-auto');
    expect(toast).toHaveClass('sm:top-6');
    expect(toast).toHaveClass('inset-x-4');
    expect(toast).toHaveClass('sm:right-6');
    expect(toast).toHaveClass('z-[60]');
  });
});
