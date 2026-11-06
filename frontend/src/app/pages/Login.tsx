import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router';
import {
  ArrowRight,
  Check,
  Clock,
  Eye,
  EyeOff,
  FileText,
  Handshake,
  HelpCircle,
  Lock,
  Mail,
  ShieldAlert,
  ShieldCheck,
  UserCheck,
  Users,
  Wallet,
} from 'lucide-react';
import logo from '@/assets/logo-color.svg';
import { useLogin } from '@/app/hooks/useAuth';
import { AxiosError } from 'axios';
import SmartCaptcha, { CAPTCHA_ENABLED } from '@/app/components/SmartCaptcha';

type Role = 'agent' | 'partner' | 'admin';

const ROLES: { id: Role; label: string; hint: string; icon: typeof Handshake }[] = [
  { id: 'partner', label: 'Партнёр', hint: 'Клиенты и работа', icon: Users },
  { id: 'agent', label: 'Агент', hint: 'Партнёры и выплаты', icon: Handshake },
  { id: 'admin', label: 'Администратор', hint: 'Управление кабинетом', icon: ShieldCheck },
];

interface RoleCopy {
  headline: string;
  subheadline: string;
  cardTitle: string;
  cardSubtitle: string;
  rightTitle: string;
  rightSubtitle: string;
  bullets: string[];
  cta?: { label: string; to: string };
  steps: { title: string; text: string; icon: typeof Handshake }[];
  faq: { q: string; a: string }[];
}

