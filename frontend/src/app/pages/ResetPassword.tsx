import { useState } from 'react';
import { ArrowLeft, CheckCircle2, Lock } from 'lucide-react';
import { Link, useSearchParams } from 'react-router';

import logo from '@/assets/logo-color.svg';
import { useResetPassword } from '@/app/hooks/useAuth';

export default function ResetPassword() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') ?? '';
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [formError, setFormError] = useState('');
  const mutation = useResetPassword();

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    if (password.length < 8 || !/[A-Za-zА-Яа-я]/.test(password) || !/\d/.test(password)) {
      setFormError('Пароль должен содержать не менее 8 символов, хотя бы одну букву и одну цифру');
      return;
    }
    if (password !== confirmation) {
      setFormError('Пароли не совпадают');
      return;
    }
    setFormError('');
    mutation.mutate({ token, password });
  };

  const invalidLink = !token;

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
      <main className="w-full max-w-xl bg-white rounded-2xl shadow-xl px-8 lg:px-10 py-8">
        <div className="flex justify-center mb-6 px-4">
          <img src={logo} alt="ЮРИТЕХ" className="w-full max-w-sm h-auto" />
        </div>

        {mutation.isSuccess ? (
          <div className="text-center" role="status">
            <CheckCircle2 className="w-14 h-14 text-green-600 mx-auto mb-4" />
            <h1 className="text-2xl font-semibold text-gray-900 mb-3">Пароль изменён</h1>
            <p className="text-gray-600 mb-7">Теперь вы можете войти в кабинет с новым паролем.</p>
            <Link
              to="/login"
              className="inline-flex w-full items-center justify-center py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
            >
              Войти в кабинет
            </Link>
          </div>
        ) : invalidLink ? (
          <div className="text-center">
            <h1 className="text-2xl font-semibold text-gray-900 mb-3">Ссылка недействительна</h1>
            <p className="text-gray-600 mb-7">Запросите новую ссылку для восстановления пароля.</p>
            <Link to="/forgot-password" className="text-blue-600 hover:underline font-medium">
              Запросить новую ссылку
            </Link>
          </div>
        ) : (
          <>
            <h1 className="text-2xl font-semibold text-gray-900 mb-2">Новый пароль</h1>
            <p className="text-gray-600 mb-7">
              Используйте не менее 8 символов, включая хотя бы одну букву и одну цифру.
            </p>

            {formError || mutation.isError ? (
              <div className="mb-5 p-3 border border-red-200 bg-red-50 rounded-lg text-sm text-red-700" role="alert">
                {formError || 'Ссылка недействительна или устарела. Запросите новую ссылку.'}
              </div>
            ) : null}

            <form onSubmit={handleSubmit} className="space-y-5">
              <div>
                <label htmlFor="new-password" className="block text-sm font-medium text-gray-700 mb-1">
                  Новый пароль
                </label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                  <input
                    id="new-password"
                    type="password"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    required
                    minLength={8}
                    autoComplete="new-password"
                    autoFocus
                    className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>

              <div>
                <label htmlFor="confirm-password" className="block text-sm font-medium text-gray-700 mb-1">
                  Повторите пароль
                </label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                  <input
                    id="confirm-password"
                    type="password"
                    value={confirmation}
                    onChange={(event) => setConfirmation(event.target.value)}
                    required
                    minLength={8}
                    autoComplete="new-password"
                    className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={mutation.isPending}
                className="w-full py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium disabled:opacity-50"
              >
                {mutation.isPending ? 'Сохраняем...' : 'Сохранить новый пароль'}
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
