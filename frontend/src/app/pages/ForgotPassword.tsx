import { useState } from 'react';
import { ArrowLeft, CheckCircle2, Mail } from 'lucide-react';
import { Link, useLocation } from 'react-router';

import logo from '@/assets/logo-color.svg';
import { useForgotPassword } from '@/app/hooks/useAuth';

export default function ForgotPassword() {
  const location = useLocation();
  const initialEmail = (location.state as { email?: string } | null)?.email ?? '';
  const [email, setEmail] = useState(initialEmail);
  const mutation = useForgotPassword();

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    mutation.mutate(email.trim());
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
      <main className="w-full max-w-xl bg-white rounded-2xl shadow-xl px-8 lg:px-10 py-8">
        <div className="flex justify-center mb-6 px-4">
          <img src={logo} alt="ЮРИТЕХ" className="w-full max-w-sm h-auto" />
        </div>

        {mutation.isSuccess ? (
          <div className="text-center" role="status">
            <CheckCircle2 className="w-14 h-14 text-green-600 mx-auto mb-4" />
            <h1 className="text-2xl font-semibold text-gray-900 mb-3">Проверьте почту</h1>
            <p className="text-gray-600 mb-7">
              Если аккаунт с адресом <span className="font-medium text-gray-800">{email.trim()}</span>{' '}
              существует, мы отправили ссылку для восстановления пароля. Она действует 30 минут.
            </p>
            <Link
              to="/login"
              className="inline-flex items-center justify-center gap-2 text-blue-600 hover:underline font-medium"
            >
              <ArrowLeft className="w-4 h-4" />
              Вернуться ко входу
            </Link>
          </div>
        ) : (
          <>
            <h1 className="text-2xl font-semibold text-gray-900 mb-2">Восстановление пароля</h1>
            <p className="text-gray-600 mb-7">
              Укажите email, с которым вы зарегистрированы. Мы отправим ссылку для создания нового пароля.
            </p>

            {mutation.isError ? (
              <div className="mb-5 p-3 border border-red-200 bg-red-50 rounded-lg text-sm text-red-700" role="alert">
                Не удалось отправить запрос. Проверьте соединение и попробуйте ещё раз.
              </div>
            ) : null}

            <form onSubmit={handleSubmit} className="space-y-5">
              <div>
                <label htmlFor="recovery-email" className="block text-sm font-medium text-gray-700 mb-1">
                  Email
                </label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                  <input
                    id="recovery-email"
                    type="email"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    required
                    autoComplete="email"
                    autoFocus
                    placeholder="partner@example.com"
                    className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={mutation.isPending}
                className="w-full py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium disabled:opacity-50"
              >
                {mutation.isPending ? 'Отправляем...' : 'Отправить ссылку'}
              </button>
            </form>

            <Link to="/login" className="mt-6 inline-flex items-center gap-2 text-sm text-blue-600 hover:underline">
              <ArrowLeft className="w-4 h-4" />
              Вернуться ко входу
            </Link>
          </>
        )}
      </main>
    </div>
  );
}
