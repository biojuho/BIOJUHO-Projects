import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8002';

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

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
