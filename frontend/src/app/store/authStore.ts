import { useState, useEffect } from 'react';
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface AuthUser {
  id: string;
  email: string;
  role: 'partner' | 'admin' | 'super_admin';
}

interface AuthState {
  user: AuthUser | null;
  accessToken: string | null;

  login: (user: AuthUser, accessToken: string) => void;
  logout: () => void;
  setAccessToken: (token: string) => void;
}

const SESSION_FLAG = 'hasSession';

export function hasActiveSessionFlag(): boolean {
  try {
    return localStorage.getItem(SESSION_FLAG) === '1';
  } catch {
    return false;
  }
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      accessToken: null,

      login: (user, accessToken) => {
        try { localStorage.setItem(SESSION_FLAG, '1'); } catch { /* noop */ }
        set({ user, accessToken });
      },

      logout: () => {
        try { localStorage.removeItem(SESSION_FLAG); } catch { /* noop */ }
        set({ user: null, accessToken: null });
      },

      setAccessToken: (token) => set({ accessToken: token }),
    }),
    {
      name: 'auth-storage',
      // Не сохраняем user/role на клиенте: роль должна приходить от бэка
      // при каждом старте сессии (refresh → /auth/me), иначе пользователь
      // может подделать role через DevTools → localStorage.
      partialize: () => ({}),
    },
  ),
);

export function useHasHydrated() {
  const [hydrated, setHydrated] = useState(false);
  useEffect(() => {
    const unsub = useAuthStore.persist.onFinishHydration(() => setHydrated(true));
    if (useAuthStore.persist.hasHydrated()) setHydrated(true);
    return unsub;
  }, []);
  return hydrated;
}
