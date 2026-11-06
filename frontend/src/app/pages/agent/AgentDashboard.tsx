import { useState } from 'react';
import { Link } from 'react-router';
import { Check, Copy, Loader2, Users, Wallet, TrendingUp, UserCheck } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { getAgentAccruals, getAgentMe } from '@/app/api/agent';
import { formatMoney } from '@/app/utils/money';

const STATUS_LABELS: Record<string, string> = {
  accrued: 'Начислено',
  paid: 'Выплачено',
  cancelled: 'Отменено',
  review: 'На проверке',
};

export default function AgentDashboard() {
  const { data: me, isLoading } = useQuery({ queryKey: ['agent', 'me'], queryFn: getAgentMe });
  const { data: accruals = [] } = useQuery({
    queryKey: ['agent', 'accruals'],
    queryFn: getAgentAccruals,
  });
  const [copied, setCopied] = useState(false);

  if (isLoading || !me) {
    return (
      <div className="py-20 flex justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-emerald-600" />
      </div>
    );
  }

  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(me.profile.referral_link);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch {
      setCopied(false);
    }
  };

  const cards = [
    { label: 'Партнёров', value: me.stats.partners, icon: Users, tone: 'text-blue-600 bg-blue-50' },
    { label: 'Клиентов', value: me.stats.clients, icon: UserCheck, tone: 'text-purple-600 bg-purple-50' },
    {
      label: 'Начислено',
      value: formatMoney(me.stats.accrued),
      icon: TrendingUp,
      tone: 'text-emerald-600 bg-emerald-50',
    },
    {
      label: 'Доступно к выплате',
      value: formatMoney(me.stats.available),
      icon: Wallet,
      tone: 'text-amber-600 bg-amber-50',
    },
  ];

  return (
    <div className="space-y-6 max-w-6xl">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">Здравствуйте, {me.profile.full_name.split(' ')[0]}</h1>
        <p className="text-sm text-gray-500 mt-1">
          Приводите партнёров и получайте 1 000 ₽ за каждого клиента, дошедшего до процедуры.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        {cards.map((card) => (
          <div key={card.label} className="bg-white border border-gray-200 rounded-xl p-4">
            <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${card.tone}`}>
              <card.icon className="w-5 h-5" />
            </div>
            <div className="mt-3 text-2xl font-semibold text-gray-900">{card.value}</div>
            <div className="text-xs text-gray-500">{card.label}</div>
          </div>
        ))}
      </div>

      <div className="bg-white border border-gray-200 rounded-xl p-5">
        <h2 className="text-base font-semibold text-gray-900 mb-1">Ваша ссылка для партнёров</h2>
        <p className="text-sm text-gray-500 mb-4">
          Отправьте ссылку юристу или компании. Партнёр закрепится за вами один раз — при регистрации.
        </p>
        <div className="flex flex-col sm:flex-row gap-2">
          <input
            readOnly
            value={me.profile.referral_link}
            className="flex-1 px-3 py-2.5 border border-gray-300 rounded-lg text-sm font-mono text-gray-700 bg-gray-50"
          />
          <button
            onClick={copyLink}
            className="inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-emerald-600 text-white text-sm font-medium hover:bg-emerald-700"
          >
            {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
            {copied ? 'Скопировано' : 'Скопировать'}
          </button>
        </div>
        <p className="mt-3 text-xs text-gray-400">
          Код агента: <span className="font-mono">{me.profile.code}</span>
        </p>
      </div>

      <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <h2 className="text-base font-semibold text-gray-900">Последние начисления</h2>
          <Link to="/agent/accruals" className="text-sm text-emerald-700 hover:underline">
            Все начисления
          </Link>
        </div>
        {accruals.length === 0 ? (
          <div className="px-5 py-10 text-center text-sm text-gray-500">
            Пока нет начислений. Они появятся, когда клиент вашего партнёра дойдёт до процедуры.
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {accruals.slice(0, 5).map((item) => (
              <div key={item.id} className="flex items-center justify-between px-5 py-3">
                <div>
                  <div className="text-sm text-gray-900">{item.partner_name}</div>
                  <div className="text-xs text-gray-500">
                    Клиент №{item.client_ref} · {new Date(item.created_at).toLocaleDateString('ru-RU')}
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-sm font-medium text-gray-900">{formatMoney(item.amount)}</div>
                  <div className="text-xs text-gray-500">{STATUS_LABELS[item.status] ?? item.status}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
