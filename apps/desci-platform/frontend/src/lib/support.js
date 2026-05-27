export function createSupportId(prefix = 'web') {
  if (globalThis.crypto?.randomUUID) {
    return `${prefix}-${globalThis.crypto.randomUUID()}`;
  }
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

export function readResponseHeader(headers, name) {
  if (!headers) return null;
  if (typeof headers.get === 'function') {
    return headers.get(name) || headers.get(name.toLowerCase()) || headers.get(name.toUpperCase());
  }
  const headerName = name.toLowerCase();
  const entry = Object.entries(headers).find(([key]) => key.toLowerCase() === headerName);
  return entry?.[1] || null;
}

export function getErrorRequestId(error) {
  return error?.requestId
    || error?.response?.data?.request_id
    || readResponseHeader(error?.response?.headers, 'x-request-id')
    || null;
}

export function getErrorDetail(error, fallback = 'Request failed') {
  const detail = error?.response?.data?.detail;
  if (typeof detail === 'string' && detail.trim()) {
    return detail;
  }
  if (typeof error?.message === 'string' && error.message.trim()) {
    return error.message;
  }
  return fallback;
}

export function formatSupportError(error, fallback = 'Request failed') {
  const message = getErrorDetail(error, fallback);
  const requestId = getErrorRequestId(error);
  return requestId ? `${message} (support id: ${requestId})` : message;
}
