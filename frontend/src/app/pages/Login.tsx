import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router';
import {
  ArrowRight,
  Clock,
  Eye,
  EyeOff,
  Handshake,
  Lock,
  Mail,
  ShieldAlert,
  ShieldCheck,
  Users,
} from 'lucide-react';
import logo from '@/assets/logo-color.svg';
import { useLogin } from '@/app/hooks/useAuth';
import { AxiosError } from 'axios';
import SmartCaptcha, { CAPTCHA_ENABLED } from '@/app/components/SmartCaptcha';

type Role = 'agent' | 'partner' | 'admin';

const ROLE_OPTIONS: { id: Role; label: string; icon: typeof Handshake }[] = [
  { id: 'agent', label: 'Агент', icon: Handshake },
  { id: 'partner', label: 'Партнёр', icon: Users },
  { id: 'admin', label: 'Администратор', icon: ShieldCheck },
];

const ROLE_TEXT: Record<Role, { heading: string; subtitle: string }> = {
  agent: {
    heading: 'Вход в кабинет агента',
    subtitle: 'Партнёры, начисления и выплаты в одном месте',
  },
  partner: {
    heading: 'Вход в партнёрский кабинет',
    subtitle: 'Управляйте клиентами и документами',
  },
  admin: {
    heading: 'Вход для администратора',
    subtitle: 'Доступ выдаёт супер-администратор по приглашению',
  },
};

const ROLE_RIGHT: Record<
  Role,
  { title: string; subtitle: string; bullets: string[]; cta?: { label: string; to: string } }
> = {
  agent: {
    title: 'Агентская программа URITECH',
    subtitle: 'Приводите юристов и юридические компании — получайте вознаграждение за их клиентов.',
    bullets: [
      '1 000 ₽ за клиента, дошедшего до процедуры',
      'Личная ссылка для привлечения партнёров',
      'Заявка на выплату и статусы в кабинете',
    ],
    cta: { label: 'Стать агентом', to: '/become-agent' },
  },
  partner: {
    title: 'Станьте партнером URITECH',
    subtitle: 'Присоединяйтесь к платформе для управления клиентами в процедуре банкротства',
    bullets: [
      'Удобное управление клиентами',
      'Автоматизация документооборота',
      'Аналитика и отчетность',
      'Поддержка 24/7',
    ],
    cta: { label: 'Зарегистрироваться как партнёр', to: '/register' },
  },
  admin: {
    title: 'Администрирование',
    subtitle: 'Рабочее место сотрудника: партнёры, клиенты, агенты и деньги.',
    bullets: [
      'Все партнёры, клиенты и агенты',
      'Журнал действий сотрудников',
      'Управление доступами и приглашениями',
    ],
  },
};

