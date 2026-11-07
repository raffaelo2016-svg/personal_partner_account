import { Loader2 } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { getAgentPartners } from '@/app/api/agent';
import { formatMoney } from '@/app/utils/money';

const PARTNER_STATUS: Record<string, string> = {
  active: 'Активен',
  pending: 'На проверке',
  blocked: 'Заблокирован',
};

export default function AgentPartners() {
  const { data: partners = [], isLoading } = useQuery({
    queryKey: ['agent', 'partners'],
    queryFn: getAgentPartners,
  });

  if (isLoading) {
    return (
      <div className="py-20 flex justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-emerald-600" />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-6xl">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">Партнёры</h1>
        <p className="text-sm text-gray-500 mt-1">
          Все, кто зарегистрировался по вашей ссылке. Чужие партнёры и их клиенты вам не видны.
        </p>
      </div>

      <div className="bg-white border border-gray-200 rounded-xl overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-xs uppercase tracking-wide text-gray-500">
            <tr>
              <th className="text-left px-4 py-3">Партнёр</th>
              <th className="text-left px-4 py-3">Статус</th>
              <th className="text-left px-4 py-3">Закреплён</th>
              <th className="text-right px-4 py-3">Клиентов</th>
              <th className="text-right px-4 py-3">Начислено</th>
            </tr>
          </thead>
          <tbody>
            {partners.map((partner) => (
              <tr key={partner.id} className="border-t border-gray-100">
                <td className="px-4 py-3 font-medium text-gray-900">{partner.name}</td>
                <td className="px-4 py-3 text-gray-600">
                  {PARTNER_STATUS[partner.status] ?? partner.status}
                </td>
                <td className="px-4 py-3 text-gray-600">
                  {partner.linked_at ? new Date(partner.linked_at).toLocaleDateString('ru-RU') : '—'}
                </td>
                <td className="px-4 py-3 text-right text-gray-700">{partner.clients}</td>
                <td className="px-4 py-3 text-right text-gray-900">{formatMoney(partner.accrued)}</td>
              </tr>
            ))}
            {partners.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-12 text-center text-gray-500">
                  Пока никто не зарегистрировался по вашей ссылке.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
