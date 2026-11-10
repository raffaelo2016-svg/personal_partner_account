import { useState } from 'react';
import { Link, useNavigate } from 'react-router';
import { Loader2, UserPlus } from 'lucide-react';
import logo from '@/assets/logo-color.svg';
import { registerAgent } from '@/app/api/agent';
import { useAuthStore } from '@/app/store/authStore';
import { getApiErrorMessage } from '@/app/utils/apiError';

export default function BecomeAgent() {
  const navigate = useNavigate();
  const login = useAuthStore((s) => s.login);
  const [form, setForm] = useState({
    email: '',
    full_name: '',
    phone: '',
    company_name: '',
    password: '',
    repeat: '',
  });
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

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
      const data = await registerAgent({
        email: form.email.trim(),
        full_name: form.full_name.trim(),
        phone: form.phone.trim(),
        company_name: form.company_name.trim() || undefined,
        password: form.password,
      });
      login(
        { id: data.user.id, email: data.user.email, role: data.user.role as 'agent' },
        data.access_token,
      );
      navigate('/agent', { replace: true });
    } catch (err) {
      setError(getApiErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-emerald-50 to-blue-50 flex items-center justify-center p-4">
      <div className="w-full max-w-lg bg-white rounded-2xl shadow-xl p-8">
        <img src={logo} alt="ЮРИТЕХ" className="h-10 mb-6 mx-auto" />

        <div className="w-12 h-12 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center mb-4">
          <UserPlus className="w-6 h-6" />
        </div>
        <h1 className="text-2xl font-semibold text-gray-900 mb-2">Стать агентом</h1>
        <p className="text-sm text-gray-600 mb-6">
          Приводите юристов и юридические компании. За каждого клиента, дошедшего до процедуры, —
          1 000 ₽ без ограничения срока программы.
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">{error}</div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Ваше имя</label>
            <input
              value={form.full_name}
              onChange={update('full_name')}
              required
              placeholder="Иванов Иван Иванович"
              className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Почта</label>
            <input
              type="email"
              value={form.email}
              onChange={update('email')}
              required
              placeholder="agent@example.ru"
              className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Телефон</label>
              <input
                value={form.phone}
                onChange={update('phone')}
                placeholder="+7 900 000-00-00"
                className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Компания</label>
              <input
                value={form.company_name}
                onChange={update('company_name')}
                placeholder="Необязательно"
                className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Пароль</label>
            <input
              type="password"
              value={form.password}
              onChange={update('password')}
              required
              className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
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
              className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
            />
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="w-full inline-flex items-center justify-center gap-2 py-2.5 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 font-medium disabled:opacity-50"
          >
            {submitting && <Loader2 className="w-4 h-4 animate-spin" />}
            Создать кабинет агента
          </button>

          <p className="text-xs text-gray-400 text-center">
            Уже есть кабинет? <Link to="/login" className="text-emerald-700 hover:underline">Войти</Link>
          </p>
        </form>
      </div>
    </div>
  );
}
