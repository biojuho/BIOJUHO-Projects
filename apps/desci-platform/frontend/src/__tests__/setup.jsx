/**
 * Global test setup for desci-platform/frontend.
 *
 * This file runs before EVERY test file (configured via vite.config.js setupFiles).
 * Mocks defined here apply globally — individual test files can override with
 * their own vi.mock() calls when different behaviour is needed.
 *
 * Pattern inspired by biolinker/tests/conftest.py:
 *   conftest.py centralises monkeypatch stubs → setup.jsx centralises vi.mock stubs
 *
 * vitest 4.0: globals: true 설정으로 vi, afterEach 등이 전역에서 사용 가능.
 * setup 파일에서 vitest를 직접 import하면 "failed to find the runner" 에러 발생.
 */
import { cleanup } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';

/* global vi, afterEach */

afterEach(() => {
  cleanup();
});

// ── Global mocks ───────────────────────────────────────────────────────────
// These replace the vi.mock() boilerplate that was copy-pasted across
// every test file. Only mocks that are IDENTICAL in all tests belong here.

// Framer Motion — strip all framer props, pass only HTML-safe props
vi.mock('framer-motion', () => {
  const FRAMER_PROPS = new Set([
    'variants', 'initial', 'animate', 'exit', 'transition',
    'whileHover', 'whileTap', 'whileInView', 'layoutId', 'layout',
  ]);
  const stripFramer = (props) => {
    const clean = {};
    for (const [k, v] of Object.entries(props)) {
      if (!FRAMER_PROPS.has(k)) clean[k] = v;
    }
    return clean;
  };
  return {
    motion: {
      div: ({ children, ...rest }) => <div {...stripFramer(rest)}>{children}</div>,
      span: ({ children, ...rest }) => <span {...stripFramer(rest)}>{children}</span>,
      button: ({ children, ...rest }) => <button {...stripFramer(rest)}>{children}</button>,
    },
    AnimatePresence: ({ children }) => <>{children}</>,
    useAnimation: () => ({ start: vi.fn(), stop: vi.fn() }),
  };
});

// Toast context — identical across all test files
vi.mock('../contexts/ToastContext', () => ({
  useToast: () => ({ showToast: vi.fn() }),
}));
