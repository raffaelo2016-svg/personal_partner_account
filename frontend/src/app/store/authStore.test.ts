import { beforeEach, describe, expect, it } from 'vitest';
import { useAuthStore, hasActiveSessionFlag, type AuthUser } from './authStore';

const PARTNER: AuthUser = { id: 'p1', email: 'p@example.com', role: 'partner' };
const ADMIN: AuthUser = { id: 'a1', email: 'a@example.com', role: 'admin' };

beforeEach(() => {
  localStorage.clear();
  useAuthStore.setState({ user: null, accessToken: null });
});

describe('useAuthStore', () => {
  it('начальное состояние без пользователя и токена', () => {
    const s = useAuthStore.getState();
    expect(s.user).toBeNull();
    expect(s.accessToken).toBeNull();
  });

  it('login выставляет user и accessToken', () => {
    useAuthStore.getState().login(PARTNER, 'tok-1');
    const s = useAuthStore.getState();
    expect(s.user).toEqual(PARTNER);
    expect(s.accessToken).toBe('tok-1');
  });

  it('login с ролью admin сохраняет role', () => {
    useAuthStore.getState().login(ADMIN, 'tok-2');
    expect(useAuthStore.getState().user?.role).toBe('admin');
  });

  it('logout очищает user и accessToken', () => {
    useAuthStore.getState().login(PARTNER, 'tok-1');
    useAuthStore.getState().logout();
    const s = useAuthStore.getState();
    expect(s.user).toBeNull();
    expect(s.accessToken).toBeNull();
  });

  it('setAccessToken меняет только токен, user сохраняется', () => {
    useAuthStore.getState().login(PARTNER, 'old');
    useAuthStore.getState().setAccessToken('new');
    const s = useAuthStore.getState();
    expect(s.accessToken).toBe('new');
    expect(s.user).toEqual(PARTNER);
  });

  it('persist не хранит ни user, ни accessToken (роль должна приходить от бэка)', () => {
    useAuthStore.getState().login(PARTNER, 'secret-token');

    const raw = localStorage.getItem('auth-storage');
    expect(raw).toBeTruthy();
    const parsed = JSON.parse(raw as string);
    // partialize: () => ({}) — ни user, ни accessToken не сохраняются.
    expect(parsed.state.user).toBeUndefined();
    expect(parsed.state.accessToken).toBeUndefined();
    expect(raw).not.toContain('secret-token');
    expect(raw).not.toContain('p@example.com');
  });

  it('login выставляет, а logout снимает флаг активной сессии', () => {
    expect(hasActiveSessionFlag()).toBe(false);
    useAuthStore.getState().login(PARTNER, 'tok');
    expect(hasActiveSessionFlag()).toBe(true);
    useAuthStore.getState().logout();
    expect(hasActiveSessionFlag()).toBe(false);
  });
});
