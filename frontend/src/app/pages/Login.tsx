import { useState, useMemo } from 'react';
import { Link } from 'react-router';
import { Mail, Lock, ArrowRight, ShieldAlert, Clock, Eye, EyeOff } from 'lucide-react';
import logo from '@/assets/logo-color.svg';
import { useLogin } from '@/app/hooks/useAuth';
import { AxiosError } from 'axios';

function LoginError({ error }: { error: Error | null }) {
  const info = useMemo(() => {
    const axiosErr = error as AxiosError<{ detail?: string }>;
    const code =
      (axiosErr?.response?.data as Record<string, unknown>)?.code ??
      axiosErr?.response?.headers?.code;

    if (code === 'PARTNER_PENDING') {
      return {
        icon: <Clock className="w-5 h-5 text-yellow-600 flex-shrink-0 mt-0.5" />,
        bg: 'bg-yellow-50 border-yellow-200',
        text: 'text-yellow-800',
        message: 'Ваш аккаунт находится на проверке. Пожалуйста, дождитесь подтверждения администратором.',
      };
    }
    if (code === 'PARTNER_BLOCKED') {
      return {
        icon: <ShieldAlert className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />,
        bg: 'bg-red-50 border-red-200',
        text: 'text-red-800',
        message: 'Ваш аккаунт заблокирован. Обратитесь к администратору для получения информации.',
      };
    }
    return {
      icon: null,
      bg: 'bg-red-50 border-red-200',
      text: 'text-red-700',
      message: 'Неверный email или пароль',
    };
  }, [error]);

  return (
    <div className={`mb-4 p-3 border rounded-lg text-sm ${info.bg} ${info.text} flex items-start gap-2`}>
      {info.icon}
      <span>{info.message}</span>
    </div>
  );
}

export default function Login() {
  const loginMutation = useLogin();
  const [showPassword, setShowPassword] = useState(false);
  const [formData, setFormData] = useState({
    email: '',
    password: '',
  });
  
  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData({ ...formData, [name]: value });
  };
  
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    loginMutation.mutate({ email: formData.email, password: formData.password });
  };
  
  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
      <div className="w-full max-w-5xl grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Login Form */}
        <div className="bg-white rounded-2xl shadow-xl px-8 lg:px-10 pb-8 lg:pb-10 pt-6">
          <div className="flex justify-center mb-6 px-4">
            <img src={logo} alt="ЮРИТЕХ" className="w-full max-w-sm h-auto" />
          </div>
          
          <div className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-900 mb-2">
              Вход в систему
            </h2>
            <p className="text-gray-600">
              Войдите в партнерский кабинет для управления клиентами
            </p>
          </div>

          {loginMutation.isError && <LoginError error={loginMutation.error} />}
          
          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Email
              </label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                <input
                  type="email"
                  name="email"
                  value={formData.email}
                  onChange={handleChange}
                  required
                  placeholder="partner@example.com"
                  className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Пароль
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                <input
                  type={showPassword ? 'text' : 'password'}
                  name="password"
                  value={formData.password}
                  onChange={handleChange}
                  required
                  placeholder="Введите пароль"
                  className="w-full pl-10 pr-11 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((value) => !value)}
                  aria-label={showPassword ? 'Скрыть пароль' : 'Показать пароль'}
                  aria-pressed={showPassword}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded"
                >
                  {showPassword ? (
                    <EyeOff className="w-5 h-5" aria-hidden="true" />
                  ) : (
                    <Eye className="w-5 h-5" aria-hidden="true" />
                  )}
                </button>
              </div>
            </div>
            
            <div className="flex items-center justify-end">
              <a href="#" className="text-sm text-blue-600 hover:underline">
                Забыли пароль?
              </a>
            </div>
            
            <button
              type="submit"
              disabled={loginMutation.isPending}
              className="w-full py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium disabled:opacity-50"
            >
              {loginMutation.isPending ? 'Вход...' : 'Войти'}
            </button>
          </form>
          
          <div className="mt-6 text-center text-sm text-gray-600">
            Нужна помощь?{' '}
            <a href="#" className="text-blue-600 hover:underline font-medium">
              Свяжитесь с нами
            </a>
          </div>
          
        </div>
        
        {/* Registration Panel */}
        <div className="bg-gradient-to-br from-blue-600 to-indigo-700 rounded-2xl shadow-xl px-8 lg:px-10 pb-8 lg:pb-10 pt-0 text-white flex flex-col justify-center">
          <div className="mb-8">
            <h2 className="text-3xl font-semibold mb-4">
              Станьте партнером URITECH
            </h2>
            <p className="text-blue-100 text-lg mb-6">
              Присоединяйтесь к платформе для управления клиентами в процедуре банкротства
            </p>
          </div>
          
          <div className="space-y-4 mb-8">
            <div className="flex items-start gap-3">
              <div className="w-6 h-6 bg-white/20 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">
                <div className="w-2 h-2 bg-white rounded-full" />
              </div>
              <div>
                <h3 className="font-medium mb-1">Удобное управление клиентами</h3>
                <p className="text-blue-100 text-sm">
                  Ведите карточки клиентов до и во время судебного процесса
                </p>
              </div>
            </div>
            
            <div className="flex items-start gap-3">
              <div className="w-6 h-6 bg-white/20 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">
                <div className="w-2 h-2 bg-white rounded-full" />
              </div>
              <div>
                <h3 className="font-medium mb-1">Автоматизация документооборота</h3>
                <p className="text-blue-100 text-sm">
                  Подготовка и подача документов через единую платформу
                </p>
              </div>
            </div>
            
            <div className="flex items-start gap-3">
              <div className="w-6 h-6 bg-white/20 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">
                <div className="w-2 h-2 bg-white rounded-full" />
              </div>
              <div>
                <h3 className="font-medium mb-1">Аналитика и отчетность</h3>
                <p className="text-blue-100 text-sm">
                  Следите за статистикой и прогрессом ваших дел
                </p>
              </div>
            </div>
            
            <div className="flex items-start gap-3">
              <div className="w-6 h-6 bg-white/20 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">
                <div className="w-2 h-2 bg-white rounded-full" />
              </div>
              <div>
                <h3 className="font-medium mb-1">Поддержка 24/7</h3>
                <p className="text-blue-100 text-sm">
                  Наша команда всегда готова помочь вам
                </p>
              </div>
            </div>
          </div>
          
          <Link
            to="/register"
            className="inline-flex items-center justify-center gap-2 px-6 py-3 bg-white text-blue-600 rounded-lg hover:bg-blue-50 transition-colors font-medium"
          >
            Зарегистрироваться как партнёр
            <ArrowRight className="w-5 h-5" />
          </Link>
          
          <p className="text-blue-100 text-sm mt-4">
            Регистрация занимает всего несколько минут
          </p>
        </div>
      </div>
    </div>
  );
}
