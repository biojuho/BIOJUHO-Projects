import { beforeEach, describe, expect, it, vi } from 'vitest';

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

const { default: api } = await import('./api');

describe('api interceptors', () => {
  beforeEach(() => {
    authMock.currentUser = null;
    vi.restoreAllMocks();
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  it('adds bearer token to plain object headers', async () => {
    authMock.currentUser = {
      getIdToken: vi.fn().mockResolvedValue('token-123'),
    };

    const requestHandler = api.interceptors.request.handlers[0].fulfilled;
    const config = await requestHandler({ headers: {} });

    expect(config.headers.Authorization).toBe('Bearer token-123');
    expect(config.headers['X-User-Locale']).toBe('ko-KR');
    expect(config.headers['X-Output-Language']).toBe('ko');
  });

  it('uses header.set when axios headers object is provided', async () => {
    const setHeader = vi.fn();
    authMock.currentUser = {
      getIdToken: vi.fn().mockResolvedValue('token-456'),
    };

    const requestHandler = api.interceptors.request.handlers[0].fulfilled;
    const headers = { set: setHeader };
    const config = await requestHandler({ headers });

    expect(setHeader).toHaveBeenCalledWith('X-User-Locale', 'ko-KR');
    expect(setHeader).toHaveBeenCalledWith('X-Output-Language', 'ko');
    expect(setHeader).toHaveBeenCalledWith('Authorization', 'Bearer token-456');
    expect(config.headers).toBe(headers);
  });

  it('logs token lookup errors and keeps the request moving', async () => {
    const tokenError = new Error('token failed');
    authMock.currentUser = {
      getIdToken: vi.fn().mockRejectedValue(tokenError),
    };

    const requestHandler = api.interceptors.request.handlers[0].fulfilled;
    const config = await requestHandler({ headers: {} });

    expect(config.headers.Authorization).toBeUndefined();
    expect(config.headers['X-User-Locale']).toBe('ko-KR');
    expect(config.headers['X-Output-Language']).toBe('ko');
    expect(console.error).toHaveBeenCalledWith('Failed to get ID token:', tokenError);
  });

  it('logs API failures and rethrows them', async () => {
    const responseError = { response: { status: 500 } };
    const responseHandler = api.interceptors.response.handlers[0].rejected;

    await expect(responseHandler(responseError)).rejects.toBe(responseError);
    expect(console.error).toHaveBeenCalledWith('API Error:', responseError.response);
  });
});