function LoginError({ error }: { error: Error | null }) {
  const info = useMemo(() => {
    const axiosErr = error as AxiosError<{ detail?: { code?: string } | string; code?: string }>;
    const detail = axiosErr?.response?.data?.detail;
    const detailCode = typeof detail === 'object' && detail ? detail.code : undefined;
    const code =
      detailCode ??
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
    if (code === 'CAPTCHA_REQUIRED') {
      return {
        icon: null,
        bg: 'bg-blue-50 border-blue-200',
        text: 'text-blue-800',
        message: 'Подтвердите, что вы не робот, и войдите снова.',
      };
    }
    if (code === 'CAPTCHA_INVALID') {
      return {
        icon: null,
        bg: 'bg-red-50 border-red-200',
        text: 'text-red-700',
        message: 'Капча не прошла проверку. Попробуйте ещё раз.',
      };
    }
    if (code === 'ACCOUNT_LOCKED') {
      return {
        icon: <Clock className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />,
        bg: 'bg-red-50 border-red-200',
        text: 'text-red-800',
        message: 'Слишком много неудачных попыток. Повторите через 15 минут.',
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
  const [captchaToken, setCaptchaToken] = useState('');
  const [captchaKey, setCaptchaKey] = useState(0);
  const [role, setRole] = useState<Role>('partner');

  const errorCode = useMemo(() => {
    const axiosErr = loginMutation.error as AxiosError<{ detail?: { code?: string } }> | null;
    const detail = axiosErr?.response?.data?.detail;
    return typeof detail === 'object' && detail ? detail.code : undefined;
  }, [loginMutation.error]);

  const captchaRequired = errorCode === 'CAPTCHA_REQUIRED' && CAPTCHA_ENABLED;

  useEffect(() => {
    if (errorCode === 'CAPTCHA_INVALID') {
      setCaptchaToken('');
      setCaptchaKey((value) => value + 1);
    }
  }, [errorCode]);

  const [formData, setFormData] = useState({
    identifier: '',
    password: '',
  });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData({ ...formData, [name]: value });
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    loginMutation.mutate({
      identifier: formData.identifier,
      password: formData.password,
      captcha_token: captchaRequired ? captchaToken : undefined,
    });
  };

  const text = ROLE_TEXT[role];
  const right = ROLE_RIGHT[role];

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
      <div className="w-full max-w-5xl grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Вход */}
        <div className="bg-white rounded-2xl shadow-xl px-8 lg:px-10 pb-8 lg:pb-10 pt-6">
          <div className="flex justify-center mb-6 px-4">
            <img src={logo} alt="ЮРИТЕХ" className="w-full max-w-sm h-auto" />
          </div>

          <div className="grid grid-cols-3 gap-2 mb-7">
            {ROLE_OPTIONS.map((option) => {
              const active = role === option.id;
              return (
                <button
                  key={option.id}
                  type="button"
                  onClick={() => setRole(option.id)}
                  aria-pressed={active}
                  className={`flex flex-col items-center gap-1.5 rounded-xl border px-2 py-3 text-xs transition-colors ${
                    active
                      ? 'border-blue-500 bg-blue-50 text-blue-700'
                      : 'border-gray-200 text-gray-500 hover:border-gray-300'
                  }`}
                >
                  <option.icon className="w-5 h-5" />
                  {option.label}
                </button>
              );
            })}
          </div>

          <div className="mb-6">
            <h2 className="text-2xl font-semibold text-gray-900 mb-2">{text.heading}</h2>
            <p className="text-gray-600">{text.subtitle}</p>
          </div>

          {loginMutation.isError && <LoginError error={loginMutation.error} />}

          {captchaRequired && (
            <div className="mb-4">
              <p className="text-sm text-gray-600 mb-2">Подтвердите, что вы не робот</p>
              <SmartCaptcha key={captchaKey} onToken={setCaptchaToken} />
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Email или логин</label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                <input
                  type="text"
                  name="identifier"
                  value={formData.identifier}
                  onChange={handleChange}
                  required
                  autoComplete="username"
                  placeholder="ivanov@uritech.ru или i.ivanov"
                  className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Пароль</label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                <input
                  type={showPassword ? 'text' : 'password'}
                  name="password"
                  value={formData.password}
                  onChange={handleChange}
                  required
                  autoComplete="current-password"
                  placeholder="Введите пароль"
                  className="w-full pl-10 pr-12 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((value) => !value)}
                  aria-label={showPassword ? 'Скрыть пароль' : 'Показать пароль'}
                  aria-pressed={showPassword}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded"
                >
                  {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
            </div>

            <div className="flex items-center justify-end">
              <Link
                to="/forgot-password"
                state={{ email: formData.identifier }}
                className="text-sm text-blue-600 hover:underline"
              >
                Забыли пароль?
              </Link>
            </div>

            <button
              type="submit"
              disabled={loginMutation.isPending || (captchaRequired && !captchaToken)}
              className="w-full flex items-center justify-center gap-2 bg-blue-600 text-white py-3 rounded-lg hover:bg-blue-700 transition-colors font-medium disabled:opacity-50"
            >
              {loginMutation.isPending ? 'Вход…' : 'Войти'}
              {!loginMutation.isPending && <ArrowRight className="w-4 h-4" />}
            </button>
          </form>

          <div className="mt-6 text-sm text-center">
            {role === 'agent' && (
              <p className="text-gray-600">
                Ещё нет кабинета?{' '}
                <Link to="/become-agent" className="text-emerald-700 hover:underline font-medium">
                  Стать агентом
                </Link>
              </p>
            )}
            {role === 'partner' && (
              <p className="text-gray-600">
                Ещё нет кабинета?{' '}
                <Link to="/register" className="text-blue-600 hover:underline font-medium">
                  Зарегистрироваться как партнёр
                </Link>
              </p>
            )}
            {role === 'admin' && (
              <p className="text-gray-500">Нет доступа? Обратитесь к супер-администратору.</p>
            )}
          </div>

          <div className="mt-4 text-sm text-gray-500 text-center">
            Нужна помощь?{' '}
            <a href="mailto:support@uritech.ru" className="text-blue-600 hover:underline">
              Свяжитесь с нами
            </a>
          </div>
        </div>

        {/* Правая панель */}
        <div className="hidden lg:flex bg-gradient-to-br from-blue-600 to-indigo-700 rounded-2xl shadow-xl p-10 flex-col justify-center text-white">
          <h2 className="text-3xl font-bold mb-4">{right.title}</h2>
          <p className="text-blue-100 mb-8">{right.subtitle}</p>

          <div className="space-y-5 mb-8">
            {right.bullets.map((bullet) => (
              <div key={bullet} className="flex items-start gap-3">
                <div className="w-6 h-6 bg-white/20 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">
                  <div className="w-2 h-2 bg-white rounded-full" />
                </div>
                <p className="text-blue-50">{bullet}</p>
              </div>
            ))}
          </div>

          {right.cta && (
            <Link
              to={right.cta.to}
              className="bg-white text-blue-600 px-6 py-3 rounded-lg font-semibold hover:bg-blue-50 transition-colors text-center"
            >
              {right.cta.label}
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}
