import { useState } from 'react';
import { Link, Outlet, useLocation, useNavigate } from 'react-router';
import {
  LayoutDashboard,
  Users,
  UserPlus,
  LogOut,
  MessageSquare,
  Wallet,
  CheckSquare,
  GraduationCap,
  Newspaper,
  Settings,
  Menu,
  X,
} from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import logo from '@/assets/logo-color.svg';
import NotificationBell from '../components/NotificationBell';
import { useMe } from '../hooks/useAuth';
import { useAuthStore } from '../store/authStore';
import { fetchPartnerUnreadCount } from '../api/chat';
import { fetchNewsCount } from '../api/news';

function sidebarBadgeLabel(companyName: string | null | undefined): string {
  const t = companyName?.trim();
  if (!t) return 'ЮК';
  return t.slice(0, 2).toUpperCase();
}

export default function Layout() {
  const location = useLocation();
  const navigate = useNavigate();
  const logout = useAuthStore((s) => s.logout);
  const { data: me } = useMe();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const companyTitle =
    me?.company_name?.trim() || me?.email || (me ? 'Партнёр' : '…');
  const badgeText = sidebarBadgeLabel(me?.company_name || me?.email);

  const { data: chatUnreadCount = 0 } = useQuery({
    queryKey: ['partnerUnreadCount'],
    queryFn: fetchPartnerUnreadCount,
    refetchInterval: 15000,
  });

  const { data: newsUnreadCount = 0 } = useQuery({
    queryKey: ['newsUnreadCount'],
    queryFn: fetchNewsCount,
    refetchInterval: 30_000,
  });

  const navigation = [
    { name: 'Дашборд', href: '/dashboard', icon: LayoutDashboard, color: 'text-blue-600', bgColor: 'bg-blue-50' },
    { name: 'Клиенты', href: '/dashboard/clients', icon: Users, color: 'text-purple-600', bgColor: 'bg-purple-50' },
    { name: 'Добавить клиента', href: '/dashboard/clients/new', icon: UserPlus, color: 'text-green-600', bgColor: 'bg-green-50' },
    { name: 'Список задач', href: '/dashboard/tasks', icon: CheckSquare, color: 'text-pink-600', bgColor: 'bg-pink-50' },
    { name: 'Финансы', href: '/dashboard/finance/court-fees', icon: Wallet, color: 'text-emerald-600', bgColor: 'bg-emerald-50' },
    { name: 'Чат', href: '/dashboard/chat', icon: MessageSquare, color: 'text-teal-600', bgColor: 'bg-teal-50', badge: chatUnreadCount },
    { name: 'Новости', href: '/dashboard/news', icon: Newspaper, color: 'text-blue-600', bgColor: 'bg-blue-50', badge: newsUnreadCount },
    { name: 'Обучение', href: '/dashboard/training', icon: GraduationCap, color: 'text-indigo-600', bgColor: 'bg-indigo-50' },
    { name: 'Настройки', href: '/dashboard/settings', icon: Settings, color: 'text-gray-600', bgColor: 'bg-gray-100' },
  ];

  const isActive = (href: string) => {
    if (href === '/dashboard') return location.pathname === '/dashboard';
    return location.pathname.startsWith(href);
  };

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const sidebarContent = (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-center px-6 py-6 border-b border-gray-200">
        <img src={logo} alt="ЮРИТЕХ" className="h-[50px] w-auto" />
      </div>

      <nav className="flex-1 px-4 py-6 overflow-y-auto">
        <div className="space-y-2">
          {navigation.map((item) => {
            const Icon = item.icon;
            const active = isActive(item.href);
            const badge = 'badge' in item ? (item as { badge?: number }).badge : undefined;
            return (
              <Link
                key={item.name}
                to={item.href}
                onClick={() => setSidebarOpen(false)}
                className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${
                  active ? 'bg-blue-50 shadow-sm' : 'hover:bg-gray-50'
                }`}
              >
                <div className={`w-10 h-10 rounded-lg flex items-center justify-center relative ${active ? item.bgColor : 'bg-gray-100'}`}>
                  <Icon className={`w-5 h-5 ${active ? item.color : 'text-gray-500'}`} />
                  {!!badge && badge > 0 && (
                    <span className="absolute -top-1 -right-1 bg-red-500 text-white text-[10px] font-bold rounded-full w-5 h-5 flex items-center justify-center">
                      {badge > 9 ? '9+' : badge}
                    </span>
                  )}
                </div>
                <span className={`font-medium ${active ? 'text-gray-900' : 'text-gray-700'}`}>
                  {item.name}
                </span>
              </Link>
            );
          })}
        </div>
      </nav>

      <div className="p-4 border-t border-gray-200">
        <button
          onClick={handleLogout}
          className="w-full flex items-center gap-3 px-4 py-3 rounded-xl hover:bg-gray-50 cursor-pointer transition-all group"
        >
          <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-blue-600 rounded-lg flex items-center justify-center shrink-0">
            <span className="text-sm font-semibold text-white leading-none">{badgeText}</span>
          </div>
          <div className="flex-1 min-w-0 text-left">
            <p className="text-sm font-medium text-gray-900 truncate" title={companyTitle}>
              {companyTitle}
            </p>
            <p className="text-xs text-gray-500 truncate">Партнёр</p>
          </div>
          <LogOut className="w-4 h-4 text-gray-400 group-hover:text-gray-600 transition-colors" />
        </button>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
          role="presentation"
          aria-hidden="true"
        />
      )}

      {/* Sidebar — mobile: slide in/out, desktop: fixed */}
      <aside
        aria-label="Основная навигация"
        className={`fixed inset-y-0 left-0 w-64 bg-white border-r border-gray-200 z-50 transform transition-transform duration-200 lg:translate-x-0 ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        {/* Close button for mobile */}
        <button
          type="button"
          aria-label="Закрыть меню"
          className="absolute top-4 right-4 lg:hidden p-1 rounded-lg hover:bg-gray-100"
          onClick={() => setSidebarOpen(false)}
        >
          <X className="w-5 h-5 text-gray-500" aria-hidden="true" />
        </button>
        {sidebarContent}
      </aside>

      {/* Main content */}
      <div className="lg:ml-64">
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
        <main>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
