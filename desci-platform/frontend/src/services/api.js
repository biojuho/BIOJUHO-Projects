import axios from "axios";

// Create an Axios instance with default configuration
const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "http://localhost:8001",
  headers: {
    "Content-Type": "application/json",
  },
});

import { auth } from '../firebase';

// Add a request interceptor (useful for auth tokens later)
api.interceptors.request.use(
  async (config) => {
    const user = auth.currentUser;
    if (user) {
      try {
        const token = await user.getIdToken();
        config.headers.Authorization = `Bearer ${token}`;
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
  (error) => {
    // Handle specific error codes or log errors
    console.error("API Error:", error.response || error.message);
    return Promise.reject(error);
  },
);

export default api;
