import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router';
import { Loader2, Mail } from 'lucide-react';
import logo from '@/assets/logo-color.svg';
import { getInviteInfo, registerByInvite, type InviteInfo } from '@/app/api/adminAccess';
import { useAuthStore } from '@/app/store/authStore';
import { getApiErrorMessage } from '@/app/utils/apiError';

const ROLE_LABELS: Record<string, string> = {
  admin: 'Администратор',
  super_admin: 'Супер-администратор',
  agent: 'Агент',
};

const STATUS_TEXT: Record<string, string> = {
  used: 'Ссылка уже использована',
  revoked: 'Приглашение отозвано',
  expired: 'Срок действия ссылки истёк',
  invalid: 'Ссылка недействительна',
};

function formatDate(value: string) {
  return new Date(value).toLocaleString('ru-RU', { day: '2-digit', month: 'long', hour: '2-digit', minute: '2-digit' });
}

export default function InviteAccept() {
  const { token = '' } = useParams();
  const navigate = useNavigate();
  const login = useAuthStore((s) => s.login);

  const [loading, setLoading] = useState(true);
  const [invite, setInvite] = useState<InviteInfo | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const [form, setForm] = useState({ login: '', password: '', repeat: '', full_name: '', phone: '' });
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getInviteInfo(token)
      .then((data) => {
        if (cancelled) return;
        setInvite(data);
      })
      .catch((err) => {
        if (!cancelled) setFailure(getApiErrorMessage(err, STATUS_TEXT.invalid));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  const update = (field: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((prev) => ({ ...prev, [field]: e.target.value }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (form.password !== form.repeat) {
      setError('Пароли не совпадают');
      return;
    }
    if (form.password.length < 10) {
      setError('Пароль должен содержать минимум 10 символов');
      return;
    }

    setSubmitting(true);
    try {
      const data = await registerByInvite({
        token,
        login: form.login.trim(),
        password: form.password,
        full_name: form.full_name.trim() || undefined,
        phone: form.phone.trim() || undefined,
      });
      login({ id: data.user.id, email: data.user.email, role: data.user.role }, data.access_token);
      navigate(data.user.role === 'agent' ? '/agent' : '/admin', { replace: true });
    } catch (err) {
      setError(getApiErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
      </div>
    );
  }

  const inactiveStatus = invite && invite.status !== 'active' ? invite.status : null;

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-white rounded-2xl shadow-xl p-8">
        <img src={logo} alt="ЮРИТЕХ" className="w-56 mb-6 mx-auto" />

        {failure || inactiveStatus ? (
          <div>
            <h1 className="text-xl font-semibold text-gray-900 mb-2">
              {inactiveStatus ? STATUS_TEXT[inactiveStatus] : failure}
            </h1>
            <p className="text-sm text-gray-600 mb-6">
              Попросите супер-администратора выпустить новое приглашение на вашу почту.
            </p>
            <Link to="/login" className="text-blue-600 hover:underline font-medium text-sm">
              Перейти ко входу
            </Link>
          </div>
        ) : invite ? (
          <>
            <div className="mb-5">
              <p className="inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full bg-amber-50 text-amber-700 border border-amber-200">
                Приглашение · действует до {formatDate(invite.expires_at)}
              </p>
              <h1 className="text-2xl font-semibold text-gray-900 mt-3 mb-1">Создайте свой аккаунт</h1>
              <p className="text-sm text-gray-600">
                Роль: {ROLE_LABELS[invite.role] ?? invite.role}
                {invite.inviter_label ? ` · пригласил(а) ${invite.inviter_label}` : ''}
              </p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              {error && (
                <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">
                  {error}
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Почта</label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                  <input
                    value={invite.email}
                    disabled
                    className="w-full pl-9 pr-3 py-2.5 border border-gray-200 bg-gray-100 rounded-lg text-sm text-gray-700"
                  />
                </div>
                <p className="mt-1 text-xs text-gray-500">Почта закреплена за приглашением.</p>
              </div>

              {invite.role === 'agent' && (
                <>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Ваше имя</label>
                    <input
                      value={form.full_name}
                      onChange={update('full_name')}
                      required
                      placeholder="Иванов Иван Иванович"
                      className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Телефон</label>
                    <input
                      value={form.phone}
                      onChange={update('phone')}
                      placeholder="+7 900 000-00-00"
                      className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                </>
              )}

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Логин</label>
                <input
                  value={form.login}
                  onChange={update('login')}
                  required
                  pattern="[A-Za-z0-9._-]{3,32}"
                  placeholder="i.kovaleva"
                  className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Пароль</label>
                <input
                  type="password"
                  value={form.password}
                  onChange={update('password')}
                  required
                  className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <p className="mt-1 text-xs text-gray-500">Не менее 10 символов, буквы и цифры.</p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Повторите пароль</label>
                <input
                  type="password"
                  value={form.repeat}
                  onChange={update('repeat')}
                  required
                  className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <button
                type="submit"
                disabled={submitting}
                className="w-full py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium disabled:opacity-50"
              >
                {submitting ? 'Создаём…' : 'Создать аккаунт'}
              </button>

              <p className="text-xs text-gray-400 text-center">
                Ссылка одноразовая — после создания аккаунта она перестанет работать.
              </p>
            </form>
          </>
        ) : null}
      </div>
    </div>
  );
}
