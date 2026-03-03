import { describe, it, expect, vi } from 'vitest';

// Mock framer-motion to avoid animation issues in tests
vi.mock('framer-motion', () => ({
  motion: {
    div: ({ children, ...props }) => <div {...props}>{children}</div>,
    span: ({ children, ...props }) => <span {...props}>{children}</span>,
  },
  AnimatePresence: ({ children }) => <>{children}</>,
  useAnimation: () => ({ start: vi.fn(), stop: vi.fn() }),
}));

// Mock react-router-dom
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => vi.fn(),
    useLocation: () => ({ pathname: '/dashboard' }),
    useParams: () => ({ id: 'test-id' }),
    Link: ({ children, to, ...props }) => <a href={to} {...props}>{children}</a>,
  };
});

// Mock Firebase Auth context
vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({
    user: { email: 'test@test.com', displayName: 'Test User' },
    logout: vi.fn(),
    walletAddress: '0x1234567890abcdef1234567890abcdef12345678',
    connectWallet: vi.fn().mockResolvedValue({ success: true, address: '0x1234' }),
  }),
}));

// Mock Toast context
vi.mock('../contexts/ToastContext', () => ({
  useToast: () => ({
    showToast: vi.fn(),
  }),
}));

// Mock API
vi.mock('../services/api', () => ({
  default: {
    get: vi.fn().mockResolvedValue({ data: [] }),
    post: vi.fn().mockResolvedValue({ data: { success: true } }),
  },
}));

describe('Test Setup', () => {
  it('should pass basic assertion', () => {
    expect(1 + 1).toBe(2);
  });
});