const COPY: Record<Role, RoleCopy> = {
  agent: {
    headline: 'Приводите партнёров. Получайте «вечные» выплаты.',
    subheadline:
      'Агент — юрист или компания, которая приводит партнёров. Партнёр передаёт клиентов, вы получаете вознаграждение за каждого, кто дошёл до процедуры.',
    cardTitle: 'Кабинет агента',
    cardSubtitle: 'Доступ только для агентов.',
    rightTitle: 'Вы развиваете партнёрскую сеть',
    rightSubtitle: 'Ваша ссылка — ваш инструмент. Партнёр закрепляется за вами один раз и навсегда.',
    bullets: [
      '1 000 ₽ за нового клиента — без ограничения срока программы',
      'Понятные выплаты: статусы и история в кабинете',
      'Поддержка: поможем с приглашением и начислениями',
    ],
    cta: { label: 'Стать агентом', to: '/become-agent' },
    steps: [
      { title: 'Вы — Агент', text: 'Приглашаете юристов и компании по своей ссылке.', icon: Handshake },
      { title: 'Партнёр', text: 'Регистрируется по ссылке и закрепляется за вами.', icon: Users },
      { title: 'Клиенты', text: 'Партнёр передаёт клиентов в ЮРИТЕХ.', icon: UserCheck },
      {
        title: 'Выплаты',
        text: '1 000 ₽ за каждого клиента, дошедшего до процедуры.',
        icon: Wallet,
      },
    ],
    faq: [
      {
        q: 'Что важно знать?',
        a: 'Вознаграждение начисляется один раз за клиента, дошедшего до введения в процедуру. Повторные события и переходы дальше по делу вторую выплату не дают.',
      },
      {
        q: 'Когда начисляются вознаграждения?',
        a: 'В момент, когда клиент партнёра переходит в статус «введение в процедуру». Начисление сразу видно в кабинете агента.',
      },
      {
        q: 'Как получить выплату?',
        a: 'Заполните реквизиты, дождитесь проверки и отправьте заявку. Заявка до 14-го числа попадает в выплату 15-го, позже — в следующий цикл.',
      },
    ],
  },
  partner: {
    headline: 'Ваши клиенты. Единое пространство для работы.',
    subheadline:
      'Клиенты, документы, задачи и финансы — в одном кабинете. Передавайте клиентов и следите за прогрессом дел в ЮРИТЕХ.',
    cardTitle: 'Кабинет партнёра',
    cardSubtitle: 'Доступ для партнёров и их сотрудников.',
    rightTitle: 'Вы передаёте клиентов',
    rightSubtitle: 'Партнёр работает с клиентами и передаёт их в ЮРИТЕХ на сопровождение.',
    bullets: [
      'Клиенты и документы в одном месте',
      'Задачи и статусы по каждому делу',
      'Финансы и закрывающие документы',
    ],
    cta: { label: 'Стать партнёром', to: '/register' },
    steps: [
      { title: 'Вы — Партнёр', text: 'Регистрируетесь и получаете доступ в кабинет.', icon: Users },
      { title: 'Клиент', text: 'Добавляете клиента и его документы.', icon: UserCheck },
      { title: 'ЮРИТЕХ', text: 'Берём дело на сопровождение и ведём процедуру.', icon: FileText },
      { title: 'Результат', text: 'Следите за статусом и финансами в кабинете.', icon: Wallet },
    ],
    faq: [
      {
        q: 'Что важно знать?',
        a: 'Клиенты остаются в существующей системе. Кабинет партнёра не меняет правила работы, только делает их удобнее.',
      },
      {
        q: 'Как пользоваться кабинетом?',
        a: 'Войдите по почте или логину, которые указали при регистрации. Если пароль забыт — восстановите его по ссылке на этой странице.',
      },
      {
        q: 'Я сотрудник партнёра',
        a: 'Попросите руководителя добавить вас в кабинет. Вход — по личной почте и паролю, общие логины больше не используются.',
      },
    ],
  },
  admin: {
    headline: 'Рабочее место сотрудника.',
    subheadline:
      'Партнёры, клиенты, агенты, деньги и журнал действий. Каждый сотрудник входит под своим логином, все действия остаются в истории.',
    cardTitle: 'Кабинет администратора',
    cardSubtitle: 'Доступ выдаёт супер-администратор по приглашению.',
    rightTitle: 'Вы управляете кабинетом',
    rightSubtitle: 'Рабочие разделы и полный журнал: кто, что и когда сделал.',
    bullets: [
      'Партнёры, клиенты и агенты',
      'Начисления, заявки и выплаты',
      'Журнал действий сотрудников',
    ],
    steps: [
      { title: 'Приглашение', text: 'Супер-администратор присылает ссылку.', icon: Mail },
      { title: 'Вход', text: 'Создаёте личный пароль и входите.', icon: Lock },
      { title: 'Работа', text: 'Ведёте партнёров, клиентов и агентов.', icon: FileText },
      { title: 'Журнал', text: 'Каждое действие фиксируется с автором.', icon: ShieldCheck },
    ],
    faq: [
      {
        q: 'Как получить доступ?',
        a: 'Обратитесь к супер-администратору: он выпустит приглашение на вашу почту. Публичной регистрации для администраторов нет.',
      },
      {
        q: 'Что видно в журнале?',
        a: 'Входы, приглашения, смену ролей и блокировки, привязки партнёров к агентам, начисления и выплаты — с автором и временем.',
      },
      {
        q: 'Пароль можно восстановить?',
        a: 'Да, по ссылке «Забыли пароль?». Сброс завершает все активные сессии на других устройствах.',
      },
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
        message: 'Ваш аккаунт находится на проверке. Дождитесь подтверждения администратором.',
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
        message: 'Ваш аккаунт заблокирован. Обратитесь к администратору.',
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
  const [role, setRole] = useState<Role>('partner');
  const [showPassword, setShowPassword] = useState(false);
  const [captchaToken, setCaptchaToken] = useState('');
  const [captchaKey, setCaptchaKey] = useState(0);
  const [formData, setFormData] = useState({ identifier: '', password: '' });

  const copy = COPY[role];

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

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    loginMutation.mutate({
      identifier: formData.identifier,
      password: formData.password,
      captcha_token: captchaRequired ? captchaToken : undefined,
    });
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 py-5">
        <header className="flex items-center justify-between border-b border-gray-200 pb-4">
          <img src={logo} alt="ЮРИТЕХ" className="h-9 sm:h-10" />
          <a href="mailto:support@uritech.ru" className="text-sm text-gray-500 hover:text-gray-800">
            Помощь по сотрудничеству
          </a>
        </header>

        <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-[210px_minmax(0,1fr)_330px] lg:gap-8">
          {/* Слева: выбор кабинета */}
          <div>
            <div className="text-[11px] uppercase tracking-wider text-gray-400 mb-3">
              Выберите кабинет
            </div>
            <div className="grid grid-cols-3 gap-2 lg:grid-cols-1 lg:gap-2">
              {ROLES.map((option) => {
                const active = role === option.id;
                return (
                  <button
                    key={option.id}
                    type="button"
                    onClick={() => setRole(option.id)}
                    aria-pressed={active}
                    className={`flex items-center gap-3 rounded-xl border px-3 py-3 text-left transition-colors ${
                      active
                        ? 'border-blue-500 bg-blue-50'
                        : 'border-gray-200 bg-white hover:border-gray-300'
                    }`}
                  >
                    <span
                      className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${
                        active ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-500'
                      }`}
                    >
                      <option.icon className="h-4 w-4" />
                    </span>
                    <span className="min-w-0">
                      <span
                        className={`block text-sm font-medium ${
                          active ? 'text-blue-700' : 'text-gray-900'
                        }`}
                      >
                        {option.label}
                      </span>
                      <span className="hidden lg:block text-xs text-gray-500">{option.hint}</span>
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Центр: форма */}
          <div className="min-w-0">
            <div className="text-[11px] uppercase tracking-wider text-blue-600 mb-2">
              {role === 'agent' ? 'Агентский кабинет' : role === 'partner' ? 'Кабинет партнёра' : 'Кабинет администратора'}
            </div>
            <h1 className="text-2xl sm:text-3xl font-semibold text-gray-900 leading-tight">
              {copy.headline}
            </h1>
            <p className="mt-3 text-sm sm:text-base text-gray-600 max-w-xl">{copy.subheadline}</p>

            <div className="mt-6 rounded-2xl border border-gray-200 bg-white p-5 sm:p-6 shadow-sm max-w-xl">
              <h2 className="text-lg font-semibold text-gray-900">{copy.cardTitle}</h2>
              <p className="text-sm text-gray-500 mt-1">{copy.cardSubtitle}</p>

              <div className="mt-5">
                {loginMutation.isError && <LoginError error={loginMutation.error} />}

                {captchaRequired && (
                  <div className="mb-4">
                    <p className="text-sm text-gray-600 mb-2">Подтвердите, что вы не робот</p>
                    <SmartCaptcha key={captchaKey} onToken={setCaptchaToken} />
                  </div>
                )}

                <form onSubmit={handleSubmit} className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
                    <div className="relative">
                      <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
                      <input
                        type="text"
                        name="identifier"
                        value={formData.identifier}
                        onChange={handleChange}
                        required
                        autoComplete="username"
                        placeholder="Email или логин"
                        className="w-full pl-10 pr-3 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Пароль</label>
                    <div className="relative">
                      <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
                      <input
                        type={showPassword ? 'text' : 'password'}
                        name="password"
                        value={formData.password}
                        onChange={handleChange}
                        required
                        autoComplete="current-password"
                        placeholder="Введите пароль"
                        className="w-full pl-10 pr-11 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword((value) => !value)}
                        aria-label={showPassword ? 'Скрыть пароль' : 'Показать пароль'}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                      >
                        {showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                      </button>
                    </div>
                  </div>

                  <div className="flex justify-end">
                    <Link
                      to="/forgot-password"
                      state={{ email: formData.identifier }}
                      className="text-sm text-gray-500 hover:text-blue-600 hover:underline"
                    >
                      Забыли пароль?
                    </Link>
                  </div>

                  <button
                    type="submit"
                    disabled={loginMutation.isPending || (captchaRequired && !captchaToken)}
                    className="w-full flex items-center justify-center gap-2 bg-blue-600 text-white py-2.5 rounded-lg hover:bg-blue-700 font-medium disabled:opacity-50"
                  >
                    {loginMutation.isPending ? 'Вход…' : 'Войти в кабинет'}
                    {!loginMutation.isPending && <ArrowRight className="h-4 w-4" />}
                  </button>
                </form>

                {copy.cta && (
                  <p className="mt-4 text-sm text-center text-gray-600">
                    Ещё нет кабинета?{' '}
                    <Link to={copy.cta.to} className="text-blue-600 hover:underline font-medium">
                      {copy.cta.label}
                    </Link>
                  </p>
                )}
                {role === 'admin' && (
                  <p className="mt-4 text-sm text-center text-gray-500">
                    Нет доступа? Обратитесь к супер-администратору.
                  </p>
                )}
              </div>
            </div>
          </div>

          {/* Справа: пояснение */}
          <aside className="rounded-2xl bg-blue-50/70 border border-blue-100 p-5 sm:p-6">
            <h3 className="text-base font-semibold text-gray-900">{copy.rightTitle}</h3>
            <p className="mt-2 text-sm text-gray-600">{copy.rightSubtitle}</p>

            <ul className="mt-4 space-y-3">
              {copy.bullets.map((bullet) => (
                <li key={bullet} className="flex gap-2.5 text-sm text-gray-700">
                  <Check className="mt-0.5 h-4 w-4 shrink-0 text-blue-600" />
                  <span>{bullet}</span>
                </li>
              ))}
            </ul>

            {copy.cta && (
              <Link
                to={copy.cta.to}
                className="mt-5 inline-flex items-center gap-1.5 text-sm font-medium text-blue-700 hover:underline"
              >
                {copy.cta.label}
                <ArrowRight className="h-4 w-4" />
              </Link>
            )}
          </aside>
        </div>

        {/* Как это работает */}
        <section className="mt-10 border-t border-gray-200 pt-8">
          <h2 className="text-lg font-semibold text-gray-900">Как это работает</h2>
          <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {copy.steps.map((step) => (
              <div key={step.title} className="rounded-xl border border-gray-200 bg-white p-4">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gray-100 text-gray-600">
                  <step.icon className="h-4 w-4" />
                </div>
                <div className="mt-3 text-sm font-medium text-gray-900">{step.title}</div>
                <p className="mt-1 text-xs text-gray-500 leading-relaxed">{step.text}</p>
              </div>
            ))}
          </div>

          <div className="mt-5 flex items-start gap-2 text-xs text-gray-500">
            <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-gray-400" />
            <p>
              Все входы и действия сотрудников фиксируются в журнале. Пароли хранятся в защищённом
              виде и не видны никому, включая администраторов.
            </p>
          </div>
        </section>

        {/* Частые вопросы */}
        <section className="mt-6 mb-8">
          <h2 className="text-base font-semibold text-gray-900 mb-3">Частые вопросы</h2>
          <div className="divide-y divide-gray-200 rounded-xl border border-gray-200 bg-white">
            {copy.faq.map((item) => (
              <details key={item.q} className="group p-4">
                <summary className="flex cursor-pointer list-none items-center justify-between gap-3 text-sm font-medium text-gray-900">
                  <span className="flex items-center gap-2">
                    <HelpCircle className="h-4 w-4 text-gray-400" />
                    {item.q}
                  </span>
                  <span className="text-gray-400 transition-transform group-open:rotate-45">+</span>
                </summary>
                <p className="mt-2 pl-6 text-sm text-gray-600 leading-relaxed">{item.a}</p>
              </details>
            ))}
          </div>
        </section>

        <footer className="flex items-center justify-between border-t border-gray-200 py-4 text-xs text-gray-400">
          <img src={logo} alt="ЮРИТЕХ" className="h-6 opacity-70" />
          <span>© ЮРИТЕХ, юридическая онлайн-платформа</span>
          <a href="#top" className="hover:text-gray-600">
            Наверх
          </a>
        </footer>
      </div>
    </div>
  );
}
