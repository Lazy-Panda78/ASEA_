import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
});

// Add a request interceptor to inject the token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('asea_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

export const login = async (username, password) => {
  const response = await api.post('/auth/token/', { username, password });
  localStorage.setItem('asea_token', response.data.access);
  return response.data;
};

export const submitVerification = async (repoUrl, prNumber) => {
  const res = await api.post('/verify/submit', { repoUrl, prNumber: parseInt(prNumber, 10) });
  return res.data;
};

export const scanVerification = async (runId) => {
  const res = await api.post(`/verify/${runId}/scan`);
  return res.data;
};

export const checkArchitecture = async (runId) => {
  const res = await api.post(`/verify/${runId}/architecture`);
  return res.data;
};

export const scoreVerification = async (runId) => {
  const res = await api.post(`/verify/${runId}/score`);
  return res.data;
};

export const getAuditTrail = async (runId) => {
  const res = await api.get(`/verify/${runId}/audit`);
  return res.data;
};

export default api;
