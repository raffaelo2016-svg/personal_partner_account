const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

export function buildWsUrl(path: string): string {
  const api = new URL(API_URL, window.location.origin);
  const protocol = api.protocol === 'https:' ? 'wss:' : 'ws:';
  const basePath = api.pathname.replace(/\/$/, '');
  const suffix = path.startsWith('/') ? path : `/${path}`;
  return `${protocol}//${api.host}${basePath}${suffix}`;
}
