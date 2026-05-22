/* global beforeEach, describe, expect, it, vi */

const { authMock } = vi.hoisted(() => ({
  authMock: { currentUser: null },
}));

vi.mock('../firebase', () => ({
  auth: authMock,
}));

vi.mock('../contexts/LocaleContext', () => ({
  getStoredLocale: () => 'ko-KR',
  getStoredOutputLanguage: () => 'ko',
}));

const { ApiError, buildApiUrl, formatApiError, default: api } = await import('./api');

function jsonResponse(data, init = {}) {
  return new Response(JSON.stringify(data), {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init.headers ?? {}),
    },
  });
}

describe('fetch api client', () => {
  beforeEach(() => {
    authMock.currentUser = null;
    globalThis.fetch = vi.fn();
    vi.restoreAllMocks();
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  it('adds auth, locale, and query params to requests', async () => {
    authMock.currentUser = {
      getIdToken: vi.fn().mockResolvedValue('token-123'),
    };
    globalThis.fetch.mockResolvedValueOnce(jsonResponse({ ok: true }));

    await api.get('/me', { params: { limit: 2, source: 'KDDF' } });

    const [url, init] = globalThis.fetch.mock.calls[0];
    const requestUrl = new URL(url);
    expect(requestUrl.pathname).toBe('/me');
    expect(requestUrl.searchParams.get('limit')).toBe('2');
    expect(requestUrl.searchParams.get('source')).toBe('KDDF');
    expect(init.headers.get('Authorization')).toBe('Bearer token-123');
    expect(init.headers.get('X-User-Locale')).toBe('ko-KR');
    expect(init.headers.get('X-Output-Language')).toBe('ko');
    expect(init.headers.get('X-Request-ID')).toBeTruthy();
  });

  it('builds API URLs for streaming clients', () => {
    const url = new URL(buildApiUrl('/jobs/job-1/events', { stream: true }));

    expect(url.origin).toMatch(/^http:\/\/(localhost|127\.0\.0\.1):\d+$/);
    expect(url.pathname).toBe('/jobs/job-1/events');
    expect(url.searchParams.get('stream')).toBe('true');
  });

  it('logs token lookup errors and keeps the request moving', async () => {
    const tokenError = new Error('token failed');
    authMock.currentUser = {
      getIdToken: vi.fn().mockRejectedValue(tokenError),
    };
    globalThis.fetch.mockResolvedValueOnce(jsonResponse({ ok: true }));

    await api.get('/me');

    const [, init] = globalThis.fetch.mock.calls[0];
    expect(init.headers.has('Authorization')).toBe(false);
    expect(init.headers.get('X-User-Locale')).toBe('ko-KR');
    expect(init.headers.get('X-Output-Language')).toBe('ko');
    expect(console.error).toHaveBeenCalledWith('Failed to get ID token:', tokenError);
  });

  it('lets fetch set multipart boundaries for form uploads', async () => {
    globalThis.fetch.mockResolvedValueOnce(jsonResponse({ ok: true }));
    const formData = new FormData();
    formData.append('file', new File(['paper'], 'paper.pdf'));

    await api.post('/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });

    const [, init] = globalThis.fetch.mock.calls[0];
    expect(init.body).toBe(formData);
    expect(init.headers.has('Content-Type')).toBe(false);
  });

  it('logs API failures and rethrows them', async () => {
    globalThis.fetch.mockResolvedValueOnce(jsonResponse(
      { detail: 'failed' },
      { status: 500, headers: { 'X-Request-ID': 'support-123' } },
    ));

    let thrown;
    await api.get('/broken').catch((error) => {
      thrown = error;
    });

    expect(thrown).toBeInstanceOf(ApiError);
    expect(thrown.requestId).toBe('support-123');
    expect(formatApiError(thrown, 'Fallback')).toBe('failed (support id: support-123)');
    expect(console.error).toHaveBeenCalledWith(
      'API Error:',
      expect.objectContaining({
        status: 500,
        data: { detail: 'failed' },
      }),
    );
  });

  it('preserves caller-provided request ids', async () => {
    globalThis.fetch.mockResolvedValueOnce(jsonResponse({ ok: true }));

    await api.get('/me', { headers: { 'X-Request-ID': 'manual-trace-1' } });

    const [, init] = globalThis.fetch.mock.calls[0];
    expect(init.headers.get('X-Request-ID')).toBe('manual-trace-1');
  });
});
