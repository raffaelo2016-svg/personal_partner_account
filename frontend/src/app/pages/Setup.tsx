import { useEffect, useState } from 'react';
import { Link } from 'react-router';
import { KeyRound, Loader2, ShieldCheck } from 'lucide-react';
import { bootstrapSuperAdmin, getSetupStatus } from '@/app/api/adminAccess';
import { getApiErrorMessage } from '@/app/utils/apiError';

export default function Setup() {
  const [checking, setChecking] = useState(true);
  const [needsSetup, setNeedsSetup] = useState(false);
  const [form, setForm] = useState({ key: '', email: '', login: '', password: '', repeat: '' });
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  useEffect(() => {
    getSetupStatus()
      .then((data) => setNeedsSetup(data.needs_setup))
      .catch(() => setNeedsSetup(false))
      .finally(() => setChecking(false));
  }, []);

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
      await bootstrapSuperAdmin({
        key: form.key.trim(),
        email: form.email.trim(),
        login: form.login.trim(),
        password: form.password,
      });
      setDone(true);
    } catch (err) {
      setError(getApiErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  if (checking) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-white rounded-2xl shadow-xl p-8">
        <div className="w-12 h-12 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center mb-5">
          <ShieldCheck className="w-6 h-6" />
        </div>

        <h1 className="text-2xl font-semibold text-gray-900 mb-2">Первый запуск</h1>
        <p className="text-sm text-gray-600 mb-6">
          Введите одноразовый ключ из консоли сервера и создайте супер-администратора.
        </p>

        {!needsSetup ? (
          <div className="text-sm text-gray-700">
            <p className="mb-4">Система уже настроена. Вход — на странице входа.</p>
            <Link to="/login" className="text-blue-600 hover:underline font-medium">
              Перейти ко входу
            </Link>
          </div>
        ) : done ? (
          <div className="text-sm text-gray-700">
            <p className="mb-4">
              Супер-администратор создан, ключ погашен. Теперь войдите под своими данными.
            </p>
            <Link to="/login" className="text-blue-600 hover:underline font-medium">
              Перейти ко входу
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">
                {error}
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Одноразовый ключ</label>
              <div className="relative">
                <KeyRound className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  value={form.key}
                  onChange={update('key')}
                  required
                  placeholder="7F3A-91C2-4E8B-D05A"
                  className="w-full pl-9 pr-3 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Почта</label>
              <input
                type="email"
                value={form.email}
                onChange={update('email')}
                required
                placeholder="admin@uritech.ru"
                className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Логин</label>
              <input
                value={form.login}
                onChange={update('login')}
                required
                placeholder="a.samsonyuk"
                pattern="[A-Za-z0-9._-]{3,32}"
                className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <p className="mt-1 text-xs text-gray-500">
                Латинские буквы, цифры, точка, дефис или подчёркивание.
              </p>
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
              {submitting ? 'Создаём…' : 'Создать супер-администратора'}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
