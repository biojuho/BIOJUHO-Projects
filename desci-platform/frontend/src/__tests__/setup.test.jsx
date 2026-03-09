import { describe, it, expect } from 'vitest';

// framer-motion, ToastContext, jest-dom matchers — provided by global setup.jsx

describe('Test Setup', () => {
  it('should pass basic assertion', () => {
    expect(1 + 1).toBe(2);
  });
});
