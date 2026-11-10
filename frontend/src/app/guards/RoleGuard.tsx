import type { ReactNode } from 'react';
import { Navigate, Outlet } from 'react-router';
import { useAuthStore, useHasHydrated } from '@/app/store/authStore';

type AppRole = 'partner' | 'admin' | 'super_admin' | 'agent';

interface RoleGuardProps {
  allowedRoles: AppRole[];
  children?: ReactNode;
}

export default function RoleGuard({ allowedRoles, children }: RoleGuardProps) {
  const hydrated = useHasHydrated();
  const user = useAuthStore((s) => s.user);

  if (!hydrated) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  if (!allowedRoles.includes(user.role)) {
    const isAdmin = user.role === 'admin' || user.role === 'super_admin';
    const redirect =
      user.role === 'agent' ? '/agent' : isAdmin ? '/admin' : '/dashboard';
    return <Navigate to={redirect} replace />;
  }

  return children ?? <Outlet />;
}
