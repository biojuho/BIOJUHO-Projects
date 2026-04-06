import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8002';

const api = axios.create({
  baseURL: API_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 429 Rate Limit 재시도 (1회)
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 429 && !error.config._retried) {
      error.config._retried = true;
      const retryAfter = parseInt(error.response.headers['retry-after'], 10) || 2;
      await new Promise((r) => setTimeout(r, Math.min(retryAfter, 10) * 1000));
      return api(error.config);
    }
    return Promise.reject(error);
  },
);

export const productApi = {
  // Product Operations
  create: ({ owner_id, ...body }) => api.post('/products/', body, { params: { owner_id } }),
  getAll: () => api.get('/products/'),
  getById: (id) => api.get(`/products/${id}`),

  // Tracking & Blockchain (backend expects query params)
  addTracking: (id, data) => api.post(`/products/${id}/track`, null, { params: data }),
  getHistory: (id) => api.get(`/products/${id}/history`),

  // Certifications (backend expects query params)
  addCertification: (id, data) => api.post(`/products/${id}/certifications`, null, { params: data }),
};

export const userApi = {
  create: (data) => api.post('/users/', data),
};

export const analyticsApi = {
  trackQrEvent: (payload) => api.post('/qr-events', payload),
};

export default api;
