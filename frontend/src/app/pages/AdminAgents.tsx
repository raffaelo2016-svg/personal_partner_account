import { useState } from 'react';
import { CheckCircle2, Loader2, ShieldOff, ShieldCheck } from 'lucide-react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  correctAccrual,
  getAgentDetail,
  listAgents,
  reviewAgentRequisites,
  setAgentStatus,
  updatePayoutStatus,
  type AgentPayout,
} from '@/app/api/agent';
import { formatMoney } from '@/app/utils/money';
import { getApiErrorMessage } from '@/app/utils/apiError';

const STATUS_LABELS: Record<string, string> = {
  active: 'Активен',
  blocked: 'Заблокирован',
};

const REQ_LABELS: Record<string, string> = {
  empty: 'Не заполнены',
  sent: 'На проверке',
  accepted: 'Подтверждены',
  needs_fix: 'Нужны правки',
};

const ACCRUAL_LABELS: Record<string, string> = {
  accrued: 'Начислено',
  review: 'На проверке',
  cancelled: 'Отменено',
  paid: 'Выплачено',
};

const PAYOUT_LABELS: Record<string, string> = {
  submitted: 'Отправлена',
  checking: 'Проверяем',
  scheduled: 'В выплате',
  paid: 'Выплачена',
  needs_fix: 'Нужны правки',
  cancelled: 'Отменена',
};

const PAYOUT_ACTIONS: { status: string; label: string }[] = [
  { status: 'checking', label: 'Проверяю' },
  { status: 'scheduled', label: 'В выплату' },
  { status: 'paid', label: 'Выплачено' },
  { status: 'needs_fix', label: 'Нужны правки' },
];

