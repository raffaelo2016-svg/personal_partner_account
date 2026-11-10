import { createBrowserRouter, Navigate } from 'react-router';
import AuthGuard from './guards/AuthGuard';
import RoleGuard from './guards/RoleGuard';
import Layout from './pages/Layout';
import Dashboard from './pages/Dashboard';
import NotFound from './pages/NotFound';
import Login from './pages/Login';
import AdminLayout from './pages/AdminLayout';
import AgentLayout from './pages/agent/AgentLayout';
import RouteErrorPage from './pages/RouteErrorPage';

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
    lazy: lazyPage(() => import('./pages/Registration')),
  },
  {
    path: '/become-agent',
    lazy: lazyPage(() => import('./pages/BecomeAgent')),
  },
  {
    path: '/setup',
    lazy: lazyPage(() => import('./pages/Setup')),
  },
  {
    path: '/invite/:token',
    lazy: lazyPage(() => import('./pages/InviteAccept')),
  },
  {
    path: '/forgot-password',
    lazy: lazyPage(() => import('./pages/ForgotPassword')),
  },
  {
    path: '/reset-password',
    lazy: lazyPage(() => import('./pages/ResetPassword')),
  },
  {
    path: '/agent',
    Component: AuthGuard,
    ErrorBoundary: RouteErrorPage,
    children: [
      {
        element: (
          <RoleGuard allowedRoles={['agent']}>
            <AgentLayout />
          </RoleGuard>
        ),
        children: [
          { index: true, lazy: lazyPage(() => import('./pages/agent/AgentDashboard')) },
          { path: 'partners', lazy: lazyPage(() => import('./pages/agent/AgentPartners')) },
          { path: 'accruals', lazy: lazyPage(() => import('./pages/agent/AgentAccruals')) },
          { path: 'payouts', lazy: lazyPage(() => import('./pages/agent/AgentPayouts')) },
          { path: 'requisites', lazy: lazyPage(() => import('./pages/agent/AgentRequisites')) },
          { path: 'materials', lazy: lazyPage(() => import('./pages/agent/AgentMaterials')) },
          { path: 'support', lazy: lazyPage(() => import('./pages/agent/AgentSupport')) },
        ],
      },
    ],
  },
  {
    path: '/dashboard',
    Component: AuthGuard,
    ErrorBoundary: RouteErrorPage,
    children: [
      {
        element: <RoleGuard allowedRoles={['partner']}><Layout /></RoleGuard>,
        children: [
          { index: true, Component: Dashboard },
          { path: 'sro', lazy: lazyPage(() => import('./pages/SroDetails')) },
          { path: 'clients', lazy: lazyPage(() => import('./pages/ClientsList')) },
          { path: 'clients/new', lazy: lazyPage(() => import('./pages/ClientForm')) },
          { path: 'clients/:id', lazy: lazyPage(() => import('./pages/ClientDetails')) },
          { path: 'clients/:id/edit', lazy: lazyPage(() => import('./pages/ClientForm')) },
          { path: 'clients/:id/documents', lazy: lazyPage(() => import('./pages/ClientDocuments')) },
          { path: 'clients/:id/progress', lazy: lazyPage(() => import('./pages/ClientProgress')) },
          { path: 'chat', lazy: lazyPage(() => import('./pages/Chat')) },
          { path: 'news', lazy: lazyPage(() => import('./pages/News')) },
          { path: 'news/:id', lazy: lazyPage(() => import('./pages/NewsDetail')) },
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
    ErrorBoundary: RouteErrorPage,
    children: [
      {
        element: <RoleGuard allowedRoles={['admin', 'super_admin']}><AdminLayout /></RoleGuard>,
        children: [
          { index: true, lazy: lazyPage(() => import('./pages/AdminDashboard')) },
          { path: 'partners', lazy: lazyPage(() => import('./pages/AdminPartners')) },
          { path: 'partners/without-clients', lazy: lazyPage(() => import('./pages/AdminPartnersWithoutClients')) },
          { path: 'partners/new', lazy: lazyPage(() => import('./pages/AdminAddPartner')) },
          { path: 'partners/:id', lazy: lazyPage(() => import('./pages/AdminPartnerDetails')) },
          { path: 'clients', lazy: lazyPage(() => import('./pages/AdminClients')) },
          { path: 'clients/:id', lazy: lazyPage(() => import('./pages/AdminDebtorDetails')) },
          { path: 'clients/:id/documents', lazy: lazyPage(() => import('./pages/ClientDocuments')) },
          { path: 'debtors/:id', lazy: lazyPage(() => import('./pages/AdminDebtorDetails')) },
          { path: 'tasks', lazy: lazyPage(() => import('./pages/AdminTasks')) },
          { path: 'bitrix-attention', lazy: lazyPage(() => import('./pages/AdminBitrixAttention')) },
          { path: 'transactions', lazy: lazyPage(() => import('./pages/AdminTransactions')) },
          { path: 'chat', lazy: lazyPage(() => import('./pages/AdminChat')) },
          { path: 'documents-inbox', lazy: lazyPage(() => import('./pages/AdminChatDocuments')) },
          { path: 'news', lazy: lazyPage(() => import('./pages/AdminNews')) },
          { path: 'settings', lazy: lazyPage(() => import('./pages/AdminSettings')) },
          { path: 'agents', lazy: lazyPage(() => import('./pages/AdminAgents')) },
          { path: 'admins', lazy: lazyPage(() => import('./pages/AdminAdmins')) },
        ],
      },
    ],
  },
  {
    path: '*',
    Component: NotFound,
  },
]);
