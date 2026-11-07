import { useState } from 'react';
import { Outlet, Link, useNavigate, useLocation } from 'react-router';
import { AlertTriangle, LayoutDashboard, Users, Settings, LogOut, Shield, ShieldCheck, Menu, X, CheckSquare, MessageSquare, CreditCard, Newspaper, Handshake } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import logo from '@/assets/logo-white.svg';
import NotificationBell from '../components/NotificationBell';
import { useAuthStore } from '../store/authStore';
import { fetchAdminUnreadCount } from '../api/chat';
import { fetchBitrixAttention } from '../api/bitrixAttention';
import { fetchPartnerStats } from '../api/partners';

export default function AdminLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const logout = useAuthStore((s) => s.logout);
  const currentUser = useAuthStore((s) => s.user);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const { data: unreadCount = 0 } = useQuery({
    queryKey: ['adminUnreadCount'],
    queryFn: fetchAdminUnreadCount,
    refetchInterval: 15000,
  });

  const { data: attentionData } = useQuery({
    queryKey: ['adminBitrixAttentionCount'],
    queryFn: () => fetchBitrixAttention({ page_size: 1 }),
    refetchInterval: 30_000,
  });

  const { data: partnerStats } = useQuery({
    queryKey: ['admin', 'partners', 'stats'],
    queryFn: fetchPartnerStats,
    refetchInterval: 30_000,
  });

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const menuItems = [
    { icon: LayoutDashboard, label: 'Дашборд', path: '/admin' },
    {
      icon: Users,
      label: 'Партнеры',
      path: '/admin/partners',
      badge: partnerStats?.pending_partners ?? 0,
    },
    { icon: Handshake, label: 'Агенты', path: '/admin/agents' },
    { icon: Users, label: 'Все клиенты', path: '/admin/clients' },
    { icon: CheckSquare, label: 'Задачи', path: '/admin/tasks' },
    { icon: AlertTriangle, label: 'Требует внимания', path: '/admin/bitrix-attention', badge: attentionData?.total ?? 0 },
    { icon: CreditCard, label: 'Транзакции', path: '/admin/transactions' },
    { icon: MessageSquare, label: 'Чат', path: '/admin/chat', badge: unreadCount },
    { icon: Newspaper, label: 'Новости', path: '/admin/news' },
    ...(currentUser?.role === 'super_admin'
      ? [{ icon: ShieldCheck, label: 'Админы', path: '/admin/admins' }]
      : []),
    { icon: Settings, label: 'Настройки', path: '/admin/settings' },
  ];

  const isActive = (path: string) => {
    if (path === '/admin') return location.pathname === '/admin';
    return location.pathname.startsWith(path);
  };

  const sidebarContent = (
    <>
      <div className="p-4 border-b border-slate-700">
        <img src={logo} alt="ЮРИТЕХ" className="h-[50px] w-auto mx-auto" />
      </div>

      <div className="p-4 border-b border-slate-700">
        <div className="flex items-center gap-3">
          <div className="bg-slate-700 p-2 rounded-lg">
            <Shield className="w-6 h-6" />
          </div>
          <div>
            <h2 className="font-semibold">Администратор</h2>
            <p className="text-xs text-slate-400">Панель управления</p>
          </div>
        </div>
      </div>

      <nav className="flex-1 p-4 space-y-1">
        {menuItems.map((item) => {
          const active = isActive(item.path);
          const badge = 'badge' in item ? (item as { badge?: number }).badge : undefined;
          return (
            <Link
              key={item.path}
              to={item.path}
              onClick={() => setSidebarOpen(false)}
              className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
                active
                  ? 'bg-slate-700 text-white'
                  : 'text-slate-300 hover:bg-slate-700/50 hover:text-white'
              }`}
            >
              <item.icon className="w-5 h-5" />
              <span className="flex-1">{item.label}</span>
              {!!badge && badge > 0 && (
                <span className="bg-red-500 text-white text-xs rounded-full px-2 py-0.5 min-w-[20px] text-center">
                  {badge}
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      <div className="p-4 border-t border-slate-700">
        <button
          onClick={handleLogout}
          className="flex items-center gap-3 px-4 py-3 text-slate-300 hover:bg-slate-700/50 hover:text-white rounded-lg transition-colors w-full"
        >
          <LogOut className="w-5 h-5" />
          <span>Выйти</span>
        </button>
      </div>
    </>
  );

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
          role="presentation"
          aria-hidden="true"
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 w-64 bg-slate-800 text-white flex flex-col z-50 transform transition-transform duration-200 lg:translate-x-0 lg:static ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <button
          type="button"
          aria-label="Закрыть меню"
          className="absolute top-4 right-4 lg:hidden p-1 rounded-lg hover:bg-slate-700"
          onClick={() => setSidebarOpen(false)}
        >
          <X className="w-5 h-5 text-slate-300" aria-hidden="true" />
        </button>
        {sidebarContent}
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-auto">
        <div className="sticky top-0 z-30 bg-white/80 backdrop-blur border-b border-gray-100 px-4 lg:px-8 py-3 flex items-center justify-between">
          <button
            type="button"
            aria-label="Открыть меню"
            className="lg:hidden p-2 rounded-lg hover:bg-gray-100"
            onClick={() => setSidebarOpen(true)}
          >
            <Menu className="w-5 h-5 text-gray-600" aria-hidden="true" />
          </button>
          <div className="flex-1" />
          <NotificationBell />
        </div>
        <div className="p-4 lg:p-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