export default function AdminAgents() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const { data: agents = [], isLoading } = useQuery({
    queryKey: ['admin', 'agents', search],
    queryFn: () => listAgents(search.trim() || undefined),
  });

  const { data: detail } = useQuery({
    queryKey: ['admin', 'agent', selected],
    queryFn: () => getAgentDetail(selected as string),
    enabled: Boolean(selected),
  });

  const statusMutation = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) =>
      setAgentStatus(id, active, undefined),
    onSuccess: async () => {
      setNotice('Статус агента обновлён');
      await queryClient.invalidateQueries({ queryKey: ['admin', 'agents'] });
      await queryClient.invalidateQueries({ queryKey: ['admin', 'agent', selected] });
    },
    onError: (err) => setError(getApiErrorMessage(err)),
  });

  const requisitesMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: 'accepted' | 'needs_fix' }) =>
      reviewAgentRequisites(id, status),
    onSuccess: async () => {
      setNotice('Реквизиты проверены');
      await queryClient.invalidateQueries({ queryKey: ['admin', 'agent', selected] });
    },
    onError: (err) => setError(getApiErrorMessage(err)),
  });

  const accrualMutation = useMutation({
    mutationFn: ({ id, status, reason }: { id: string; status: 'accrued' | 'cancelled'; reason: string }) =>
      correctAccrual(id, { status, reason }),
    onSuccess: async () => {
      setNotice('Начисление скорректировано');
      await queryClient.invalidateQueries({ queryKey: ['admin', 'agent', selected] });
      await queryClient.invalidateQueries({ queryKey: ['admin', 'agents'] });
    },
    onError: (err) => setError(getApiErrorMessage(err)),
  });

  const handleAccrualCorrection = (accrualId: string, status: 'accrued' | 'cancelled') => {
    const reason = window.prompt(
      status === 'cancelled' ? 'Причина отмены начисления' : 'Причина восстановления начисления',
    );
    if (!reason || reason.trim().length < 3) return;
    accrualMutation.mutate({ id: accrualId, status, reason: reason.trim() });
  };

  const payoutMutation = useMutation({
    mutationFn: ({ payout, status }: { payout: AgentPayout; status: string }) =>
      updatePayoutStatus(payout.id, status),
    onSuccess: async () => {
      setNotice('Статус заявки обновлён');
      await queryClient.invalidateQueries({ queryKey: ['admin', 'agent', selected] });
    },
    onError: (err) => setError(getApiErrorMessage(err)),
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Агенты</h1>
          <p className="text-sm text-gray-500 mt-1">
            Кто приводит партнёров, сколько начислено и какие заявки ждут выплаты.
          </p>
        </div>
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Имя, код или компания"
          className="w-full sm:w-64 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      {error && (
        <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">{error}</div>
      )}
      {notice && (
        <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-sm text-emerald-700">
          {notice}
        </div>
      )}

      {isLoading ? (
        <div className="py-16 flex justify-center">
          <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
        </div>
      ) : (
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-xs uppercase tracking-wide text-gray-500">
              <tr>
                <th className="text-left px-4 py-3">Агент</th>
                <th className="text-left px-4 py-3">Код</th>
                <th className="text-right px-4 py-3">Партнёров</th>
                <th className="text-right px-4 py-3">Начислено</th>
                <th className="text-right px-4 py-3">Доступно</th>
                <th className="text-left px-4 py-3">Реквизиты</th>
                <th className="text-left px-4 py-3">Статус</th>
              </tr>
            </thead>
            <tbody>
              {agents.map((agent) => (
                <tr
                  key={agent.id}
                  onClick={() => setSelected(agent.id)}
                  className={`border-t border-gray-100 cursor-pointer hover:bg-gray-50 ${
                    selected === agent.id ? 'bg-blue-50/40' : ''
                  }`}
                >
                  <td className="px-4 py-3">
                    <div className="font-medium text-gray-900">{agent.full_name}</div>
                    <div className="text-xs text-gray-500">{agent.email}</div>
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-gray-600">{agent.code}</td>
                  <td className="px-4 py-3 text-right text-gray-700">{agent.stats.partners}</td>
                  <td className="px-4 py-3 text-right text-gray-900">{formatMoney(agent.stats.accrued)}</td>
                  <td className="px-4 py-3 text-right text-gray-900">{formatMoney(agent.stats.available)}</td>
                  <td className="px-4 py-3 text-gray-600">{REQ_LABELS[agent.requisites_status] ?? agent.requisites_status}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`text-xs ${
                        agent.status === 'active' ? 'text-emerald-700' : 'text-red-700'
                      }`}
                    >
                      {STATUS_LABELS[agent.status] ?? agent.status}
                    </span>
                  </td>
                </tr>
              ))}
              {agents.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-gray-500">
                    Агентов пока нет.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {detail && (
        <div className="space-y-4 border-t border-gray-200 pt-6">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-gray-900">{detail.agent.full_name}</h2>
              <p className="text-sm text-gray-500">
                {detail.agent.email} · код {detail.agent.code} · зарегистрирован{' '}
                {new Date(detail.agent.created_at).toLocaleDateString('ru-RU')}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              {detail.agent.requisites_status !== 'accepted' && (
                <button
                  onClick={() =>
                    requisitesMutation.mutate({ id: detail.agent.id, status: 'accepted' })
                  }
                  className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg border border-emerald-200 text-emerald-700 text-sm"
                >
                  <CheckCircle2 className="w-4 h-4" /> Принять реквизиты
                </button>
              )}
              <button
                onClick={() =>
                  statusMutation.mutate({
                    id: detail.agent.id,
                    active: detail.agent.status !== 'active',
                  })
                }
                className={`inline-flex items-center gap-1.5 px-3 py-2 rounded-lg border text-sm ${
                  detail.agent.status === 'active'
                    ? 'border-red-200 text-red-700'
                    : 'border-emerald-200 text-emerald-700'
                }`}
              >
                {detail.agent.status === 'active' ? (
                  <>
                    <ShieldOff className="w-4 h-4" /> Заблокировать
                  </>
                ) : (
                  <>
                    <ShieldCheck className="w-4 h-4" /> Разблокировать
                  </>
                )}
              </button>
            </div>
          </div>

          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            {[
              ['Партнёров', detail.agent.stats.partners],
              ['Клиентов', detail.agent.stats.clients],
              ['Начислено', formatMoney(detail.agent.stats.accrued)],
              ['Доступно', formatMoney(detail.agent.stats.available)],
            ].map(([label, value]) => (
              <div key={String(label)} className="bg-white border border-gray-200 rounded-xl p-3">
                <div className="text-xs text-gray-500">{label}</div>
                <div className="text-lg font-semibold text-gray-900">{value}</div>
              </div>
            ))}
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
              <div className="px-4 py-3 border-b border-gray-100 text-sm font-medium text-gray-900">
                Партнёры агента
              </div>
              <table className="w-full text-sm">
                <tbody>
                  {detail.partners.map((partner) => (
                    <tr key={partner.id} className="border-t border-gray-100">
                      <td className="px-4 py-2.5">{partner.name}</td>
                      <td className="px-4 py-2.5 text-right text-gray-600">{partner.clients} кл.</td>
                      <td className="px-4 py-2.5 text-right text-gray-900">{formatMoney(partner.accrued)}</td>
                    </tr>
                  ))}
                  {detail.partners.length === 0 && (
                    <tr>
                      <td className="px-4 py-6 text-center text-gray-500">Пока нет партнёров</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
              <div className="px-4 py-3 border-b border-gray-100 text-sm font-medium text-gray-900">
                Начисления
              </div>
              <table className="w-full text-sm">
                <tbody>
                  {detail.accruals.map((accrual) => (
                    <tr key={accrual.id} className="border-t border-gray-100">
                      <td className="px-4 py-2.5 text-gray-600">
                        {new Date(accrual.created_at).toLocaleDateString('ru-RU')}
                        <span className="block text-xs text-gray-400">№{accrual.client_ref}</span>
                        {accrual.comment && (
                          <span className="block text-xs text-gray-400">Причина: {accrual.comment}</span>
                        )}
                      </td>
                      <td className="px-4 py-2.5 text-right text-gray-900">{formatMoney(accrual.amount)}</td>
                      <td className="px-4 py-2.5 text-right text-xs text-gray-500">
                        {ACCRUAL_LABELS[accrual.status] ?? accrual.status}
                      </td>
                      <td className="px-4 py-2.5 text-right">
                        {accrual.status === 'cancelled' ? (
                          <button
                            onClick={() => handleAccrualCorrection(accrual.id, 'accrued')}
                            className="rounded border border-emerald-200 px-2 py-1 text-xs text-emerald-700 hover:bg-emerald-50"
                          >
                            Вернуть
                          </button>
                        ) : (
                          <button
                            onClick={() => handleAccrualCorrection(accrual.id, 'cancelled')}
                            className="rounded border border-red-200 px-2 py-1 text-xs text-red-700 hover:bg-red-50"
                          >
                            Отменить
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                  {detail.accruals.length === 0 && (
                    <tr>
                      <td className="px-4 py-6 text-center text-gray-500">Начислений нет</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
            <div className="px-4 py-3 border-b border-gray-100 text-sm font-medium text-gray-900">
              Заявки на выплату
            </div>
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-xs uppercase text-gray-500">
                <tr>
                  <th className="text-left px-4 py-2">Создана</th>
                  <th className="text-left px-4 py-2">Период</th>
                  <th className="text-left px-4 py-2">Статус</th>
                  <th className="text-right px-4 py-2">Сумма</th>
                  <th className="text-right px-4 py-2">Действия</th>
                </tr>
              </thead>
              <tbody>
                {detail.payouts.map((payout) => (
                  <tr key={payout.id} className="border-t border-gray-100">
                    <td className="px-4 py-2.5 text-gray-600">
                      {new Date(payout.created_at).toLocaleDateString('ru-RU')}
                    </td>
                    <td className="px-4 py-2.5 text-gray-600">{payout.period || '—'}</td>
                    <td className="px-4 py-2.5 text-gray-700">
                      {PAYOUT_LABELS[payout.status] ?? payout.status}
                    </td>
                    <td className="px-4 py-2.5 text-right text-gray-900">{formatMoney(payout.amount)}</td>
                    <td className="px-4 py-2.5 text-right">
                      <div className="flex flex-wrap justify-end gap-1">
                        {PAYOUT_ACTIONS.filter((action) => action.status !== payout.status).map((action) => (
                          <button
                            key={action.status}
                            onClick={() => payoutMutation.mutate({ payout, status: action.status })}
                            className="px-2 py-1 rounded border border-gray-200 text-xs text-gray-600 hover:border-blue-300 hover:text-blue-700"
                          >
                            {action.label}
                          </button>
                        ))}
                      </div>
                    </td>
                  </tr>
                ))}
                {detail.payouts.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-4 py-6 text-center text-gray-500">
                      Заявок нет
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
