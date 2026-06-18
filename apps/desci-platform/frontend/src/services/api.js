import { auth } from '../firebase';
import { getStoredLocale, getStoredOutputLanguage } from "../contexts/LocaleContext";
import { createSupportId, formatSupportError, readResponseHeader } from '../lib/support';

const API_BASE_URL = import.meta.env?.VITE_API_BASE_URL || "http://127.0.0.1:8000";
const DEFAULT_TIMEOUT_MS = 30_000;

export class ApiError extends Error {
  constructor(message, { status, data, headers }) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.requestId = readResponseHeader(headers, "x-request-id") || data?.request_id || null;
    this.responseTimeMs = readResponseHeader(headers, "x-response-time-ms") || null;
    this.response = { status, data, headers };
  }
}

export function formatApiError(error, fallback = "Request failed") {
  return formatSupportError(error, fallback);
}

function isFormData(value) {
  return typeof FormData !== "undefined" && value instanceof FormData;
}

function isUrlSearchParams(value) {
  return typeof URLSearchParams !== "undefined" && value instanceof URLSearchParams;
}

function isBinaryBody(value) {
  return (
    (typeof Blob !== "undefined" && value instanceof Blob)
    || (typeof ArrayBuffer !== "undefined" && value instanceof ArrayBuffer)
  );
}

function appendParams(url, params = {}) {
  Object.entries(params ?? {}).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") return;

    if (Array.isArray(value)) {
      value.forEach((item) => {
        if (item !== undefined && item !== null && item !== "") {
          url.searchParams.append(key, String(item));
        }
      });
      return;
    }

    url.searchParams.append(key, String(value));
  });
}

function buildUrl(path, params) {
  const baseUrl = API_BASE_URL.endsWith("/") ? API_BASE_URL : `${API_BASE_URL}/`;
  const url = new URL(path, baseUrl);
  appendParams(url, params);
  return url.toString();
}

export function buildApiUrl(path, params) {
  return buildUrl(path, params);
}

async function buildHeaders(inputHeaders = {}, body) {
  const headers = new Headers(inputHeaders);
  headers.set("X-User-Locale", getStoredLocale());
  headers.set("X-Output-Language", getStoredOutputLanguage());
  if (!headers.has("X-Request-ID")) {
    headers.set("X-Request-ID", createSupportId("web"));
  }

  if (isFormData(body)) {
    headers.delete("Content-Type");
  } else if (body !== undefined && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const user = auth.currentUser;
  if (user) {
    try {
      const token = await user.getIdToken();
      headers.set("Authorization", `Bearer ${token}`);
    } catch (error) {
      console.error("Failed to get ID token:", error);
    }
  }

  return headers;
}

function buildBody(data, method) {
  if (["GET", "HEAD"].includes(method) || data === undefined || data === null) {
    return undefined;
  }

  if (isFormData(data) || isUrlSearchParams(data) || isBinaryBody(data) || typeof data === "string") {
    return data;
  }

  return JSON.stringify(data);
}

function createAbortSignal(externalSignal, timeoutMs) {
  const controller = new AbortController();
  let timeoutId;

  const abortFromExternal = () => {
    controller.abort(externalSignal.reason);
  };

  if (externalSignal?.aborted) {
    controller.abort(externalSignal.reason);
  } else if (externalSignal) {
    externalSignal.addEventListener("abort", abortFromExternal, { once: true });
  }

  if (timeoutMs > 0) {
    timeoutId = globalThis.setTimeout(() => {
      controller.abort(new DOMException("Request timed out", "TimeoutError"));
    }, timeoutMs);
  }

  return {
    signal: controller.signal,
    cleanup() {
      if (timeoutId) globalThis.clearTimeout(timeoutId);
      externalSignal?.removeEventListener?.("abort", abortFromExternal);
    },
  };
}

async function parseResponse(response) {
  if (response.status === 204) return null;

  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return response.json();
  }

  const text = await response.text();
  return text.length > 0 ? text : null;
}

function wait(ms) {
  return new Promise((resolve) => globalThis.setTimeout(resolve, ms));
}

async function request(method, path, data, options = {}, retryState = { retried: false }) {
  const body = buildBody(data, method);
  const headers = await buildHeaders(options.headers, body);
  const { signal, cleanup } = createAbortSignal(options.signal, options.timeout ?? DEFAULT_TIMEOUT_MS);

  try {
    const response = await fetch(buildUrl(path, options.params), {
      method,
      headers,
      body,
      signal,
    });

    const responseData = await parseResponse(response);

    if (response.status === 429 && !retryState.retried) {
      const retryAfter = Number.parseInt(response.headers.get("retry-after") || "", 10) || 2;
      await wait(Math.min(retryAfter, 10) * 1000);
      return request(method, path, data, options, { retried: true });
    }

    if (!response.ok) {
      throw new ApiError(`API request failed with status ${response.status}`, {
        status: response.status,
        data: responseData,
        headers: response.headers,
      });
    }

    return {
      data: responseData,
      status: response.status,
      headers: response.headers,
      requestId: readResponseHeader(response.headers, "x-request-id"),
      responseTimeMs: readResponseHeader(response.headers, "x-response-time-ms"),
      ok: response.ok,
    };
  } catch (error) {
    if (error?.name !== "AbortError" && error?.name !== "TimeoutError") {
      console.error("API Error:", error.response || error.message || error);
    }
    throw error;
  } finally {
    cleanup();
  }
}

const api = {
  request,
  get(path, options) {
    return request("GET", path, undefined, options);
  },
  post(path, data, options) {
    return request("POST", path, data, options);
  },
  put(path, data, options) {
    return request("PUT", path, data, options);
  },
  patch(path, data, options) {
    return request("PATCH", path, data, options);
  },
  delete(path, options) {
    return request("DELETE", path, undefined, options);
  },
};

export default api;
