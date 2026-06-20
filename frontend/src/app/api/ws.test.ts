import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

describe('buildWsUrl', () => {
  const originalLocation = window.location;

  beforeEach(() => {
    vi.resetModules();
    Object.defineProperty(window, 'location', {
      value: { origin: 'http://localhost:5173' },
      writable: true,
    });
  });

  afterEach(() => {
    Object.defineProperty(window, 'location', { value: originalLocation, writable: true });
  });

  it('uses ws:// for http API and preserves base path', async () => {
    vi.stubEnv('VITE_API_URL', 'http://localhost:8000/api/v1');
    const { buildWsUrl } = await import('./ws');
    expect(buildWsUrl('/ws/chat')).toBe('ws://localhost:8000/api/v1/ws/chat');
  });

  it('uses wss:// for https API', async () => {
    vi.stubEnv('VITE_API_URL', 'https://api.example.com/v1');
    const { buildWsUrl } = await import('./ws');
    expect(buildWsUrl('/ws/chat')).toBe('wss://api.example.com/v1/ws/chat');
  });

  it('handles path without leading slash', async () => {
    vi.stubEnv('VITE_API_URL', 'http://localhost:8000/api/v1');
    const { buildWsUrl } = await import('./ws');
    expect(buildWsUrl('ws/chat')).toBe('ws://localhost:8000/api/v1/ws/chat');
  });

  it('strips trailing slash from API base to avoid double slash', async () => {
    vi.stubEnv('VITE_API_URL', 'http://localhost:8000/api/v1/');
    const { buildWsUrl } = await import('./ws');
    expect(buildWsUrl('/ws/chat')).toBe('ws://localhost:8000/api/v1/ws/chat');
  });

  it('falls back to default API URL when env is empty', async () => {
    vi.stubEnv('VITE_API_URL', '');
    const { buildWsUrl } = await import('./ws');
    expect(buildWsUrl('/ws/chat')).toBe('ws://localhost:8000/api/v1/ws/chat');
  });

  it('handles empty path (keeps trailing slash from normalized suffix)', async () => {
    vi.stubEnv('VITE_API_URL', 'http://localhost:8000/api/v1');
    const { buildWsUrl } = await import('./ws');
    expect(buildWsUrl('')).toBe('ws://localhost:8000/api/v1/');
  });

  it('handles non-default port', async () => {
    vi.stubEnv('VITE_API_URL', 'https://api.example.com:8443/v2');
    const { buildWsUrl } = await import('./ws');
    expect(buildWsUrl('/ws/x')).toBe('wss://api.example.com:8443/v2/ws/x');
  });
});
