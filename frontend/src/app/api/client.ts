import axios from 'axios';
import { useAuthStore } from '@/app/store/authStore';

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1',
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true,
});

apiClient.interceptors.request.use((config) => {
  const token = useAuthStore.getState().accessToken;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

let isRefreshing = false;
let refreshSubscribers: ((token: string) => void)[] = [];

function onRefreshed(token: string) {
  refreshSubscribers.forEach((cb) => cb(token));
  refreshSubscribers = [];
}

function addRefreshSubscriber(cb: (token: string) => void) {
  refreshSubscribers.push(cb);
}

type RefreshMessage =
  | { type: 'refresh-start' }
  | { type: 'refresh-success'; token: string }
  | { type: 'refresh-fail' };

const refreshChannel: BroadcastChannel | null =
  typeof BroadcastChannel !== 'undefined' ? new BroadcastChannel('auth-refresh') : null;

function waitForExternalRefresh(timeoutMs = 10000): Promise<string | null> {
  if (!refreshChannel) return Promise.resolve(null);
  return new Promise((resolve) => {
    const timer = setTimeout(() => {
      refreshChannel.removeEventListener('message', handler);
      resolve(null);
    }, timeoutMs);
    const handler = (ev: MessageEvent<RefreshMessage>) => {
      if (ev.data.type === 'refresh-success') {
        clearTimeout(timer);
        refreshChannel.removeEventListener('message', handler);
        resolve(ev.data.token);
      } else if (ev.data.type === 'refresh-fail') {
        clearTimeout(timer);
        refreshChannel.removeEventListener('message', handler);
        resolve(null);
      }
    };
    refreshChannel.addEventListener('message', handler);
  });
}

if (refreshChannel) {
  refreshChannel.addEventListener('message', (ev: MessageEvent<RefreshMessage>) => {
    if (ev.data.type === 'refresh-success') {
      useAuthStore.getState().setAccessToken(ev.data.token);
      onRefreshed(ev.data.token);
    } else if (ev.data.type === 'refresh-fail') {
      useAuthStore.getState().logout();
    }
  });
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    const code =
      error.response?.data?.code ||
      error.response?.headers?.code;

    if (error.response?.status !== 401 || originalRequest._retry) {
      return Promise.reject(error);
    }

    // Wrong password / invalid credentials — just propagate, don't refresh
    if (code === 'INVALID_CREDENTIALS') {
      return Promise.reject(error);
    }

    // Not authenticated at all — no user in store, don't attempt refresh
    if (!useAuthStore.getState().user) {
      return Promise.reject(error);
    }

    // Another refresh is already in flight (this tab) — queue this request
    if (isRefreshing) {
      return new Promise((resolve, reject) => {
        addRefreshSubscriber((token: string) => {
          if (!token) {
            reject(error);
            return;
          }
          originalRequest.headers.Authorization = `Bearer ${token}`;
          resolve(apiClient(originalRequest));
        });
      });
    }

    // Try to refresh the access token
    originalRequest._retry = true;
    isRefreshing = true;
    refreshChannel?.postMessage({ type: 'refresh-start' } satisfies RefreshMessage);

    try {
      const { data } = await axios.post(
        `${apiClient.defaults.baseURL}/auth/refresh`,
        {},
        { withCredentials: true },
      );

      const newToken = data.access_token;
      useAuthStore.getState().setAccessToken(newToken);
      originalRequest.headers.Authorization = `Bearer ${newToken}`;
      onRefreshed(newToken);
      refreshChannel?.postMessage({ type: 'refresh-success', token: newToken } satisfies RefreshMessage);
      return apiClient(originalRequest);
    } catch {
      // Another tab may have already rotated the refresh token — wait briefly for its broadcast
      const externalToken = await waitForExternalRefresh(2000);
      if (externalToken) {
        onRefreshed(externalToken);
        originalRequest.headers.Authorization = `Bearer ${externalToken}`;
        return apiClient(originalRequest);
      }
      // Разбудим подписчиков пустым токеном, чтобы их промисы не висли до таймаута.
      onRefreshed('');
      refreshChannel?.postMessage({ type: 'refresh-fail' } satisfies RefreshMessage);
      try {
        await axios.post(
          `${apiClient.defaults.baseURL}/auth/logout`,
          {},
          { withCredentials: true },
        );
      } catch { /* best-effort server-side revoke */ }
      useAuthStore.getState().logout();
      window.location.href = '/login';
      return Promise.reject(error);
    } finally {
      isRefreshing = false;
    }
  },
);

export default apiClient;
