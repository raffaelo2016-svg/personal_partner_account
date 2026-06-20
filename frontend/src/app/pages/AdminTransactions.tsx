import { useCallback, useMemo, useState } from 'react';
import { CreditCard, Loader2 } from 'lucide-react';
import CustomSelect from '../components/ui/CustomSelect';
import { useInfiniteAdminTransactions } from '@/app/hooks/useAdminTransactions';
import { useIntersectionObserver } from '@/app/hooks/useIntersectionObserver';
import { formatDateShort } from '@/app/utils/formatDate';
import { useTimezone } from '@/app/contexts/TimezoneContext';
import type { TransactionStatus } from '@/app/api/adminTransactions';

const STATUS_LABELS: Record<string, string> = {
  completed: 'Завершено',
  pending: 'В обработке',
  failed: 'Ошибка',
};

const STATUS_COLORS: Record<string, string> = {
  completed: 'bg-green-100 text-green-700',
  pending: 'bg-yellow-100 text-yellow-700',
  failed: 'bg-red-100 text-red-700',
};

const STATUS_FILTER_OPTIONS = [
  { value: 'all', label: 'Все статусы' },
  { value: 'pending', label: 'В обработке' },
  { value: 'completed', label: 'Завершено' },
  { value: 'failed', label: 'Ошибка' },
];

export default function AdminTransactions() {
  const tz = useTimezone();
  const [statusFilter, setStatusFilter] = useState<string>('all');

  const filters = {
    status: statusFilter !== 'all' ? (statusFilter as TransactionStatus) : undefined,
  };

  const { data: pages, isLoading, fetchNextPage, hasNextPage, isFetchingNextPage } =
    useInfiniteAdminTransactions(filters);

  const loadMore = useCallback(() => {
    if (hasNextPage) fetchNextPage();
  }, [hasNextPage, fetchNextPage]);
  const sentinelRef = useIntersectionObserver(loadMore, !!hasNextPage && !isFetchingNextPage);

  const items = useMemo(() => pages?.pages.flatMap((p) => p.items) ?? [], [pages]);
  const total = pages?.pages[0]?.total ?? 0;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold text-gray-900">Транзакции</h1>
        <p className="text-gray-600 mt-2">Всего: {total}</p>
      </div>

      <div className="bg-white rounded-xl shadow-sm p-6">
        <div className="mb-6 max-w-xs">
          <CustomSelect
            value={statusFilter}
            onChange={setStatusFilter}
            options={STATUS_FILTER_OPTIONS}
          />
        </div>

        {isLoading ? (
          <div className="flex justify-center py-10">
            <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
          </div>
        ) : items.length === 0 ? (
          <p className="text-center text-gray-500 py-10">Транзакций пока нет</p>
        ) : (
          <div className="space-y-4">
            {items.map((t) => (
              <div
                key={t.id}
                className="p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
              >
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <CreditCard className="w-5 h-5 text-gray-400" />
                    <span className="text-sm font-medium text-gray-900">{t.id.slice(0, 8)}</span>
                  </div>
                  <span
                    className={`text-xs px-2 py-1 rounded-full ${STATUS_COLORS[t.status] ?? 'bg-gray-100 text-gray-700'}`}
                  >
                    {STATUS_LABELS[t.status] ?? t.status}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-600">{t.partner_name}</p>
                    <p className="text-xs text-gray-500 mt-0.5">Клиент: {t.client_name ?? '—'}</p>
                    <p className="text-xs text-gray-400 mt-0.5">{formatDateShort(t.created_at, tz)}</p>
                  </div>
                  <p className="text-lg font-semibold text-gray-900">
                    {(t.amount / 100).toLocaleString('ru-RU')} ₽
                  </p>
                </div>
              </div>
            ))}

            <div ref={sentinelRef} className="h-4" />

            {isFetchingNextPage && (
              <div className="flex justify-center py-4">
                <Loader2 className="w-5 h-5 animate-spin text-gray-400" />
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
