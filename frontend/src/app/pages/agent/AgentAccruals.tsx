import { useState } from 'react';
import { Loader2 } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { getAgentAccruals } from '@/app/api/agent';
import { formatMoney } from '@/app/utils/money';

const STATUS_LABELS: Record<string, string> = {
  accrued: 'Начислено',
  paid: 'Выплачено',
  cancelled: 'Отменено',
  review: 'На проверке',
};

const STATUS_STYLES: Record<string, string> = {
  accrued: 'text-emerald-700',
  paid: 'text-emerald-700',
  cancelled: 'text-red-600',
  review: 'text-amber-600',
};

export default function AgentAccruals() {
  const [status, setStatus] = useState('');
  const { data: accruals = [], isLoading } = useQuery({
    queryKey: ['agent', 'accruals'],
    queryFn: getAgentAccruals,
  });

  const filtered = status ? accruals.filter((item) => item.status === status) : accruals;

  if (isLoading) {
    return (
      <div className="py-20 flex justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-emerald-600" />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-6xl">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Начисления</h1>
          <p className="text-sm text-gray-500 mt-1">
            1 000 ₽ за каждого клиента партнёра, дошедшего до введения в процедуру.
          </p>
        </div>
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white"
        >
          <option value="">Все статусы</option>
          <option value="accrued">Начислено</option>
          <option value="paid">Выплачено</option>
          <option value="review">На проверке</option>
          <option value="cancelled">Отменено</option>
        </select>
      </div>

      <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-xs uppercase tracking-wide text-gray-500">
            <tr>
              <th className="text-left px-4 py-3">Дата</th>
              <th className="text-left px-4 py-3">Партнёр</th>
              <th className="text-left px-4 py-3">Клиент</th>
              <th className="text-left px-4 py-3">Статус</th>
              <th className="text-right px-4 py-3">Сумма</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((item) => (
              <tr key={item.id} className="border-t border-gray-100">
                <td className="px-4 py-3 text-gray-600 whitespace-nowrap">
                  {new Date(item.created_at).toLocaleDateString('ru-RU')}
                </td>
                <td className="px-4 py-3 text-gray-900">
                  {item.partner_name}
                  {item.comment && (
                    <span className="block text-xs text-gray-400">Причина: {item.comment}</span>
                  )}
                </td>
                <td className="px-4 py-3 text-gray-600">№{item.client_ref}</td>
                <td className={`px-4 py-3 ${STATUS_STYLES[item.status] ?? 'text-gray-600'}`}>
                  {STATUS_LABELS[item.status] ?? item.status}
                </td>
                <td className="px-4 py-3 text-right font-medium text-gray-900">
                  {formatMoney(item.amount)}
                </td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-12 text-center text-gray-500">
                  Начислений пока нет.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <p className="text-xs text-gray-400">
        Начисления не удаляются. Если нужна корректировка — напишите в поддержку, её сделает администратор
        с записью в журнале.
      </p>
    </div>
  );
}
