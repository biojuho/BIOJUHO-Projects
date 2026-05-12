/* global describe, expect, it */

import {
  createSupportId,
  formatSupportError,
  getErrorDetail,
  getErrorRequestId,
  readResponseHeader,
} from './support';

describe('support diagnostics helpers', () => {
  it('creates backend-safe prefixed support ids', () => {
    expect(createSupportId('ui')).toMatch(/^ui-[A-Za-z0-9._-]+$/);
  });

  it('reads response headers from Fetch Headers and plain objects', () => {
    expect(readResponseHeader(new Headers({ 'X-Request-ID': 'req-1' }), 'x-request-id')).toBe('req-1');
    expect(readResponseHeader({ 'X-Response-Time-Ms': '12.50' }, 'x-response-time-ms')).toBe('12.50');
  });

  it('formats API errors with support ids for user-facing messages', () => {
    const error = {
      response: {
        data: { detail: 'Backend failed' },
        headers: new Headers({ 'X-Request-ID': 'support-123' }),
      },
    };

    expect(getErrorDetail(error, 'Fallback')).toBe('Backend failed');
    expect(getErrorRequestId(error)).toBe('support-123');
    expect(formatSupportError(error, 'Fallback')).toBe('Backend failed (support id: support-123)');
  });

  it('falls back to the error message when there is no API detail', () => {
    expect(formatSupportError(new Error('Network failed'), 'Fallback')).toBe('Network failed');
  });
});
