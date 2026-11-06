import { useState } from 'react';
import { Link, NavLink, Outlet, useNavigate } from 'react-router';
import {
  Banknote,
  Building2,
  ClipboardList,
  LayoutDashboard,
  LogOut,
  Menu,
  Users,
  Wallet,
  X,
} from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import logo from '@/assets/logo-color.svg';
import { useAuthStore } from '@/app/store/authStore';
import { getAgentMe } from '@/app/api/agent';

const NAV = [
  { to: '/agent', label: 'Главная', icon: LayoutDashboard, end: true },
  { to: '/agent/partners', label: 'Партнёры', icon: Users, end: false },
  { to: '/agent/accruals', label: 'Начисления', icon: ClipboardList, end: false },
  { to: '/agent/payouts', label: 'Выплаты', icon: Wallet, end: false },
  { to: '/agent/requisites', label: 'Реквизиты', icon: Banknote, end: false },
];

export default function AgentLayout() {
  const navigate = useNavigate();
  const logout = useAuthStore((s) => s.logout);
  const [open, setOpen] = useState(false);
  const { data: me } = useQuery({ queryKey: ['agent', 'me'], queryFn: getAgentMe });

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="min-h-screen bg-gray-50 flex">
      {open && (
        <button
          aria-label="Закрыть меню"
          className="fixed inset-0 bg-black/30 z-30 lg:hidden"
          onClick={() => setOpen(false)}
        />
      )}

      <aside
        className={`fixed lg:static inset-y-0 left-0 z-40 w-72 bg-white border-r border-gray-200 flex flex-col transition-transform ${
          open ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        }`}
      >
        <div className="h-16 flex items-center justify-between px-5 border-b border-gray-100">
          <Link to="/agent">
            <img src={logo} alt="ЮРИТЕХ" className="h-9" />
          </Link>
          <button className="lg:hidden text-gray-400" onClick={() => setOpen(false)}>
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="px-5 py-4 border-b border-gray-100">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-emerald-50 text-emerald-700 flex items-center justify-center">
              <Building2 className="w-5 h-5" />
            </div>
            <div className="min-w-0">
              <div className="text-sm font-medium text-gray-900 truncate">
                {me?.profile.full_name || 'Агент'}
              </div>
              <div className="text-xs text-gray-500 font-mono">{me?.profile.code || '—'}</div>
            </div>
          </div>
        </div>

        <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              onClick={() => setOpen(false)}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                  isActive
                    ? 'bg-emerald-50 text-emerald-700 font-medium'
                    : 'text-gray-600 hover:bg-gray-50'
                }`
              }
            >
              <item.icon className="w-5 h-5" />
              {item.label}
            </NavLink>
          ))}
        </nav>

        <button
          onClick={handleLogout}
          className="m-3 flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-gray-600 hover:bg-gray-50"
        >
          <LogOut className="w-5 h-5" />
          Выйти
        </button>
      </aside>

      <div className="flex-1 min-w-0 flex flex-col">
        <header className="lg:hidden h-14 bg-white border-b border-gray-200 flex items-center px-4 gap-3">
          <button onClick={() => setOpen(true)} aria-label="Меню">
            <Menu className="w-5 h-5 text-gray-600" />
          </button>
          <img src={logo} alt="ЮРИТЕХ" className="h-8" />
        </header>
        <main className="flex-1 p-4 sm:p-6 lg:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
