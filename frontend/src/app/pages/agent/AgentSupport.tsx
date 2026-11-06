import { HelpCircle, Mail, MessageSquare, ShieldCheck } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router';
import { getAgentMe } from '@/app/api/agent';

const FAQ = [
  {
    q: 'Когда начисляется вознаграждение?',
    a: 'В момент, когда клиент партнёра переходит в статус «введение в процедуру». Начисление сразу появляется в разделе «Начисления», уведомление приходит в кабинет.',
  },
  {
    q: 'Почему нет начисления, хотя клиент передан?',
    a: 'Передача клиента — это статистика, а не деньги. Начисление появляется только после введения в процедуру. Если статус уже сменился, а начисления нет — напишите в поддержку с номером клиента.',
  },
  {
    q: 'Как получить выплату?',
    a: 'Заполните реквизиты в кабинете и дождитесь проверки. Затем отправьте заявку на выплату. Заявка до 14-го числа попадает в выплату 15-го, позже — в следующий цикл.',
  },
  {
    q: 'Почему реквизиты вернули на правки?',
    a: 'Обычно из-за несовпадения получателя, ИНН или счёта. Проверьте данные, отправьте заново — администратор проверит повторно.',
  },
  {
    q: 'Партнёр закрепился не за мной',
    a: 'Закрепление происходит один раз при регистрации по ссылке. Если партнёр ошибся со ссылкой, напишите в поддержку: администратор исправит привязку с причиной, изменение попадёт в журнал.',
  },
  {
    q: 'Как поменять почту или пароль?',
    a: 'Пароль меняется по ссылке «Забыли пароль?» на странице входа. Для смены почты напишите в поддержку — это делает администратор.',
  },
];

export default function AgentSupport() {
  const { data: me } = useQuery({ queryKey: ['agent', 'me'], queryFn: getAgentMe });
  const code = me?.profile.code ?? '';
  const subject = encodeURIComponent(`Вопрос агента${code ? ` ${code}` : ''}`);
  const mailto = `mailto:support@uritech.ru?subject=${subject}`;

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">Поддержка</h1>
        <p className="text-sm text-gray-500 mt-1">
          Поможем с приглашениями, начислениями, выплатами и реквизитами.
        </p>
      </div>

      <div className="bg-white border border-gray-200 rounded-xl p-5 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-3">
          <div className="w-11 h-11 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center shrink-0">
            <Mail className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-gray-900">Написать в поддержку</h2>
            <p className="text-sm text-gray-500">
              support@uritech.ru
              {code && <> · укажите код агента <span className="font-mono">{code}</span></>}
            </p>
          </div>
        </div>
        <a
          href={mailto}
          className="inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-emerald-600 text-white text-sm font-medium hover:bg-emerald-700"
        >
          <MessageSquare className="w-4 h-4" />
          Написать письмо
        </a>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-white border border-gray-200 rounded-xl p-5">
          <h2 className="text-sm font-semibold text-gray-900">Что приложить к обращению</h2>
          <ul className="mt-3 space-y-2 text-sm text-gray-600">
            <li>• код агента или ссылку на кабинет;</li>
            <li>• почту партнёра, если вопрос про привязку;</li>
            <li>• номер клиента или скриншот, если вопрос про начисление;</li>
            <li>• дату и сумму, если вопрос про выплату.</li>
          </ul>
          <p className="mt-3 text-xs text-gray-400">
            Так мы ответим быстрее и не попросим данные повторно.
          </p>
        </div>

        <div className="bg-white border border-gray-200 rounded-xl p-5">
          <h2 className="text-sm font-semibold text-gray-900">Полезные разделы</h2>
          <div className="mt-3 space-y-2 text-sm">
            <Link to="/agent/payouts" className="block text-emerald-700 hover:underline">
              Выплаты и статусы заявок
            </Link>
            <Link to="/agent/accruals" className="block text-emerald-700 hover:underline">
              Начисления по клиентам
            </Link>
            <Link to="/agent/requisites" className="block text-emerald-700 hover:underline">
              Реквизиты и проверка
            </Link>
            <Link to="/agent/materials" className="block text-emerald-700 hover:underline">
              Материалы для приглашений
            </Link>
          </div>
          <div className="mt-4 flex items-start gap-2 text-xs text-gray-400">
            <ShieldCheck className="mt-0.5 w-4 h-4 shrink-0" />
            Не отправляйте в поддержку паспортные данные клиентов — они не нужны для решения вопроса.
          </div>
        </div>
      </div>

      <div>
        <h2 className="text-lg font-semibold text-gray-900 mb-3">Частые вопросы</h2>
        <div className="divide-y divide-gray-200 rounded-xl border border-gray-200 bg-white">
          {FAQ.map((item) => (
            <details key={item.q} className="group p-4">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-3 text-sm font-medium text-gray-900">
                <span className="flex items-center gap-2">
                  <HelpCircle className="w-4 h-4 text-gray-400" />
                  {item.q}
                </span>
                <span className="text-gray-400 transition-transform group-open:rotate-45">+</span>
              </summary>
              <p className="mt-2 pl-6 text-sm text-gray-600 leading-relaxed">{item.a}</p>
            </details>
          ))}
        </div>
      </div>
    </div>
  );
}
