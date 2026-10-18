import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_BASE || '/api';

const client = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
});

client.interceptors.request.use((config) => {
  const token = localStorage.getItem('bugsight_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// When the short-lived access token expires, the API returns 401 on every
// call. Previously nothing handled that, so the app just went silently dead
// after ~15 minutes. Now: try a silent refresh once, replay the request, and
// only force a logout if the refresh itself fails (refresh token expired/revoked).
let refreshPromise = null;

function forceLogout() {
  localStorage.removeItem('bugsight_token');
  localStorage.removeItem('bugsight_refresh_token');
  localStorage.removeItem('bugsight_user');
  window.dispatchEvent(new Event('bugsight:session-expired'));
}

async function refreshAccessToken() {
  const refreshToken = localStorage.getItem('bugsight_refresh_token');
  if (!refreshToken) throw new Error('No refresh token');
  const res = await axios.post(`${API_BASE}/auth/refresh`, null, {
    headers: { Authorization: `Bearer ${refreshToken}` },
  });
  const newToken = res.data.token;
  localStorage.setItem('bugsight_token', newToken);
  return newToken;
}

client.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true;
      try {
        // Coalesce concurrent refresh calls into a single request.
        refreshPromise = refreshPromise || refreshAccessToken().finally(() => {
          refreshPromise = null;
        });
        const newToken = await refreshPromise;
        original.headers.Authorization = `Bearer ${newToken}`;
        return client(original);
      } catch (refreshError) {
        forceLogout();
        return Promise.reject(refreshError);
      }
    }
    return Promise.reject(error);
  }
);

export const api = {
  login: (email, password) =>
    client.post('/auth/login', { email, password }).then(r => r.data),
  register: (email, name, password) =>
    client.post('/auth/register', { email, name, password }).then(r => r.data),
  health: () => client.get('/health').then(r => r.data),
  metrics: () => client.get('/metrics').then(r => r.data),
  predict: (file, confidence = 0.25) => {
    const form = new FormData();
    form.append('image', file);
    form.append('confidence', confidence);
    return client.post('/predict', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then(r => r.data);
  },
  predictVideo: (file, confidence = 0.25, maxFrames = 60, { onUploadProgress, signal } = {}) => {
    const form = new FormData();
    form.append('video', file);
    form.append('confidence', confidence);
    form.append('max_frames', maxFrames);
    return client.post('/predict-video', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 300000,
      onUploadProgress,
      signal,
    }).then(r => r.data);
  },
  history: (params = {}) => client.get('/history', { params }).then(r => r.data),
  deleteAnalysis: (id) => client.delete(`/history/${id}`).then(r => r.data),
  stats: () => client.get('/stats').then(r => r.data),
  adminOverview: () => client.get('/admin/overview').then(r => r.data),
  adminUsers: () => client.get('/admin/users').then(r => r.data),
  adminAnalyses: () => client.get('/admin/analyses').then(r => r.data),
  adminSystem: () => client.get('/admin/system').then(r => r.data),
  adminUpdateRole: (userId, role) =>
    client.patch(`/admin/users/${userId}/role`, { role }).then(r => r.data),
  adminDeleteUser: (userId) => client.delete(`/admin/users/${userId}`).then(r => r.data),

  report: (videoResult = null, lang = 'en') => {
    const params = new URLSearchParams({ lang });
    if (videoResult) params.set('include_video', 'true');
    const url = `/report?${params}`;
    // Routed through the axios `client` (not raw fetch) so the 401 -> silent
    // refresh -> retry interceptor above also covers this call.
    return client.get(url, { responseType: 'blob' }).then((r) => {
      const blobUrl = URL.createObjectURL(r.data);
      const a = document.createElement('a');
      a.href = blobUrl;
      a.download = `bugsight_report.pdf`;
      a.click();
      URL.revokeObjectURL(blobUrl);
    });
  },
};