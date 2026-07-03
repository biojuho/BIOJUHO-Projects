import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest';

import api, { productApi, qrVerifyApi, resolveApiBaseUrl } from './api';

const API_URL = resolveApiBaseUrl();

const server = setupServer(
  http.get(`${API_URL}/products/:id`, ({ params }) => {
    const { id } = params;

    if (id === '1') {
      return HttpResponse.json({ id: '1', title: 'Success Product' }, { status: 200 });
    }
    if (id === 'invalid') {
      return HttpResponse.json({ message: 'Invalid ID format' }, { status: 400 });
    }
    return HttpResponse.json({ message: 'Internal Server Error' }, { status: 500 });
  }),
  http.get(`${API_URL}/api/qr/:qrToken/verify`, ({ params, request }) => {
    const url = new URL(request.url);

    return HttpResponse.json({
      qrToken: params.qrToken,
      sessionId: url.searchParams.get('session_id'),
      source: url.searchParams.get('source'),
      variantId: url.searchParams.get('variant_id'),
    });
  }),
);

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('api base URL', () => {
  it('defaults to the same-origin API proxy when no explicit URL is configured', () => {
    expect(resolveApiBaseUrl()).toBe('/api');
    expect(api.defaults.baseURL).toBe('/api');
  });
});

describe('productApi', () => {
  it('returns product data for successful responses', async () => {
    const response = await productApi.getById('1');

    expect(response.status).toBe(200);
    expect(response.data.title).toBe('Success Product');
  });

  it('surfaces validation errors from the backend', async () => {
    await expect(productApi.getById('invalid')).rejects.toMatchObject({
      response: {
        status: 400,
        data: { message: 'Invalid ID format' },
      },
    });
  });

  it('surfaces server errors from the backend', async () => {
    await expect(productApi.getById('error_trigger')).rejects.toMatchObject({
      response: {
        status: 500,
        data: { message: 'Internal Server Error' },
      },
    });
  });
});

describe('qrVerifyApi', () => {
  it('keeps the backend public QR route behind the same-origin API proxy', async () => {
    const response = await qrVerifyApi.verify('token-123', {
      sessionId: 'session-123',
      source: 'browser_smoke',
      variantId: 'qr_page_v2',
    });

    expect(response.data).toEqual({
      qrToken: 'token-123',
      sessionId: 'session-123',
      source: 'browser_smoke',
      variantId: 'qr_page_v2',
    });
  });
});
