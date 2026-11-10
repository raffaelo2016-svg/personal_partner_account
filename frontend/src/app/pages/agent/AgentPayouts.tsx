import { useState } from 'react';
import { AlertCircle, Loader2, Wallet } from 'lucide-react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getAgentMe, getAgentPayouts, requestPayout } from '@/app/api/agent';
import { formatMoney } from '@/app/utils/money';
import { getApiErrorMessage } from '@/app/utils/apiError';

const STATUS_LABELS: Record<string, { label: string; className: string }> = {
  submitted: { label: 'Отправлена', className: 'bg-blue-50 text-blue-700 border-blue-200' },
  checking: { label: 'Проверяем', className: 'bg-amber-50 text-amber-700 border-amber-200' },
  scheduled: { label: 'В выплате', className: 'bg-indigo-50 text-indigo-700 border-indigo-200' },
  paid: { label: 'Выплачена', className: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
  needs_fix: { label: 'Нужны правки', className: 'bg-red-50 text-red-700 border-red-200' },
  cancelled: { label: 'Отменена', className: 'bg-gray-100 text-gray-600 border-gray-200' },
};

const ACTIVE = ['submitted', 'checking', 'scheduled', 'needs_fix'];

export default function AgentPayouts() {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const { data: me } = useQuery({ queryKey: ['agent', 'me'], queryFn: getAgentMe });
  const { data: payouts = [], isLoading } = useQuery({
    queryKey: ['agent', 'payouts'],
    queryFn: getAgentPayouts,
  });

  const mutation = useMutation({
    mutationFn: requestPayout,
    onSuccess: async () => {
      setError(null);
      await queryClient.invalidateQueries({ queryKey: ['agent'] });
    },
    onError: (err) => setError(getApiErrorMessage(err)),
  });

  const hasActive = payouts.some((item) => ACTIVE.includes(item.status));
  const canRequest = Boolean(me && me.stats.available > 0 && !hasActive);

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">Выплаты</h1>
        <p className="text-sm text-gray-500 mt-1">
          Заявка до 14-го числа попадает в выплату 15-го, позже — в следующий цикл.
        </p>
      </div>

      <div className="bg-white border border-gray-200 rounded-xl p-5 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center">
            <Wallet className="w-6 h-6" />
          </div>
          <div>
            <div className="text-xs text-gray-500">Доступно к выплате</div>
            <div className="text-2xl font-semibold text-gray-900">
              {me ? formatMoney(me.stats.available) : '—'}
            </div>
          </div>
        </div>

        <button
          onClick={() => mutation.mutate()}
          disabled={!canRequest || mutation.isPending}
          className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-lg bg-emerald-600 text-white text-sm font-medium hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {mutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
          Запросить выплату
        </button>
      </div>

      {error && (
        <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700 flex items-center gap-2">
          <AlertCircle className="w-4 h-4" />
          {error}
        </div>
      )}

      {me && me.profile.requisites_status !== 'accepted' && (
        <div className="p-3 rounded-lg bg-amber-50 border border-amber-200 text-sm text-amber-800">
          Чтобы запросить выплату, заполните реквизиты и дождитесь проверки администратором.
        </div>
      )}

      {hasActive && (
        <div className="p-3 rounded-lg bg-blue-50 border border-blue-200 text-sm text-blue-800">
          У вас уже есть активная заявка. Новая появится после её закрытия.
        </div>
      )}

      <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-xs uppercase tracking-wide text-gray-500">
            <tr>
              <th className="text-left px-4 py-3">Создана</th>
              <th className="text-left px-4 py-3">Период</th>
              <th className="text-left px-4 py-3">Статус</th>
              <th className="text-right px-4 py-3">Сумма</th>
            </tr>
          </thead>
          <tbody>
            {payouts.map((item) => {
              const status = STATUS_LABELS[item.status] ?? STATUS_LABELS.cancelled;
              return (
                <tr key={item.id} className="border-t border-gray-100">
                  <td className="px-4 py-3 text-gray-600">
                    {new Date(item.created_at).toLocaleDateString('ru-RU')}
                  </td>
                  <td className="px-4 py-3 text-gray-600">{item.period || '—'}</td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex px-2 py-0.5 rounded-full border text-xs ${status.className}`}>
                      {status.label}
                    </span>
                    {item.comment && <div className="text-xs text-gray-400 mt-1">{item.comment}</div>}
                  </td>
                  <td className="px-4 py-3 text-right font-medium text-gray-900">
                    {formatMoney(item.amount)}
                  </td>
                </tr>
              );
            })}
            {!isLoading && payouts.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-12 text-center text-gray-500">
                  Заявок пока не было.
                </td>
              </tr>
            )}
          </tbody>
        </table>
        {isLoading && (
          <div className="py-8 flex justify-center">
            <Loader2 className="w-5 h-5 animate-spin text-emerald-600" />
          </div>
        )}
      </div>
    </div>
  );
}
