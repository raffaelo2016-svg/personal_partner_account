import { useCallback, useEffect, useMemo, useState } from 'react';
import { Navigate } from 'react-router';
import {
  Ban,
  CheckCircle2,
  Clock,
  Copy,
  KeyRound,
  Loader2,
  Mail,
  Plus,
  RefreshCw,
  ShieldCheck,
  Trash2,
} from 'lucide-react';
import {
  createInvite,
  getAudit,
  listAdmins,
  listInvites,
  resetAdminPassword,
  resendInvite,
  revokeInvite,
  updateAdmin,
  type AdminRole,
  type AdminUser,
  type AuditEntry,
  type Invite,
} from '@/app/api/adminAccess';
import { getApiErrorMessage } from '@/app/utils/apiError';
import { useAuthStore } from '@/app/store/authStore';

type Tab = 'users' | 'invites' | 'audit';

const ROLE_LABELS: Record<string, string> = {
  admin: 'Администратор',
  super_admin: 'Супер-админ',
};

const INVITE_STATUS: Record<string, { label: string; className: string }> = {
  active: { label: 'Активно', className: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
  used: { label: 'Использовано', className: 'bg-gray-100 text-gray-600 border-gray-200' },
  expired: { label: 'Просрочено', className: 'bg-amber-50 text-amber-700 border-amber-200' },
  revoked: { label: 'Отозвано', className: 'bg-red-50 text-red-700 border-red-200' },
};

const ACTION_LABELS: Record<string, string> = {
  bootstrap_completed: 'Первый запуск',
  invite_created: 'Создано приглашение',
  invite_resent: 'Перевыпущено приглашение',
  invite_revoked: 'Отозвано приглашение',
  invite_accepted: 'Регистрация по приглашению',
  login_success: 'Вход',
  login: 'Вход',
  login_failed: 'Неудачный вход',
  token_refresh: 'Обновление сессии',
  logout: 'Выход',
  user_blocked: 'Блокировка',
  user_unblocked: 'Разблокировка',
  user_role_changed: 'Смена роли',
  partner_registered: 'Регистрация партнёра',
};

function formatDateTime(value: string | null) {
  if (!value) return '—';
  return new Date(value).toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export default function AdminAdmins() {
  const currentUser = useAuthStore((s) => s.user);
  const [tab, setTab] = useState<Tab>('users');
  const [search, setSearch] = useState('');
  const [admins, setAdmins] = useState<AdminUser[]>([]);
  const [invites, setInvites] = useState<Invite[]>([]);
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [auditTotal, setAuditTotal] = useState(0);
  const [auditPage, setAuditPage] = useState(1);
  const [auditAction, setAuditAction] = useState('');
  const [auditPeriod, setAuditPeriod] = useState<'30' | 'all'>('30');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [inviteOpen, setInviteOpen] = useState(false);
  const [inviteForm, setInviteForm] = useState<{ email: string; role: AdminRole; ttl: number }>({
    email: '',
    role: 'admin',
    ttl: 72,
  });
  const [inviteBusy, setInviteBusy] = useState(false);
  const [createdInvite, setCreatedInvite] = useState<Invite | null>(null);

  const loadAdmins = useCallback(async () => {
    const data = await listAdmins(search.trim() || undefined);
    setAdmins(data);
  }, [search]);

  const loadInvites = useCallback(async () => {
    setInvites(await listInvites());
  }, []);

  const loadAudit = useCallback(
    async (page = 1, append = false) => {
      const data = await getAudit({
        page,
        page_size: 25,
        action: auditAction || undefined,
        search: search.trim() || undefined,
        date_from:
          auditPeriod === '30'
            ? new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString()
            : undefined,
      });
      setAudit((prev) => (append ? [...prev, ...data.items] : data.items));
      setAuditTotal(data.total);
      setAuditPage(page);
    },
    [auditAction, search, auditPeriod],
  );

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // Счётчики в шапке всегда должны быть актуальны, поэтому грузим оба списка.
      await Promise.all([loadAdmins(), loadInvites()]);
      if (tab === 'audit') await loadAudit(1, false);
    } catch (err) {
      setError(getApiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [tab, loadAdmins, loadInvites, loadAudit]);

  useEffect(() => {
    void reload();
  }, [reload]);

  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => setNotice(null), 4000);
    return () => clearTimeout(timer);
  }, [notice]);

  const stats = useMemo(() => {
    const active = admins.filter((a) => a.is_active).length;
    const supers = admins.filter((a) => a.role === 'super_admin' && a.is_active).length;
    const pending = invites.filter((i) => i.status === 'active').length;
    return { active, supers, pending };
  }, [admins, invites]);

  const handleToggleBlock = async (admin: AdminUser) => {
    try {
      await updateAdmin(admin.id, { is_active: !admin.is_active });
      setNotice(admin.is_active ? 'Доступ заблокирован' : 'Доступ восстановлен');
      await loadAdmins();
    } catch (err) {
      setError(getApiErrorMessage(err));
    }
  };

  const handleRoleChange = async (admin: AdminUser, role: AdminRole) => {
    try {
      await updateAdmin(admin.id, { role });
      setNotice('Роль обновлена');
      await loadAdmins();
    } catch (err) {
      setError(getApiErrorMessage(err));
    }
  };

  const handleResetPassword = async (admin: AdminUser) => {
    if (!window.confirm(`Отправить ссылку на сброс пароля на ${admin.email}?`)) return;
    try {
      const { message } = await resetAdminPassword(admin.id);
      setNotice(message);
    } catch (err) {
      setError(getApiErrorMessage(err));
    }
  };

  const submitInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    setInviteBusy(true);
    setError(null);
    try {
      const created = await createInvite({
        email: inviteForm.email.trim(),
        role: inviteForm.role,
        ttl_hours: inviteForm.ttl,
      });
      setInviteOpen(false);
      setInviteForm({ email: '', role: 'admin', ttl: 72 });
      setCreatedInvite(created);
      await loadInvites();
    } catch (err) {
      setError(getApiErrorMessage(err));
    } finally {
      setInviteBusy(false);
    }
  };

  const handleRevoke = async (invite: Invite) => {
    if (!window.confirm(`Отозвать приглашение на ${invite.email}?`)) return;
    try {
      await revokeInvite(invite.id);
      setNotice('Приглашение отозвано');
      await loadInvites();
    } catch (err) {
      setError(getApiErrorMessage(err));
    }
  };

  const handleResend = async (invite: Invite) => {
    try {
      const updated = await resendInvite(invite.id);
      setCreatedInvite(updated);
      await loadInvites();
    } catch (err) {
      setError(getApiErrorMessage(err));
    }
  };

  const copyLink = async (url: string) => {
    try {
      await navigator.clipboard.writeText(url);
      setNotice('Ссылка скопирована');
    } catch {
      setNotice('Не удалось скопировать — выделите ссылку вручную');
    }
  };

  if (currentUser && currentUser.role !== 'super_admin') {
    return <Navigate to="/admin" replace />;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Админы и доступы</h1>
          <p className="text-sm text-gray-500 mt-1">Кто входит в кабинет и как выдать или забрать доступ.</p>
        </div>
        <button
          onClick={() => setInviteOpen(true)}
          className="inline-flex items-center justify-center gap-2 px-4 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium"
        >
          <Plus className="w-4 h-4" />
          Пригласить админа
        </button>
      </div>

      {error && (
        <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700 flex items-start justify-between gap-4">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="text-red-500 hover:text-red-700">×</button>
        </div>
      )}
      {notice && (
        <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-sm text-emerald-700">
          {notice}
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white border border-gray-200 rounded-xl p-4 flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div>
            <div className="text-2xl font-semibold text-gray-900">{stats.active}</div>
            <div className="text-xs text-gray-500">Действующих админов</div>
          </div>
        </div>
        <div className="bg-white border border-gray-200 rounded-xl p-4 flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center">
            <Clock className="w-5 h-5" />
          </div>
          <div>
            <div className="text-2xl font-semibold text-gray-900">{stats.pending}</div>
            <div className="text-xs text-gray-500">Ждут регистрации</div>
          </div>
        </div>
        <div className="bg-white border border-gray-200 rounded-xl p-4 flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center">
            <KeyRound className="w-5 h-5" />
          </div>
          <div>
            <div className="text-2xl font-semibold text-gray-900">{stats.supers}</div>
            <div className="text-xs text-gray-500">Супер-админов</div>
          </div>
        </div>
      </div>

      {stats.supers === 1 && (
        <div className="p-3 rounded-lg bg-amber-50 border border-amber-200 text-sm text-amber-800">
          В системе один супер-администратор. Назначьте второго — иначе при утрате доступа
          управлять приглашениями будет некому.
        </div>
      )}

      <div className="flex items-center gap-4 border-b border-gray-200">
        {([
          ['users', 'Действующие'],
          ['invites', 'Приглашения'],
          ['audit', 'Журнал доступа'],
        ] as [Tab, string][]).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`pb-2.5 px-1 text-sm border-b-2 -mb-px transition-colors ${
              tab === key
                ? 'border-blue-600 text-blue-600 font-medium'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            {label}
          </button>
        ))}
        <div className="ml-auto pb-2">
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={tab === 'audit' ? 'Почта или логин' : 'Поиск по почте или логину'}
            className="w-56 px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      </div>

      {loading ? (
        <div className="py-16 flex justify-center">
          <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
        </div>
      ) : tab === 'users' ? (
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-xs uppercase tracking-wide text-gray-500">
              <tr>
                <th className="text-left px-4 py-3">Сотрудник</th>
                <th className="text-left px-4 py-3">Логин</th>
                <th className="text-left px-4 py-3">Роль</th>
                <th className="text-left px-4 py-3">Последний вход</th>
                <th className="text-left px-4 py-3">Статус</th>
                <th className="text-right px-4 py-3">Действия</th>
              </tr>
            </thead>
            <tbody>
              {admins.map((admin) => (
                <tr key={admin.id} className="border-t border-gray-100">
                  <td className="px-4 py-3">
                    <div className="font-medium text-gray-900">{admin.email}</div>
                    {admin.is_legacy_shared && (
                      <div className="text-xs text-amber-600">бывшая общая учётная запись</div>
                    )}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-gray-600">{admin.login ?? '—'}</td>
                  <td className="px-4 py-3">
                    <select
                      value={admin.role}
                      onChange={(e) => handleRoleChange(admin, e.target.value as AdminRole)}
                      className="border border-gray-200 rounded-md px-2 py-1 text-xs bg-white"
                    >
                      <option value="admin">Администратор</option>
                      <option value="super_admin">Супер-админ</option>
                    </select>
                  </td>
                  <td className="px-4 py-3 text-gray-600">{formatDateTime(admin.last_login_at)}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-flex items-center gap-1.5 text-xs ${
                        admin.is_active ? 'text-emerald-700' : 'text-red-700'
                      }`}
                    >
                      <span
                        className={`w-1.5 h-1.5 rounded-full ${
                          admin.is_active ? 'bg-emerald-500' : 'bg-red-500'
                        }`}
                      />
                      {admin.is_active ? 'Активен' : 'Заблокирован'}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-1">
                      <button
                        onClick={() => handleResetPassword(admin)}
                        title="Сбросить пароль"
                        className="p-2 rounded-md text-gray-400 hover:text-blue-600 hover:bg-blue-50"
                      >
                        <RefreshCw className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => handleToggleBlock(admin)}
                        title={admin.is_active ? 'Заблокировать' : 'Разблокировать'}
                        className={`p-2 rounded-md hover:bg-gray-100 ${
                          admin.is_active ? 'text-gray-400 hover:text-red-600' : 'text-emerald-600'
                        }`}
                      >
                        {admin.is_active ? <Ban className="w-4 h-4" /> : <CheckCircle2 className="w-4 h-4" />}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {admins.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-10 text-center text-gray-500">
                    Администраторы не найдены
                  </td>
                </tr>
              )}
            </tbody>
          </table>
          <div className="px-4 py-3 text-xs text-gray-500 border-t border-gray-100">
            Пароли не видны никому, включая супер-админа. Забыл пароль — сброс по почте.
          </div>
        </div>
      ) : tab === 'invites' ? (
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-xs uppercase tracking-wide text-gray-500">
              <tr>
                <th className="text-left px-4 py-3">Почта</th>
                <th className="text-left px-4 py-3">Роль</th>
                <th className="text-left px-4 py-3">Создал</th>
                <th className="text-left px-4 py-3">Создано</th>
                <th className="text-left px-4 py-3">Действует до</th>
                <th className="text-left px-4 py-3">Статус</th>
                <th className="text-right px-4 py-3">Действия</th>
              </tr>
            </thead>
            <tbody>
              {invites.map((invite) => {
                const status = INVITE_STATUS[invite.status] ?? INVITE_STATUS.expired;
                return (
                  <tr key={invite.id} className="border-t border-gray-100">
                    <td className="px-4 py-3 font-medium text-gray-900">{invite.email}</td>
                    <td className="px-4 py-3 text-gray-600">{ROLE_LABELS[invite.role] ?? invite.role}</td>
                    <td className="px-4 py-3 text-gray-600">{invite.created_by_label ?? '—'}</td>
                    <td className="px-4 py-3 text-gray-600">{formatDateTime(invite.created_at)}</td>
                    <td className="px-4 py-3 text-gray-600">{formatDateTime(invite.expires_at)}</td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex px-2 py-0.5 rounded-full border text-xs ${status.className}`}>
                        {status.label}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-1">
                        {invite.status === 'active' && invite.invite_url && (
                          <button
                            onClick={() => void copyLink(invite.invite_url as string)}
                            title="Скопировать ссылку"
                            className="p-2 rounded-md text-gray-400 hover:text-blue-600 hover:bg-blue-50"
                          >
                            <Copy className="w-4 h-4" />
                          </button>
                        )}
                        {(invite.status === 'expired' || invite.status === 'revoked') && (
                          <button
                            onClick={() => handleResend(invite)}
                            title="Перевыпустить"
                            className="p-2 rounded-md text-gray-400 hover:text-blue-600 hover:bg-blue-50"
                          >
                            <RefreshCw className="w-4 h-4" />
                          </button>
                        )}
                        {invite.status === 'active' && (
                          <button
                            onClick={() => handleRevoke(invite)}
                            title="Отозвать"
                            className="p-2 rounded-md text-gray-400 hover:text-red-600 hover:bg-red-50"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
              {invites.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-10 text-center text-gray-500">
                    Приглашений пока нет — пригласите администратора.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          <div className="flex flex-wrap items-center gap-2 px-4 py-3 border-b border-gray-100">
            <select
              value={auditPeriod}
              onChange={(e) => setAuditPeriod(e.target.value as '30' | 'all')}
              className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm bg-white"
            >
              <option value="30">Последние 30 дней</option>
              <option value="all">За всё время</option>
            </select>
            <select
              value={auditAction}
              onChange={(e) => setAuditAction(e.target.value)}
              className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm bg-white"
            >
              <option value="">Все действия</option>
              {Object.entries(ACTION_LABELS).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
            <button
              onClick={() => void loadAudit(1, false)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm text-gray-600 hover:text-blue-600"
            >
              <RefreshCw className="w-4 h-4" /> Обновить
            </button>
          </div>
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-xs uppercase tracking-wide text-gray-500">
              <tr>
                <th className="text-left px-4 py-3">Время</th>
                <th className="text-left px-4 py-3">Кто</th>
                <th className="text-left px-4 py-3">Действие</th>
                <th className="text-left px-4 py-3">Объект</th>
                <th className="text-left px-4 py-3">IP</th>
              </tr>
            </thead>
            <tbody>
              {audit.map((entry) => (
                <tr key={entry.id} className="border-t border-gray-100">
                  <td className="px-4 py-3 text-gray-600 whitespace-nowrap">{formatDateTime(entry.created_at)}</td>
                  <td className="px-4 py-3 text-gray-900">{entry.actor_label ?? 'система'}</td>
                  <td className="px-4 py-3 text-gray-700">{ACTION_LABELS[entry.action] ?? entry.action}</td>
                  <td className="px-4 py-3 text-gray-600">{entry.target_label ?? '—'}</td>
                  <td className="px-4 py-3 font-mono text-xs text-gray-400">{entry.ip_address ?? '—'}</td>
                </tr>
              ))}
              {audit.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-10 text-center text-gray-500">
                    Записей пока нет
                  </td>
                </tr>
              )}
            </tbody>
          </table>
          <div className="flex items-center justify-between px-4 py-3 border-t border-gray-100 text-xs text-gray-500">
            <span>Показано {audit.length} из {auditTotal}</span>
            {audit.length < auditTotal && (
              <button
                onClick={() => void loadAudit(auditPage + 1, true)}
                className="text-blue-600 hover:underline font-medium"
              >
                Показать ещё
              </button>
            )}
          </div>
        </div>
      )}

      {inviteOpen && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <form onSubmit={submitInvite} className="w-full max-w-md bg-white rounded-xl shadow-2xl p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-1">Пригласить админа</h2>
            <p className="text-sm text-gray-500 mb-5">
              Ссылка придёт на почту и будет действовать {inviteForm.ttl} ч. Аккаунт появится только после регистрации.
            </p>

            <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <div className="relative mb-4">
              <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="email"
                required
                value={inviteForm.email}
                onChange={(e) => setInviteForm((prev) => ({ ...prev, email: e.target.value }))}
                placeholder="i.kovaleva@uritech.ru"
                className="w-full pl-9 pr-3 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <label className="block text-sm font-medium text-gray-700 mb-2">Роль</label>
            <div className="space-y-2 mb-4">
              {(['admin', 'super_admin'] as AdminRole[]).map((role) => (
                <label
                  key={role}
                  className={`flex gap-2 items-start border rounded-lg p-3 cursor-pointer ${
                    inviteForm.role === role ? 'border-blue-500 bg-blue-50/50' : 'border-gray-200'
                  }`}
                >
                  <input
                    type="radio"
                    name="role"
                    checked={inviteForm.role === role}
                    onChange={() => setInviteForm((prev) => ({ ...prev, role }))}
                    className="mt-1"
                  />
                  <span>
                    <span className="block text-sm font-medium text-gray-900">
                      {role === 'admin' ? 'Администратор' : 'Супер-админ'}
                    </span>
                    <span className="block text-xs text-gray-500">
                      {role === 'admin'
                        ? 'Работает в кабинете, но не управляет доступами других.'
                        : 'Управляет админами и приглашениями. Нужно минимум два.'}
                    </span>
                  </span>
                </label>
              ))}
            </div>

            <label className="block text-sm font-medium text-gray-700 mb-2">Срок действия ссылки</label>
            <div className="flex gap-2 mb-5">
              {[24, 72, 168].map((hours) => (
                <button
                  key={hours}
                  type="button"
                  onClick={() => setInviteForm((prev) => ({ ...prev, ttl: hours }))}
                  className={`px-3 py-1.5 rounded-lg border text-sm ${
                    inviteForm.ttl === hours
                      ? 'border-blue-500 bg-blue-50 text-blue-700'
                      : 'border-gray-200 text-gray-600'
                  }`}
                >
                  {hours === 24 ? '1 день' : hours === 72 ? '3 дня' : '7 дней'}
                </button>
              ))}
            </div>

            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setInviteOpen(false)}
                className="px-4 py-2 rounded-lg border border-gray-200 text-sm text-gray-700"
              >
                Отмена
              </button>
              <button
                type="submit"
                disabled={inviteBusy}
                className="px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
              >
                {inviteBusy ? 'Создаём…' : 'Создать приглашение'}
              </button>
            </div>
          </form>
        </div>
      )}

      {createdInvite && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="w-full max-w-lg bg-white rounded-xl shadow-2xl p-6">
            <div className="w-12 h-12 rounded-full bg-emerald-50 text-emerald-600 flex items-center justify-center mx-auto mb-3">
              <CheckCircle2 className="w-6 h-6" />
            </div>
            <h2 className="text-lg font-semibold text-gray-900 text-center mb-1">Приглашение создано</h2>
            <p className="text-sm text-gray-500 text-center mb-4">
              Отправлено на <span className="text-gray-900 font-medium">{createdInvite.email}</span>
            </p>

            {createdInvite.invite_url && (
              <div className="flex items-center gap-2 border border-gray-200 bg-gray-50 rounded-lg p-2 mb-3">
                <span className="flex-1 truncate font-mono text-xs text-gray-600">
                  {createdInvite.invite_url}
                </span>
                <button
                  onClick={() => void copyLink(createdInvite.invite_url as string)}
                  className="inline-flex items-center gap-1 px-2.5 py-1.5 bg-white border border-gray-200 rounded-md text-xs text-gray-700"
                >
                  <Copy className="w-3.5 h-3.5" /> Копировать
                </button>
              </div>
            )}

            <div className="flex items-center justify-center gap-3 text-xs text-gray-500 mb-5">
              <span>Действует до {formatDateTime(createdInvite.expires_at)}</span>
              <span>·</span>
              <span>Одноразовая</span>
              <span>·</span>
              <span>{ROLE_LABELS[createdInvite.role] ?? createdInvite.role}</span>
            </div>

            <p className="text-xs text-gray-500 bg-gray-50 border border-gray-200 rounded-lg p-3 mb-5">
              Если письмо не дойдёт — передайте ссылку лично. Она сработает только для этой почты и только один раз.
            </p>

            <div className="flex items-center justify-between">
              <button
                onClick={() => {
                  setCreatedInvite(null);
                  setInviteOpen(true);
                }}
                className="px-4 py-2 rounded-lg border border-gray-200 text-sm text-gray-700"
              >
                Пригласить ещё
              </button>
              <button
                onClick={() => setCreatedInvite(null)}
                className="px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700"
              >
                Готово
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
