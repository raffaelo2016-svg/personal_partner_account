import { createBrowserRouter, Navigate } from 'react-router';
import AuthGuard from './guards/AuthGuard';
import RoleGuard from './guards/RoleGuard';
import Layout from './pages/Layout';
import Dashboard from './pages/Dashboard';
import NotFound from './pages/NotFound';
import Login from './pages/Login';
import AdminLayout from './pages/AdminLayout';

const lazyPage = (loader: () => Promise<{ default: React.ComponentType }>) => async () => ({
  Component: (await loader()).default,
});

export const router = createBrowserRouter([
  {
    path: '/',
    element: <Navigate to="/login" replace />,
  },
  {
    path: '/login',
    Component: Login,
  },
  {
    path: '/register',
    lazy: async () => {
      const AdminAddPartner = (await import('./pages/AdminAddPartner')).default;
      return {
        element: (
          <div className="min-h-screen bg-gray-50">
            <div className="max-w-5xl mx-auto px-4 py-8">
              <AdminAddPartner />
            </div>
          </div>
        ),
      };
    },
  },
  {
    path: '/dashboard',
    Component: AuthGuard,
    children: [
      {
        element: <RoleGuard allowedRoles={['partner']} />,
        Component: Layout,
        children: [
          { index: true, Component: Dashboard },
          { path: 'clients', lazy: lazyPage(() => import('./pages/ClientsList')) },
          { path: 'clients/new', lazy: lazyPage(() => import('./pages/ClientForm')) },
          { path: 'clients/:id', lazy: lazyPage(() => import('./pages/ClientDetails')) },
          { path: 'clients/:id/edit', lazy: lazyPage(() => import('./pages/ClientForm')) },
          { path: 'clients/:id/progress', lazy: lazyPage(() => import('./pages/ClientProgress')) },
          { path: 'chat', lazy: lazyPage(() => import('./pages/Chat')) },
          { path: 'tasks', lazy: lazyPage(() => import('./pages/TasksList')) },
          { path: 'training', lazy: lazyPage(() => import('./pages/Training')) },
          { path: 'finance/court-fees', lazy: lazyPage(() => import('./pages/CourtFees')) },
          { path: 'finance/history', lazy: lazyPage(() => import('./pages/FinanceHistory')) },
          { path: 'settings', lazy: lazyPage(() => import('./pages/PartnerSettings')) },
        ],
      },
    ],
  },
  {
    path: '/admin',
    Component: AuthGuard,
    children: [
      {
        element: <RoleGuard allowedRoles={['admin']} />,
        Component: AdminLayout,
        children: [
          { index: true, lazy: lazyPage(() => import('./pages/AdminDashboard')) },
          { path: 'partners', lazy: lazyPage(() => import('./pages/AdminPartners')) },
          { path: 'partners/:id', lazy: lazyPage(() => import('./pages/AdminPartnerDetails')) },
          { path: 'clients', lazy: lazyPage(() => import('./pages/AdminClients')) },
          { path: 'clients/:id', lazy: lazyPage(() => import('./pages/AdminDebtorDetails')) },
          { path: 'debtors/:id', lazy: lazyPage(() => import('./pages/AdminDebtorDetails')) },
          { path: 'tasks', lazy: lazyPage(() => import('./pages/AdminTasks')) },
          { path: 'transactions', lazy: lazyPage(() => import('./pages/AdminTransactions')) },
          { path: 'chat', lazy: lazyPage(() => import('./pages/AdminChat')) },
          { path: 'settings', lazy: lazyPage(() => import('./pages/AdminSettings')) },
        ],
      },
    ],
  },
  {
    path: '*',
    Component: NotFound,
  },
]);
