import axios from "axios";
import { auth } from '../firebase';
import { getStoredLocale, getStoredOutputLanguage } from "../contexts/LocaleContext";

// Create an Axios instance with default configuration
const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "http://localhost:8000",
  timeout: 30000,
  headers: {
    "Content-Type": "application/json",
  },
});

function setAuthorizationHeader(headers, token) {
  if (typeof headers?.set === "function") {
    headers.set("Authorization", `Bearer ${token}`);
    return headers;
  }

  return {
    ...(headers ?? {}),
    Authorization: `Bearer ${token}`,
  };
}

function setRequestHeader(headers, name, value) {
  if (typeof headers?.set === "function") {
    headers.set(name, value);
    return headers;
  }

  return {
    ...(headers ?? {}),
    [name]: value,
  };
}

// Add a request interceptor (useful for auth tokens later)
api.interceptors.request.use(
  async (config) => {
    const user = auth.currentUser;
    const locale = getStoredLocale();
    const outputLanguage = getStoredOutputLanguage();
    config.headers = setRequestHeader(config.headers, "X-User-Locale", locale);
    config.headers = setRequestHeader(config.headers, "X-Output-Language", outputLanguage);
    if (user) {
      try {
        const token = await user.getIdToken();
        config.headers = setAuthorizationHeader(config.headers, token);
      } catch (error) {
        console.error('Failed to get ID token:', error);
      }
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Add a response interceptor (useful for global error handling)
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const status = error.response?.status;

    // 429 Rate Limit — Retry-After 헤더 기반 재시도 (1회)
    if (status === 429 && !error.config._retried) {
      error.config._retried = true;
      const retryAfter = parseInt(error.response.headers["retry-after"], 10) || 2;
      const delay = Math.min(retryAfter, 10) * 1000;
      await new Promise((r) => setTimeout(r, delay));
      return api(error.config);
    }

    console.error("API Error:", error.response || error.message);
    return Promise.reject(error);
  },
);

export default api;
