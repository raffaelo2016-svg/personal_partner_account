import { useEffect, useState } from 'react';
import { Navigate, Outlet } from 'react-router';
import { useAuthStore, useHasHydrated, hasActiveSessionFlag } from '@/app/store/authStore';
import { refreshApi, getMeApi } from '@/app/api/auth';

type Bootstrap = 'idle' | 'loading' | 'done' | 'failed';

function Spinner() {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
    </div>
  );
}

export default function AuthGuard() {
  const hydrated = useHasHydrated();
  const accessToken = useAuthStore((s) => s.accessToken);
  const user = useAuthStore((s) => s.user);
  const login = useAuthStore((s) => s.login);
  const setAccessToken = useAuthStore((s) => s.setAccessToken);
  const logout = useAuthStore((s) => s.logout);
  const [bootstrap, setBootstrap] = useState<Bootstrap>('idle');

  useEffect(() => {
    if (!hydrated || bootstrap !== 'idle') return;

    // Уже залогинены и user подгружен — ничего не делаем.
    if (accessToken && user) {
      setBootstrap('done');
      return;
    }

    // Есть accessToken, но нет user — подтягиваем /auth/me.
    if (accessToken && !user) {
      setBootstrap('loading');
      getMeApi()
        .then((me) => {
          login({ id: me.id, email: me.email, role: me.role }, accessToken);
          setBootstrap('done');
        })
        .catch(() => {
          logout();
          setBootstrap('failed');
        });
      return;
    }

    // Нет accessToken и нет отметки об активной сессии — не пытаемся
    // refresh: иначе после logout отозванный cookie всё равно даст 401,
    // но браузер зря отправит запрос и добавит задержку.
    if (!hasActiveSessionFlag()) {
      setBootstrap('failed');
      return;
    }

    // Нет accessToken — пробуем refresh по HttpOnly cookie, затем /auth/me.
    setBootstrap('loading');
    refreshApi()
      .then(async ({ access_token }) => {
        setAccessToken(access_token);
        const me = await getMeApi();
        login({ id: me.id, email: me.email, role: me.role }, access_token);
        setBootstrap('done');
      })
      .catch(() => {
        logout();
        setBootstrap('failed');
      });
  }, [hydrated, accessToken, user, bootstrap, login, setAccessToken, logout]);

  if (!hydrated || bootstrap === 'idle' || bootstrap === 'loading') {
    return <Spinner />;
  }

  if (!accessToken || !user) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}
