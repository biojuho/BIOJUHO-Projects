/**
 * Global test setup for desci-platform/frontend.
 *
 * This file runs before EVERY test file (configured via vite.config.js setupFiles).
 * Mocks defined here apply globally — individual test files can override with
 * their own vi.mock() calls when different behaviour is needed.
 *
 * Pattern inspired by biolinker/tests/conftest.py:
 *   conftest.py centralises monkeypatch stubs → setup.jsx centralises vi.mock stubs
 */
import { cleanup } from '@testing-library/react';
import { afterEach, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';

afterEach(() => {
  cleanup();
});

// ── Global mocks ───────────────────────────────────────────────────────────
// These replace the vi.mock() boilerplate that was copy-pasted across
// every test file. Only mocks that are IDENTICAL in all tests belong here.

// Framer Motion — comprehensive prop-stripping to avoid React DOM warnings
vi.mock('framer-motion', () => ({
  motion: {
    div: ({ children, variants: _v, initial: _i, animate: _a, exit: _e,
            transition: _t, whileHover: _h, whileTap: _tp, layoutId: _l,
            ...rest }) => <div {...rest}>{children}</div>,
    span: ({ children, ...props }) => <span {...props}>{children}</span>,
  },
  AnimatePresence: ({ children }) => <>{children}</>,
  useAnimation: () => ({ start: vi.fn(), stop: vi.fn() }),
}));

// Toast context — identical across all test files
vi.mock('../contexts/ToastContext', () => ({
  useToast: () => ({ showToast: vi.fn() }),
}));
